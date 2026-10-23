// app/api/chat/route.ts — الشات الحي المركزي لوكلاء مروة كور (Active / Hot-Standby) — v3.1
//
// POST /api/chat   body: { agent, messages, maxTokens?, providerId?, strictProvider?, stream? }
//   - providerId   : اختيار يدوي مطلق (يلغي Auto-Test ويجعل المزود Active).
//   - strictProvider: مع providerId — بلا احتياطي آلي.
//   - stream: true : رد NDJSON أحداث حية (plan / attempt / failover / tool) ثم سطر نهائي type:"done".
//                    بدونه: رد JSON واحد كالسابق (متوافق مع الواجهة القديمة).
// GET  /api/chat?agent=&providerId=  → قائمة المزودين + Active/Standby الحاليان (للقائمة المنسدلة وشريط الحالة)
//
// 🆕 v3.1 — Inline Agent Chaining / Auto-Orchestration (أمر المالك 2026-10-23):
//   بعد تنفيذ أوامر السلاش في رد مروة (/summon @salma ... / @task @fares ...)،
//   يُستدعى الوكيل المستهدف فوراً داخلياً عبر chatWithFailover بمساحة عمله
//   وsystemPrompt الخاص به + POS_DB_TOOLS (قراءة قاعدة الأعمال)، وتفاصيل المهمة
//   تُمرر كرسالة user — ويُدمج رده أسفل رد مروة بفاصل جمالي واضح في finalReply.
//   عمق السلسلة = مستوى واحد (لا إعادة سلاش على ردود السلسلة) — منع الحلقات.

import { NextRequest, NextResponse } from 'next/server'
import { chatWithFailover, describeFleet, type ChatMsg, type GatewayEvent } from '@/lib/ai-gateway'
import {
  resolveAgentKey,
  buildAgentSystemPrompt,
  executeSlashCommandsInText,
  executePosQuery,
  POS_DB_TOOLS,
  logAgentChatTurn,
  AGENT_MAP,
  lookupAgentKey,
  type PosQueryResult,
} from '@/lib/agent-intelligence'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'
export const maxDuration = 120

const CONTEXT_WINDOW = 6
const MAX_MESSAGE_CHARS = 5_000
const MAX_BODY_BYTES = 256_000
const DEFAULT_MAX_TOKENS = 2048
const MAX_TOKENS_CAP = 4096
const MAX_SQL_DIRECTIVES = 2
const RESULT_PREVIEW_CHARS = 1_500
const PROVIDER_ID_RE = /^[A-Za-z0-9._:\-]{1,80}$/
/** الحد الأقصى للمهام المتسلسلة داخلياً في الرد الواحد (حماية تكلفة/زمن) */
const MAX_CHAINED_CALLS = 3

type Payload = Record<string, unknown>
type ChatBody = {
  agent?: unknown
  messages?: unknown
  maxTokens?: unknown
  providerId?: unknown
  strictProvider?: unknown
  stream?: unknown
}

function json(body: unknown, status = 200) {
  return NextResponse.json(body, { status, headers: { 'Cache-Control': 'no-store' } })
}

/** providerId قادم من المتصفح: نقبل معرّفاً بسيطاً فقط (الفراغ/auto = اختيار آلي) */
function cleanProviderId(v: unknown): string | undefined {
  if (typeof v !== 'string') return undefined
  const t = v.trim()
  if (!t || t === 'auto') return undefined
  return PROVIDER_ID_RE.test(t) ? t : undefined
}

function buildWindow(raw: unknown): ChatMsg[] {
  if (!Array.isArray(raw)) return []
  const clean: ChatMsg[] = []
  for (const m of raw) {
    if (typeof m !== 'object' || m === null) continue
    const { role, content } = m as { role?: unknown; content?: unknown }
    if ((role !== 'user' && role !== 'assistant') || typeof content !== 'string') continue
    const text = content.trim().slice(0, MAX_MESSAGE_CHARS)
    if (!text) continue
    clean.push({ role, content: text })
  }
  let win = clean.slice(-CONTEXT_WINDOW)
  while (win.length > 1 && win[0].role === 'assistant') win = win.slice(1)
  return win
}

