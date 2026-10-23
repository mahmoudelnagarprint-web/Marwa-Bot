// lib/agent-task-runner.ts — محرك التنفيذ الحقيقي لمهام الوكلاء (MARWA CORE)
// ⚠️ قاعدة صارمة: المهمة لا تُغلق أبداً بلا استدعاء نموذج فعلي.
// كل إغلاق يمر من هنا: تعليمات الوكيل + بيانات المهمة → النموذج → تقرير حقيقي → agent_updates.
// يُستخدم من: عامل المهام المجدولة (worker) + التنفيذ الفوري من الواجهة (/api/tasks/execute).

import type { SupabaseClient } from '@supabase/supabase-js'
import { chatWithFailover, type ChatMsg } from '@/lib/ai-gateway'
import {
  AGENT_MAP,
  buildAgentSystemPrompt,
  executePosQuery,
  lookupAgentKey,
  POS_DB_TOOLS,
} from '@/lib/agent-intelligence'

export type TaskRow = {
  id: string
  agent_id: string
  title: string
  description: string | null
  schedule_type?: string | null
  scheduled_time?: string | null
  attempt_count?: number | null
  backoff_level?: number | null
  dependency_id?: string | null
}

export type RunOutcome = {
  ok: true
  body: string
  agentKey: string
  agentName: string
  provider: string
  latencyMs: number
  trimmed: { dropped: number; savedChars: number } | null
}

export type RunFailure = Error & {
  exhausted?: string
  retryAfterMs?: number
  gatewayReason?: string
}

/** يوم القاهرة بصيغة YYYY-MM-DD — مرجع واحد لكل الطوابع الزمنية في المحرك */
export function cairoDay(date: Date = new Date()): string {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Africa/Cairo', year: 'numeric', month: '2-digit', day: '2-digit',
  }).formatToParts(date)
  const v = Object.fromEntries(parts.map((p) => [p.type, p.value]))
  return `${v.year}-${v.month}-${v.day}`
}

export function cairoParts(date: Date) {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Africa/Cairo', year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
  }).formatToParts(date)
  return Object.fromEntries(parts.map((part) => [part.type, part.value])) as Record<string, string>
}

/** تحويل رد النموذج لنقاط عربية نظيفة — إزالة كتل التفكير وأي وسوم إنجليزية */
export function reportBullets(text: string, agentName: string): string {
  const cleaned = text
    .replace(/<think[^>]*>[\s\S]*?<\/think>/gi, '')
    .replace(/<reasoning[^>]*>[\s\S]*?<\/reasoning>/gi, '')
    .replace(/<\/?(?:minimax:[\w-]+|invoke|parameter|think|reasoning)[^>]*>/gi, '')
    .replace(/```[\s\S]*?```/g, '')
  const lines = cleaned.split(/\r?\n/).map((line) => line.trim()).filter(Boolean)
  const bullets = lines.map((line) => (/^[-•*]\s*/.test(line) ? `• ${line.replace(/^[-•*]\s*/, '')}` : `• ${line}`))
  return bullets.slice(0, 16).join('\n') || `• ${agentName} لم يرجع تفاصيل قابلة للعرض.`
}

/** أقل طول مقبول لتقرير إنجاز حقيقي — أقل من كذا = النموذج استهّل وقت في مقدمة ولم يكتب تقرير */
const MIN_REPORT_CHARS = 140
const MIN_REPORT_LINES = 2

function looksUnfinished(body: string): boolean {
  const lines = body.split('\n').filter(Boolean)
  if (lines.length < MIN_REPORT_LINES || body.length < MIN_REPORT_CHARS) return true
  // مقدمة بلا محتوى: «دعني أحاول…» أو «سأبحث…» أو رد ينتهي بنقطتين
  return /^(•\s*)?(دعني|سأقوم|سأحاول|هحاول|خليني|لحظة|جارٍ|انتظر)/.test(body.trim()) ||
    /:$/.test(body.trim().split('\n').pop() || '')
}

