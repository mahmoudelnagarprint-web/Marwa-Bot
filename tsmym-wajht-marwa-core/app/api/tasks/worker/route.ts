import { timingSafeEqual } from 'node:crypto'
import { NextRequest, NextResponse } from 'next/server'
import { chatWithFailover, type ChatMsg } from '@/lib/ai-gateway'
import {
  AGENT_MAP,
  buildAgentSystemPrompt,
  executePosQuery,
  lookupAgentKey,
  POS_DB_TOOLS,
} from '@/lib/agent-intelligence'
import { getSupabaseAdmin } from '@/lib/supabase-admin'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'
export const maxDuration = 120

function authorized(req: NextRequest): boolean {
  const expected = process.env.AGENT_TASK_WORKER_TOKEN
  const received = req.headers.get('authorization')?.replace(/^Bearer\s+/i, '') || ''
  if (!expected || !received) return false
  const a = Buffer.from(expected)
  const b = Buffer.from(received)
  return a.length === b.length && timingSafeEqual(a, b)
}

function cairoParts(date: Date) {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Africa/Cairo', year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
  }).formatToParts(date)
  return Object.fromEntries(parts.map((part) => [part.type, part.value])) as Record<string, string>
}

function dueToday(time: string | null, lastRunAt: string | null, now: Date, scheduleType: string, scheduleDay: number | null): boolean {
  if (!time) return false
  const today = cairoParts(now)
  const lastDate = lastRunAt ? cairoParts(new Date(lastRunAt)) : null
  if (scheduleType === 'weekly') {
    const dayName = new Intl.DateTimeFormat('en-US', { timeZone: 'Africa/Cairo', weekday: 'short' }).format(now)
    const dayNumber = ({ Sun: 0, Mon: 1, Tue: 2, Wed: 3, Thu: 4, Fri: 5, Sat: 6 } as Record<string, number>)[dayName]
    if (scheduleDay === null || scheduleDay !== dayNumber) return false
  }
  const target = time.slice(0, 5)
  return `${today.hour}:${today.minute}` >= target &&
    (!lastDate || `${lastDate.year}-${lastDate.month}-${lastDate.day}` !== `${today.year}-${today.month}-${today.day}`)
}

function reportBullets(text: string, agentName: string): string {
  // إزالة كتل التفكير وأي وسوم إنجليزية قبل تحويل السطور لنقاط (أمر المالك: بلا رغي ولا وسوم)
  const cleaned = text
    .replace(/<think[^>]*>[\s\S]*?<\/think>/gi, '')
    .replace(/<reasoning[^>]*>[\s\S]*?<\/reasoning>/gi, '')
    .replace(/<\/?(?:minimax:[\w-]+|invoke|parameter|think|reasoning)[^>]*>/gi, '')
    .replace(/```[\s\S]*?```/g, '')
  const lines = cleaned.split(/\r?\n/).map((line) => line.trim()).filter(Boolean)
  const bullets = lines.map((line) => /^[-•*]\s*/.test(line) ? `• ${line.replace(/^[-•*]\s*/, '')}` : `• ${line}`)
  return bullets.slice(0, 16).join('\n') || `• ${agentName} لم يرجع تفاصيل قابلة للعرض.`
}

/**
 * الإرجاء المتزايد للمهام المجدولة.
 * لو فشلت المهمة لعدم توفر أي نموذج (كل المزودين في فترة تبريد) لا نعيد المحاولة فوراً:
 * نؤجلها 5 دقائق، ثم 10 دقائق، ثم نثبت على 10 دقائق — حتى تعود النماذج بلا حرق أرصدة.
 */
const BACKOFF_STEPS_MS = [5 * 60_000, 10 * 60_000]
const MAX_BACKOFF_LEVEL = 6

function backoffDelayMs(level: number): number {
  const i = Math.min(Math.max(level, 0), BACKOFF_STEPS_MS.length - 1)
  return BACKOFF_STEPS_MS[i]
}

function backoffLabel(ms: number): string {
  return `${Math.round(ms / 60_000)} دقائق`
}