function renderRows(res: PosQueryResult): string {
  let body = JSON.stringify(res.data ?? [], null, 2).replace(/```/g, "'''")
  if (body.length > RESULT_PREVIEW_CHARS) body = `${body.slice(0, RESULT_PREVIEW_CHARS)}\n… [مقتطع]`
  return '```json\n' + body + '\n```'
}

function extractTextToolSql(text: string): string | null {
  const t = text.trim()
  if (!t.startsWith('{') || !t.endsWith('}')) return null
  try {
    const parsed = JSON.parse(t) as { name?: unknown; parameters?: unknown; arguments?: unknown }
    if (parsed.name !== 'query_pos_db') return null
    let args: unknown = parsed.parameters ?? parsed.arguments
    if (typeof args === 'string') args = JSON.parse(args)
    const sql = (args as { sql?: unknown } | null)?.sql
    return typeof sql === 'string' && sql.trim() ? sql : null
  } catch {
    return null
  }
}

function runSqlDirectives(text: string): string {
  const re = /\[SQL:\s*(SELECT[^\]]*)\]/gi
  const blocks: string[] = []
  let m: RegExpExecArray | null
  while (blocks.length < MAX_SQL_DIRECTIVES && (m = re.exec(text)) !== null) {
    const res = executePosQuery(m[1])
    if (res.ok && res.data && res.data.length > 0) {
      blocks.push(`📊 **[نتائج استعلام قاعدة البيانات الحية - ${res.count} سجل]**:\n${renderRows(res)}`)
    } else if (!res.ok && res.error) {
      blocks.push(`⚠️ **[تنبيه أداة SQL]**: ${res.error}`)
    }
  }
  return blocks.join('\n\n')
}

/** منفذ الأدوات المشترك — نفس سلوك الاستدعاء الرئيسي (قراءة قاعدة الأعمال فقط) */
function makeToolExecutor() {
  return async (name: string, args: Record<string, unknown>) => {
    if (name === 'query_pos_db') {
      return executePosQuery(typeof args.sql === 'string' ? args.sql : '')
    }
    return { ok: false, error: `أداة غير معروفة: ${name}` }
  }
}

/** قلب المعالجة: يُستخدم للرد العادي ولرد البث معاً */
async function handleChat(
  body: ChatBody,
  t0: number,
  onEvent?: (e: GatewayEvent) => void,
  signal?: AbortSignal,
): Promise<{ status: number; payload: Payload }> {
  const agentKey = resolveAgentKey(body.agent)
  const agentWs = AGENT_MAP[agentKey]?.ws || 'marwa_maestro'

  const windowMsgs = buildWindow(body.messages)
  const lastUserMsg = [...windowMsgs].reverse().find((m) => m.role === 'user')?.content ?? ''
  if (!lastUserMsg) {
    return { status: 400, payload: { ok: false, reason: 'لا رسائل في المحادثة', latency_ms: Date.now() - t0 } }
  }

  const requestedTokens =
    typeof body.maxTokens === 'number' && Number.isFinite(body.maxTokens) ? Math.floor(body.maxTokens) : DEFAULT_MAX_TOKENS
  const maxTokens = Math.min(Math.max(requestedTokens, 256), MAX_TOKENS_CAP)

  const providerId = cleanProviderId(body.providerId)
  const strictProvider = providerId ? body.strictProvider === true : false

  const tPrompt = Date.now()
  const systemMsg: ChatMsg = { role: 'system', content: buildAgentSystemPrompt(agentKey, lastUserMsg) }
  const promptMs = Date.now() - tPrompt

  const tLlm = Date.now()
  const result = await chatWithFailover(agentWs, [systemMsg, ...windowMsgs], {
    maxTokens,
    tools: POS_DB_TOOLS,
    providerId, // (2) الاختيار اليدوي المطلق
    strictProvider,
    onEvent,
    signal,
    toolExecutor: makeToolExecutor(),
  })
  const llmMs = Date.now() - tLlm

  if (!result.ok) {
    return { status: 502, payload: { ...result, latency_ms: Date.now() - t0 } }
  }

  // أوامر السلاش تُنفَّذ على نص النموذج الأصلي فقط (لا على نتائج POS المُلحقة)
  const modelText = result.text
  let finalReply = modelText

  const textToolSql = extractTextToolSql(modelText)
  if (textToolSql) {
    const qRes = executePosQuery(textToolSql)
    finalReply = qRes.ok
      ? `📊 **[استعلام قاعدة البيانات الحية - ${qRes.count} سجل]**:\n${renderRows(qRes)}`
      : `⚠️ **[تنبيه أداة SQL]**: ${qRes.error ?? 'فشل الاستعلام'}`
  } else {
    const sqlBlocks = runSqlDirectives(modelText)
    if (sqlBlocks) finalReply += `\n\n${sqlBlocks}`
  }

  const slash = await executeSlashCommandsInText(modelText, agentKey)
  if (slash.executed && slash.log.length > 0) {
    finalReply += `\n\n⚡ **[تنفيذ آلي من محرك النظام]**:\n` + slash.log.map((l) => `• ${l}`).join('\n')
  }

  // ─── Inline Agent Chaining (أمر المالك 2026-10-23): الرد الفوري للوكيل المستدعى ───
  // بعد تسجيل مهام السلاش: أي مهمة/استدعاء موجّه لوكيل آخر (@salma / @fares / @bebo ...)
  // يُستدعى فوراً داخلياً عبر chatWithFailover بمساحة عمل الوكيل المستهدف وsystemPrompt
  // الخاص به + POS_DB_TOOLS (قراءة قاعدة الأعمال)، وتفاصيل المهمة تُمرر كرسالة user —
  // ويُدمج رده أسفل رد مروة بفاصل واضح. عمق السلسلة = مستوى واحد (بلا إعادة سلاش).
  const chainedAgents: string[] = []
  if (slash.executed && slash.tasks.length > 0) {
    // استخراج تفاصيل الأوامر من نص النموذج (نفس منطق محرك السلاش) لتمريرها كرسالة user
    const reDetails = /^[ \t]*\/(task|summon)[ \t]+@(\S+)[ \t]*(.*)$/gm
    const queueByTarget = new Map<string, string[]>()
    let mm: RegExpExecArray | null
    while ((mm = reDetails.exec(modelText)) !== null) {
      const target = lookupAgentKey(mm[2])
      const detail = (mm[3] || '').trim()
      if (!target || !detail || target === agentKey) continue
      const label = mm[1] === 'summon' ? 'استدعاء فوري' : 'مهمة رسمية'
      const userMsg =
        `مهمة مُسندة إليك من ${AGENT_MAP[agentKey].name} (${label}) — تفاصيلها:\n` +
        `${detail}\n\n` +
        `نفّذها الآن وأجب بنتيجة مباشرة ومختصرة — استخدم أداة قاعدة البيانات الحية (query_pos_db) إن احتجت أرقاماً، ولا تخترع أي رقم غير موجود.`
      const q = queueByTarget.get(target) ?? []
      if (q.length < 2) q.push(userMsg) // مهمتان كحد أقصى لكل وكيل في السلسلة
      queueByTarget.set(target, q)
    }

    // الترتيب نفسه الذي سُجّلت به المهام في slash.tasks (target/fileName)
    for (const taskRef of slash.tasks.slice(0, MAX_CHAINED_CALLS)) {
      const target = lookupAgentKey(taskRef.split('/')[0])
      if (!target) continue
      const taskUser = queueByTarget.get(target)?.shift()
      if (!taskUser) continue
      const targetWs = AGENT_MAP[target]?.ws || 'marwa_maestro'
      const targetName = AGENT_MAP[target]?.name ?? target
      try {
        const chainSystem: ChatMsg = { role: 'system', content: buildAgentSystemPrompt(target, taskUser) }
        const chainRes = await chatWithFailover(
          targetWs,
          [chainSystem, { role: 'user', content: taskUser }],
          {
            maxTokens: Math.min(maxTokens, 2048),
            tools: POS_DB_TOOLS,
            signal,
            toolExecutor: makeToolExecutor(),
          },
        )
        if (chainRes.ok && chainRes.text && chainRes.text.trim()) {
          finalReply += `\n\n---\n🤖 **[استجابة فورية من: ${targetName}]**\n${chainRes.text.trim()}`
          chainedAgents.push(target)
        } else {
          const errTxt = String(('reason' in chainRes && chainRes.reason) || 'رد فارغ')
          finalReply += `\n\n---\n⚠️ **[استجابة فورية من: ${targetName}]** تعذر الحصول على الرد (${errTxt}) — المهمة مسجلة في صندوقه وستُنفَّذ من جلسته.`
        }
      } catch (chainErr) {
        const errTxt = chainErr instanceof Error ? chainErr.message : String(chainErr)
        finalReply += `\n\n---\n⚠️ **[استجابة فورية من: ${targetName}]** فشل الاستدعاء الداخلي: ${errTxt} — المهمة مسجلة في صندوقه وستُنفَّذ من جلسته.`
      }
    }
  }

  logAgentChatTurn(agentKey, lastUserMsg, finalReply)

  return {
    status: 200,
    payload: {
      ok: true,
      text: finalReply,
      rawText: modelText,
      agent: agentKey,
      provider: result.provider, // { id, name, model } — النموذج الذي أجاب فعلياً
      model: result.provider.model,
      standby: result.standby, // الاحتياطي بعد هذه المحاولة
      manual: result.manual,
      attempts: result.attempts, // عدد المحاولات المستهلكة (1 = بلا تحويل)
      handover: result.handover,
      compacted: result.compacted,
      toolsFallback: result.toolsFallback,
      usage: result.usage,
      executedSlash: slash.executed ? slash.log : undefined,
      tasks: slash.tasks.length > 0 ? slash.tasks : undefined,
      chainedAgents: chainedAgents.length > 0 ? chainedAgents : undefined, // الوكلاء الذين استُدعوا فوراً
      latency_ms: Date.now() - t0,
      timings: { prompt_ms: promptMs, llm_ms: llmMs },
    },
  }
}

export async function POST(req: NextRequest) {
  const t0 = Date.now()
  try {
    if (Number(req.headers.get('content-length') ?? 0) > MAX_BODY_BYTES) {
      return json({ ok: false, reason: 'حجم الطلب كبير جداً' }, 413)
    }

    let body: ChatBody
    try {
      body = (await req.json()) as ChatBody
    } catch {
      return json({ ok: false, reason: 'جسم الطلب غير صالح' }, 400)
    }
    if (!body || typeof body !== 'object') {
      return json({ ok: false, reason: 'جسم الطلب غير صالح' }, 400)
    }

    // ───── وضع البث: NDJSON — كل سطر JSON مستقل ─────
    if (body.stream === true) {
      const enc = new TextEncoder()
      const stream = new ReadableStream<Uint8Array>({
        async start(controller) {
          let closed = false
          const send = (obj: unknown) => {
            if (closed) return
            try {
              controller.enqueue(enc.encode(JSON.stringify(obj) + '\n'))
            } catch {
              closed = true // العميل أغلق الاتصال
            }
          }
          try {
            const { status, payload } = await handleChat(body, t0, (e) => send(e), req.signal)
            send({ type: 'done', status, ...payload })
          } catch (err) {
            console.error('[api/chat] خطأ غير متوقع (stream):', err instanceof Error ? err.stack ?? err.message : err)
            send({
              type: 'done',
              status: 500,
              ok: false,
              reason: 'خطأ داخلي غير متوقع في الشات — راجع سجل السيرفر',
              latency_ms: Date.now() - t0,
            })
          } finally {
            closed = true
            try {
              controller.close()
            } catch {
              /* أُغلق مسبقاً */
            }
          }
        },
      })
      return new Response(stream, {
        status: 200,
        headers: {
          'Content-Type': 'application/x-ndjson; charset=utf-8',
          'Cache-Control': 'no-store, no-transform',
          'X-Accel-Buffering': 'no', // يمنع Nginx من تجميع الأسطر
        },
      })
    }

    // ───── الوضع العادي: JSON واحد ─────
    const { status, payload } = await handleChat(body, t0, undefined, req.signal)
    return json(payload, status)
  } catch (err) {
    console.error('[api/chat] خطأ غير متوقع:', err instanceof Error ? err.stack ?? err.message : err)
    return json({ ok: false, reason: 'خطأ داخلي غير متوقع في الشات — راجع سجل السيرفر', latency_ms: Date.now() - t0 }, 500)
  }
}

/** حالة الأسطول للواجهة: القائمة المنسدلة + Active/Standby (بلا أي مفاتيح) */
export async function GET(req: NextRequest) {
  try {
    const sp = req.nextUrl.searchParams
    const agentKey = resolveAgentKey(sp.get('agent') ?? undefined)
    const agentWs = AGENT_MAP[agentKey]?.ws || 'marwa_maestro'
    const fleet = await describeFleet(agentWs, { providerId: cleanProviderId(sp.get('providerId')) })
    return json({ ok: true, agent: agentKey, ...fleet })
  } catch (err) {
    console.error('[api/chat GET] خطأ:', err instanceof Error ? err.stack ?? err.message : err)
    return json({ ok: false, reason: 'تعذر قراءة حالة الأسطول' }, 500)
  }
}