/** استدعاء النموذج الحقيقي لوكيل على مهمة محددة — بلا اختصارات وبلا تقارير جاهزة */
export async function runAgentTask(
  agentId: string,
  title: string,
  description: string | null,
): Promise<RunOutcome> {
  const startedAt = Date.now()
  const agentKey = lookupAgentKey(agentId)
  if (!agentKey || !AGENT_MAP[agentKey]) throw new Error('معرّف الوكيل غير مدعوم في محرك المهام')
  const agent = AGENT_MAP[agentKey]
  const taskText = [title, description].filter(Boolean).join('\n')
  const prompt = [
    `هذه مهمة مُسندة إليك بصفتك ${agent.name}. نفّذ ما يمكن إنجازه عبر الأدوات المتاحة.`,
    'لو المهمة محتاجة بيانات حقيقية (أوردر، عميل، مديونية، خامة) استعلم الأول بأداة query_pos_db، وبعد نتيجة الاستعلام اكتب التقرير فوراً — ممنوع تسيب المهمة بمقدمة زي «دعني أشوف» أو «هجرب».',
    'ممنوع تعديل قاعدة البيانات أو إرسال أي رسالة خارجية. اكتب تقرير إنجاز باللهجة المصرية في نقاط قصيرة، واذكر بوضوح إذا لم تتوفر البيانات.',
    `تفاصيل المهمة:\n${taskText}`,
  ].join('\n\n')
  const system: ChatMsg = { role: 'system', content: buildAgentSystemPrompt(agentKey, prompt, { background: true }) }
  const result = await chatWithFailover(agent.ws, [system, { role: 'user', content: prompt }], {
    maxTokens: 1400,
    tools: POS_DB_TOOLS,
    // تقليم ذكي للسياق: تعليمات + بيانات المهمة فقط، بلا سجل دردشة ولا كتل بيانات محقونة
    background: true,
    toolExecutor: async (name, args) => {
      if (name !== 'query_pos_db') return { ok: false, error: 'الأداة غير مسموحة في العامل الخلفي' }
      return executePosQuery(typeof args.sql === 'string' ? args.sql : '')
    },
  })

  if (!result.ok || !result.text?.trim()) {
    const failure = new Error(`${agent.name} لم يُكمل التقرير بسبب تعذر الاستجابة`) as RunFailure
    if (!result.ok) {
      failure.exhausted = result.exhausted
      failure.retryAfterMs = result.retryAfterMs
      failure.gatewayReason = `${result.reason} | ${result.handover
        .filter((h) => h.action === 'fail' || h.action === 'skip')
        .map((h) => `${h.provider}: ${h.detail}`)
        .join(' ; ')
        .slice(0, 160)}`
    }
    throw failure
  }

  let body = reportBullets(result.text.trim(), agent.name)

  // جولة إكمال إلزامية: النموذج رجع مقدمة فقط («دعني أشوف…» / سطر ناقص) ⇒ لا نقبلها كتقرير.
  // نطلب منه التقرير النهائي بلا أدوات ولا مقدمات، ونحتفظ بالجولة الأولى كسياق للتحسين فقط.
  if (looksUnfinished(body)) {
    const finish = await chatWithFailover(agent.ws, [
      system,
      { role: 'user', content: prompt },
      { role: 'assistant', content: result.text.trim() },
      {
        role: 'user',
        content: [
          'دي كانت مقدمة بس. مطلوب منك الآن التقرير النهائي نفسه، ممنوع أي مقدمة أو «دعني».',
          'اكتب من 3 لـ6 نقاط تبدأ بـ«•»: اللي اتعمل فعلاً، واللي ناقص أو محتاج بيانات، والخطوة التالية.',
          'لو مفيش بيانات كافية، قول كده صريح في نقطة واحدة واذكر اللي محتاجه بالظبط.',
        ].join('\n'),
      },
    ], { maxTokens: 1200, background: true })

    if (finish.ok && finish.text?.trim()) {
      const retryBody = reportBullets(finish.text.trim(), agent.name)
      // نقبل الجولة الثانية لو أطول أو لو خلّصت المقدمة الناقصة
      if (retryBody.length >= body.length || looksUnfinished(body)) {
        return {
          ok: true,
          body: retryBody,
          agentKey,
          agentName: agent.name,
          provider: `${finish.provider.name} (${finish.provider.model})`,
          latencyMs: Date.now() - startedAt,
          trimmed: finish.trimmed ?? result.trimmed ?? null,
        }
      }
    }
  }

  return {
    ok: true,
    body,
    agentKey,
    agentName: agent.name,
    provider: `${result.provider.name} (${result.provider.model})`,
    latencyMs: Date.now() - startedAt,
    trimmed: result.trimmed ?? null,
  }
}

/**
 * حفظ نتيجة التنفيذ الحقيقي: تقرير في agent_updates + إغلاق المهمة + تصفير الإرجاء.
 * op_id موحّد يجعل الإغلاق idempotent — لا تقرير مكرر لو أعاد العامل المحاولة.
 */