async function runAgentTask(agentId: string, title: string, description: string | null) {
  const agentKey = lookupAgentKey(agentId)
  if (!agentKey || !AGENT_MAP[agentKey]) throw new Error('معرّف الوكيل غير مدعوم في محرك المهام')
  const agent = AGENT_MAP[agentKey]
  const taskText = [title, description].filter(Boolean).join('\n')
  const prompt = [
    `هذه مهمة مجدولة معتمدة من مالك النظام ومُسندة إليك بصفتك ${agent.name}. نفّذ ما يمكن إنجازه عبر الأدوات المتاحة.`,
    'ممنوع تعديل قاعدة البيانات أو إرسال أي رسالة خارجية. اكتب تقرير إنجاز باللهجة المصرية في نقاط قصيرة، واذكر بوضوح إذا لم تتوفر البيانات.',
    `تفاصيل المهمة:\n${taskText}`,
  ].join('\n\n')
  const system: ChatMsg = { role: 'system', content: buildAgentSystemPrompt(agentKey, prompt, { background: true }) }
  const result = await chatWithFailover(agent.ws, [system, { role: 'user', content: prompt }], {
    maxTokens: 1400,
    tools: POS_DB_TOOLS,
    // مهمة خلفية: تقليم ذكي للسياق — تعليمات + بيانات المهمة فقط، بلا سجل دردشة ولا كتل بيانات محقونة
    background: true,
    toolExecutor: async (name, args) => {
      if (name !== 'query_pos_db') return { ok: false, error: 'الأداة غير مسموحة في العامل الخلفي' }
      return executePosQuery(typeof args.sql === 'string' ? args.sql : '')
    },
  })
  if (!result.ok || !result.text?.trim()) {
    const failure = new Error(`${agent.name} لم يُكمل التقرير بسبب تعذر الاستجابة`) as Error & {
      exhausted?: string
      retryAfterMs?: number
      gatewayReason?: string
    }
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
  return {
    body: reportBullets(result.text.trim(), agent.name),
    agentKey,
    agentName: agent.name,
    trimmed: result.trimmed,
  }
}

export async function POST(req: NextRequest) {
  if (!authorized(req)) return NextResponse.json({ ok: false }, { status: 401 })
  let admin: ReturnType<typeof getSupabaseAdmin>
  try { admin = getSupabaseAdmin() } catch {
    return NextResponse.json({ ok: false, error: 'إعدادات Supabase الخادمية غير مكتملة' }, { status: 503 })
  }

  const now = new Date()
  const { data: candidates, error: readError } = await admin
    .from('agent_tasks')
    .select('id,agent_id,title,description,status,priority,dependency_id,schedule_type,scheduled_time,schedule_day_of_week,schedule_timezone,last_run_at,attempt_count,archived_at,deferred_until,backoff_level')
    .in('schedule_type', ['daily', 'weekly'])
    .in('status', ['pending', 'done'])
    .is('archived_at', null)
    .lt('attempt_count', 3)
    .order('scheduled_time', { ascending: true })
    .limit(100)

  if (readError) return NextResponse.json({ ok: false, error: 'تعذر قراءة قائمة المهام المجدولة' }, { status: 503 })
  // الإرجاء المتزايد: أي مهمة داخل فترة الإرجاء لا تُلمس قبل انتهائها
  const notDeferred = (candidates ?? []).filter(
    (task) => !task.deferred_until || Date.parse(task.deferred_until) <= now.getTime(),
  )
  const deferredCount = (candidates ?? []).length - notDeferred.length
  const dueCandidates = notDeferred.filter((task) => dueToday(task.scheduled_time, task.last_run_at, now, task.schedule_type, task.schedule_day_of_week))
  const dependencyIds = [...new Set(dueCandidates.flatMap((task) => task.dependency_id ? [task.dependency_id] : []))]
  let readyDependencies = new Set<string>()
  if (dependencyIds.length) {
    const { data: prerequisites, error: dependencyError } = await admin.from('agent_tasks')
      .select('id,status,archived_at').in('id', dependencyIds)
    if (dependencyError) return NextResponse.json({ ok: false, error: 'تعذر التحقق من اعتماديات المهام' }, { status: 503 })
    readyDependencies = new Set((prerequisites ?? [])
      .filter((prerequisite) => prerequisite.status === 'done' && !prerequisite.archived_at)
      .map((prerequisite) => prerequisite.id))
  }
  let due: NonNullable<typeof candidates>[number] | undefined
  let waitingForDependency: string | undefined
  for (const task of dueCandidates) {
    if (task.dependency_id && !readyDependencies.has(task.dependency_id)) {
      waitingForDependency ??= task.dependency_id
      continue
    }
    due = task
    break
  }
  if (!due) return NextResponse.json({ ok: true, claimed: null, waiting_for_dependency: waitingForDependency, deferred: deferredCount })

  const { data: claimed, error: claimError } = await admin.from('agent_tasks')
    .update({ status: 'in_progress', updated_at: now.toISOString() })
    .eq('id', due.id).eq('status', due.status).is('archived_at', null)
    .select('id,agent_id,title,description,schedule_type,scheduled_time,last_run_at,attempt_count,backoff_level').maybeSingle()
  if (claimError || !claimed) return NextResponse.json({ ok: true, claimed: null })

  try {
    const result = await runAgentTask(claimed.agent_id, claimed.title, claimed.description)
    const body = result.body
    const finishedAt = new Date()
    const cairo = cairoParts(finishedAt)
    const report = {
      agent_id: claimed.agent_id, kind: 'report', title: `إنجاز يومي — ${result.agentName}: ${claimed.title}`,
      body, severity: 'منخفض', status: 'approved', decided_by: 'system',
      decided_at: finishedAt.toISOString(),
      op_id: `scheduled:${claimed.id}:${cairo.year}-${cairo.month}-${cairo.day}`,
      payload: {
        task_id: claimed.id, category: claimed.agent_id,
        actions: [
          { type: 'navigate', label: `فتح غرفة ${result.agentName}`, href: `/agent/${result.agentKey}` },
          { type: 'copy', label: 'نسخ التقرير' },
        ],
      },
    }
    const { error: reportError } = await admin.from('agent_updates').upsert(report, { onConflict: 'op_id', ignoreDuplicates: true })
    if (reportError) throw new Error('تعذر حفظ تقرير الإنجاز')
    const { error: finishError } = await admin.from('agent_tasks').update({
      status: 'done', result_note: body.slice(0, 4000), last_run_at: finishedAt.toISOString(),
      // نجاح: تصفير الإرجاء والمحاولات — دورة جديدة نظيفة
      attempt_count: 0, backoff_level: 0, deferred_until: null, last_failure_reason: null,
      updated_at: finishedAt.toISOString(),
    }).eq('id', claimed.id).eq('status', 'in_progress')
    if (finishError) throw new Error('تعذر تثبيت اكتمال المهمة')
    console.log(
      `[Worker] مهمة ${claimed.id} اكتملت — تقليم السياق: ${result.trimmed ? `${result.trimmed.dropped} رسالة محذوفة / ${result.trimmed.savedChars} حرف موفَّر` : 'غير مطلوب'}`,
    )
    return NextResponse.json({
      ok: true, claimed: claimed.id, completed: true,
      trimmed: result.trimmed ?? null,
    })
  } catch (error) {
    const message = error instanceof Error ? error.message : 'تعذر تنفيذ المهمة'
    const exhausted = (error as { exhausted?: string }).exhausted
    const retryAfterMs = (error as { retryAfterMs?: number }).retryAfterMs
    const attempts = Number(claimed.attempt_count || 0) + 1
    const level = Number(claimed.backoff_level || 0)

    // نفاد النماذج (كل المزودين في فترة تبريد/قاطع): إرجاء متزايد بدل إعادة محاولة فورية.
    // لا نزيد attempt_count هنا — العطل ليس في المهمة، بل في توفر النماذج،
    // فلا نحرق محاولات المهمة وهي تنتظر عودة المزودين.
    if (exhausted === 'all_cooling' || exhausted === 'all_failed') {
      const waitMs = Math.max(backoffDelayMs(level), Math.min(retryAfterMs ?? 0, 10 * 60_000))
      const deferredUntil = new Date(Date.now() + waitMs).toISOString()
      await admin.from('agent_tasks').update({
        status: 'pending',
        backoff_level: Math.min(level + 1, MAX_BACKOFF_LEVEL),
        deferred_until: deferredUntil,
        last_failure_reason: `لا نموذج متاح (قاطع الدائرة) — إرجاء ${backoffLabel(waitMs)}`,
        result_note: `مؤجلة — ${message} :: ${(error as { gatewayReason?: string }).gatewayReason ?? ''}`.slice(0, 500),
        updated_at: new Date().toISOString(),
      }).eq('id', claimed.id).eq('status', 'in_progress')
      console.warn(`[Worker] إرجاء مهمة ${claimed.id} لمدة ${backoffLabel(waitMs)} (المستوى ${level + 1})`)
      return NextResponse.json({
        ok: false, claimed: claimed.id, deferred_ms: waitMs, deferred_until: deferredUntil,
        backoff_level: level + 1, error: message,
      }, { status: 202 })
    }

    // فشل آخر: يبقى محاولة عادية بلا إرجاء طويل
    await admin.from('agent_tasks').update({
      status: 'pending', attempt_count: attempts,
      last_failure_reason: message.slice(0, 200),
      result_note: message.slice(0, 500),
      updated_at: new Date().toISOString(),
    }).eq('id', claimed.id).eq('status', 'in_progress')
    return NextResponse.json({ ok: false, claimed: claimed.id, error: message }, { status: 502 })
  }
}
