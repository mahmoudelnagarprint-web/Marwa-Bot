// app/api/chat/route.ts — الشات الحي المركزي لوكلاء مروة كور عبر بوابة الذكاء (Zero-Downtime)
// بأمر المالك 2026-10-21:
//   1. بناء System Prompt متخصص وديناميكي لكل وكيل بناءً على غرفته ودوره.
//   2. حقن بيانات الورشة الحية (POS SQLite + board_state + hardware_state + inboxes).
//   3. التقاط وتنفيذ أي أمر سلاش يصدره الوكيل عبر router_daemon.py آلياً.
//   4. توجيه ذكي حسب دور الوكيل (Strong/Light) مع Auto-Fallback كامل.
//   5. توثيق مستقل لكل وكيل في مجلد chats التابع له.

import { NextRequest, NextResponse } from 'next/server'
import { chatWithFailover, type ChatMsg } from '@/lib/ai-gateway'
import {
  resolveAgentKey,
  buildAgentSystemPrompt,
  executeSlashCommandsInText,
  executePosQuery,
  POS_DB_TOOLS,
  logAgentChatTurn,
  AGENT_MAP,
} from '@/lib/agent-intelligence'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

export async function POST(req: NextRequest) {
  let body: { agent?: unknown; messages?: unknown; maxTokens?: unknown; chatId?: unknown }
  try {
    body = (await req.json()) as typeof body
  } catch {
    return NextResponse.json({ ok: false, reason: 'جسم الطلب غير صالح' }, { status: 400 })
  }

  const agentKey = resolveAgentKey(body.agent)
  const agentWs = AGENT_MAP[agentKey]?.ws || 'marwa_maestro'

  const rawMsgs = Array.isArray(body.messages) ? body.messages : []
  const messages: ChatMsg[] = rawMsgs
    .filter((m): m is { role: string; content: string } =>
      typeof m === 'object' && m !== null && typeof (m as { content?: unknown }).content === 'string')
    .map((m): ChatMsg => ({
      role: m.role === 'assistant' ? 'assistant' : m.role === 'system' ? 'system' : 'user',
      content: (m.content || '').slice(0, 5000),
    }))
    .slice(-16)

  if (messages.length === 0) {
    return NextResponse.json({ ok: false, reason: 'لا رسائل في المحادثة' }, { status: 400 })
  }

  // استخلاص آخر رسالة من المستخدم لتحليل الكلمات المفتاحية والبحث في الـ POS
  const lastUserMsg = [...messages].reverse().find((m) => m.role === 'user')?.content || ''

  // بناء البرومبت التخصصي الغني والمطعم بتدريب الوكيل الأصلي والأدوات الحية
  const systemPromptContent = buildAgentSystemPrompt(agentKey, lastUserMsg)
  const systemMsg: ChatMsg = {
    role: 'system',
    content: systemPromptContent,
  }

  // إرسال الطلب عبر بوابة الذكاء الاصطناعي مع تفعيل أداة استعلام قاعدة البيانات (Dynamic POS Tool)
  const t0 = Date.now()
  const result = await chatWithFailover(agentWs, [systemMsg, ...messages], {
    maxTokens: typeof body.maxTokens === 'number' ? body.maxTokens : 2048,
    tools: POS_DB_TOOLS,
    toolExecutor: async (name: string, args: Record<string, unknown>) => {
      if (name === 'query_pos_db') {
        const sql = String(args.sql || '')
        return executePosQuery(sql)
      }
      return { error: `أداة غير معروفة: ${name}` }
    },
  })

  if (!result.ok) {
    return NextResponse.json(result, { status: 502 })
  }

  let finalReply = result.text

  // فحص إذا كان الرد عبارة عن JSON Tool Call ناتج مباشرة من النموذج بدلاً من نص طبيعي
  const jsonToolMatch = /\{\s*"name"\s*:\s*"query_pos_db"\s*,\s*"parameters"\s*:\s*\{\s*"sql"\s*:\s*"([^"]+)"/i.exec(finalReply)
  if (jsonToolMatch && jsonToolMatch[1]) {
    try {
      const sqlToExec = jsonToolMatch[1].replace(/\\"/g, '"').replace(/\\'/g, "'")
      const qRes = executePosQuery(sqlToExec)
      if (qRes.ok && qRes.data) {
        finalReply = `📊 **[استعلام قاعدة البيانات الحية - ${qRes.count} سجل]**:\n` +
          '```json\n' + JSON.stringify(qRes.data, null, 2).slice(0, 1500) + '\n```'
      }
    } catch { /* نتجاهل */ }
  }

  // فحص إذا قام الوكيل بكتابة استعلام SQL نصي مثل [SQL: SELECT ...] لتنفيذه ديناميكياً
  const sqlMatch = /\[SQL:\s*(SELECT[\s\S]*?)\]/i.exec(finalReply)
  if (sqlMatch && sqlMatch[1]) {
    try {
      const qRes = executePosQuery(sqlMatch[1])
      if (qRes.ok && qRes.data && qRes.data.length > 0) {
        finalReply += `\n\n📊 **[نتائج استعلام قاعدة البيانات الحية - ${qRes.count} سجل]**:\n` +
          '```json\n' + JSON.stringify(qRes.data, null, 2).slice(0, 1500) + '\n```'
      } else if (qRes.error) {
        finalReply += `\n\n⚠️ **[تنبيه أداة SQL]**: ${qRes.error}`
      }
    } catch { /* نتجاهل */ }
  }

  // فحص استجابة الوكيل لتنفيذ أي أمر سلاش صادر منه (مثل /task @bebo أو /summon @salma)
  const slashAction = await executeSlashCommandsInText(finalReply)
  if (slashAction.executed && slashAction.log.length > 0) {
    const confirmation = `\n\n⚡ **[تنفيذ آلي من محرك النظام]**:\n` + slashAction.log.map((l) => `• ${l}`).join('\n')
    finalReply += confirmation
  }

  // تسجيل دور المحادثة في مجلد chats الخاص بالوكيل لاستقلالية وحفظ الجلسات
  logAgentChatTurn(agentKey, lastUserMsg, finalReply)

  return NextResponse.json({
    ok: true,
    text: finalReply,
    rawText: result.text,
    agent: agentKey,
    provider: result.provider,
    handover: result.handover,
    compacted: result.compacted,
    usage: result.usage,
    executedSlash: slashAction.executed ? slashAction.log : undefined,
    latency_ms: Date.now() - t0,
  })
}