export async function persistTaskCompletion(
  admin: SupabaseClient,
  task: TaskRow,
  outcome: RunOutcome,
  opPrefix = 'scheduled',
): Promise<{ reportError: string | null; finishError: string | null }> {
  const finishedAt = new Date()
  const cairo = cairoParts(finishedAt)
  const report = {
    agent_id: task.agent_id,
    kind: 'report',
    title: `إنجاز المهمة: ${task.title}`,
    body: outcome.body,
    severity: 'منخفض',
    status: 'approved',
    decided_by: 'agent',
    decided_at: finishedAt.toISOString(),
    op_id: `${opPrefix}:${task.id}:${cairo.year}-${cairo.month}-${cairo.day}`,
    payload: {
      task_id: task.id,
      category: task.agent_id,
      provider: outcome.provider,
      latency_ms: outcome.latencyMs,
      actions: [
        { type: 'navigate', label: `فتح غرفة ${outcome.agentName}`, href: `/agent/${outcome.agentKey}` },
        { type: 'copy', label: 'نسخ التقرير' },
      ],
    },
  }
  const { error: reportError } = await admin
    .from('agent_updates')
    .upsert(report, { onConflict: 'op_id', ignoreDuplicates: true })

  const { error: finishError } = await admin.from('agent_tasks').update({
    status: 'done',
    result_note: outcome.body.slice(0, 4000),
    last_run_at: finishedAt.toISOString(),
    // نجاح: تصفير الإرجاء والمحاولات وعدّاد التحرير — دورة جديدة نظيفة
    attempt_count: 0, backoff_level: 0, deferred_until: null, last_failure_reason: null,
    claimed_by: null, claimed_at: null, release_count: 0,
    updated_at: finishedAt.toISOString(),
  }).eq('id', task.id).eq('status', 'in_progress')

  return { reportError: reportError?.message ?? null, finishError: finishError?.message ?? null }
}

/**
 * تنفيذ مهمة موجودة فوراً (زر «نفّذ الآن» / الاعتماد اليدوي) — تنفيذ حقيقي لا تقرير جاهز.
 * يحجز المهمة ذرياً، يستدعي النموذج، يحفظ التقرير، ويغلقها كمكتملة.
 */
export async function executeTaskById(
  admin: SupabaseClient,
  taskId: string,
): Promise<{ ok: boolean; body?: string; agentName?: string; provider?: string; error?: string; exhausted?: string }> {
  const { data: task, error: readError } = await admin
    .from('agent_tasks')
    .select('id,agent_id,title,description,status,attempt_count,backoff_level,schedule_type,scheduled_time,archived_at')
    .eq('id', taskId)
    .maybeSingle()
  if (readError || !task) return { ok: false, error: 'المهمة غير موجودة أو تعذر قراءتها.' }
  if (task.archived_at) return { ok: false, error: 'المهمة مؤرشفة — لا يمكن تنفيذها.' }

  const { data: claimed } = await admin.from('agent_tasks')
    .update({
      status: 'in_progress',
      claimed_by: 'manual',
      claimed_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    })
    .eq('id', taskId).in('status', ['pending', 'done']).is('archived_at', null)
    .select('id,agent_id,title,description,attempt_count,backoff_level')
    .maybeSingle()
  if (!claimed) return { ok: false, error: 'المهمة مشغولة الآن أو حالتها لا تسمح بالتنفيذ.' }

  try {
    const outcome = await runAgentTask(claimed.agent_id, claimed.title, claimed.description)
    const { reportError, finishError } = await persistTaskCompletion(admin, claimed, outcome, 'manual')
    if (reportError) throw new Error(`تعذر حفظ تقرير الإنجاز: ${reportError}`)
    if (finishError) throw new Error(`تعذر إغلاق المهمة: ${finishError}`)
    return { ok: true, body: outcome.body, agentName: outcome.agentName, provider: outcome.provider }
  } catch (error) {
    const failure = error as RunFailure
    const message = failure.message || 'تعذر تنفيذ المهمة'
    // إعادة المهمة لحالتها السابقة مع سبب الفشل — بلا ادعاء إنجاز كاذب
    await admin.from('agent_tasks').update({
      status: 'pending',
      attempt_count: Number(claimed.attempt_count || 0) + 1,
      claimed_by: null,
      claimed_at: null,
      last_failure_reason: message.slice(0, 200),
      result_note: `لم تُنفَّذ — ${message}`.slice(0, 500),
      updated_at: new Date().toISOString(),
    }).eq('id', taskId).eq('status', 'in_progress')
    return { ok: false, error: message, exhausted: failure.exhausted }
  }
}
