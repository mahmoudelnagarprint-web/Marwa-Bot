import { timingSafeEqual } from 'node:crypto'
import { NextRequest, NextResponse } from 'next/server'
import {
  cairoDay,
  cairoParts,
  persistTaskCompletion,
  runAgentTask,
  type RunFailure,
} from '@/lib/agent-task-runner'
import { runSupervisorSweep } from '@/lib/agent-task-supervisor'
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

/** هل نفّذ المشرف العام مسح اليوم؟ */
async function alreadySweptToday(admin: ReturnType<typeof getSupabaseAdmin>): Promise<boolean> {
  const { data } = await admin
    .from('agent_updates')
    .select('id')
    .eq('op_id', `supervisor:${cairoDay()}`)
    .maybeSingle()
  return !!data?.id
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

export async function POST(req: NextRequest) {
  if (!authorized(req)) return NextResponse.json({ ok: false }, { status: 401 })
  let admin: ReturnType<typeof getSupabaseAdmin>
  try { admin = getSupabaseAdmin() } catch {
    return NextResponse.json({ ok: false, error: 'إعدادات Supabase الخادمية غير مكتملة' }, { status: 503 })
  }

  // المشرف العام (مروة) يعمل مع كل نبضة عامل: مرة واحدة يومياً، وقراراته deterministic
  // فلا تستهلك أي نموذج وتصلح حتى لو كل المزودين في فترة تبريد.
  let supervisor: { ran: boolean; decisions: number; day: string } = { ran: false, decisions: 0, day: cairoDay() }
  try {
    const swept = await alreadySweptToday(admin)
    if (!swept) {
      const report = await runSupervisorSweep(admin)
      supervisor = { ran: true, decisions: report.decisions.length, day: report.day }
      if (report.decisions.length) {
        console.log(`[Supervisor] مروة اتخذت ${report.decisions.length} قرار في مسح ${report.day}`)
      }
    }
  } catch {
    // فشل المشرف لا يوقف تنفيذ المهام — يُسجل فقط
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
  let blockedDependencies = new Set<string>()
  if (dependencyIds.length) {
    const { data: prerequisites, error: dependencyError } = await admin.from('agent_tasks')
      .select('id,status,archived_at').in('id', dependencyIds)
    if (dependencyError) return NextResponse.json({ ok: false, error: 'تعذر التحقق من اعتماديات المهام' }, { status: 503 })
    readyDependencies = new Set((prerequisites ?? [])
      .filter((prerequisite) => prerequisite.status === 'done' && !prerequisite.archived_at)
      .map((prerequisite) => prerequisite.id))
    // اعتمادية مرفوضة/مؤرشفة = قفل دائم؛ المشرف العام هو من يفكّه وليس العامل
    blockedDependencies = new Set((prerequisites ?? [])
      .filter((prerequisite) => prerequisite.archived_at || prerequisite.status === 'rejected')
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
  if (!due) return NextResponse.json({
    ok: true, claimed: null, waiting_for_dependency: waitingForDependency, deferred: deferredCount,
    blocked_dependencies: [...blockedDependencies], supervisor,
  })

  const { data: claimed, error: claimError } = await admin.from('agent_tasks')
    .update({ status: 'in_progress', updated_at: now.toISOString() })
    .eq('id', due.id).eq('status', due.status).is('archived_at', null)
    .select('id,agent_id,title,description,schedule_type,scheduled_time,last_run_at,attempt_count,backoff_level').maybeSingle()
  if (claimError || !claimed) return NextResponse.json({ ok: true, claimed: null, supervisor })

  try {
    // التنفيذ الحقيقي: استدعاء نموذج الوكيل نفسه — لا تقرير جاهز ولا إغلاق صوري
    const result = await runAgentTask(claimed.agent_id, claimed.title, claimed.description)
    const { reportError, finishError } = await persistTaskCompletion(admin, claimed, result, 'scheduled')
    if (reportError) throw new Error(`تعذر حفظ تقرير الإنجاز: ${reportError}`)
    if (finishError) throw new Error(`تعذر تثبيت اكتمال المهمة: ${finishError}`)
    console.log(
      `[Worker] مهمة ${claimed.id} اكتملت بتنفيذ حقيقي عبر ${result.provider} — ${result.latencyMs}ms — تقليم السياق: ${result.trimmed ? `${result.trimmed.dropped} رسالة محذوفة / ${result.trimmed.savedChars} حرف موفَّر` : 'غير مطلوب'}`,
    )
    return NextResponse.json({
      ok: true, claimed: claimed.id, completed: true,
      agent: result.agentName, provider: result.provider, latency_ms: result.latencyMs,
      trimmed: result.trimmed ?? null, supervisor,
    })
  } catch (error) {
    const failure = error as RunFailure
    const message = failure.message || 'تعذر تنفيذ المهمة'
    const attempts = Number(claimed.attempt_count || 0) + 1
    const level = Number(claimed.backoff_level || 0)

    // نفاد النماذج (كل المزودين في فترة تبريد/قاطع): إرجاء متزايد بدل إعادة محاولة فورية.
    // لا نزيد attempt_count هنا — العطل ليس في المهمة، بل في توفر النماذج،
    // فلا نحرق محاولات المهمة وهي تنتظر عودة المزودين.
    if (failure.exhausted === 'all_cooling' || failure.exhausted === 'all_failed') {
      const waitMs = Math.max(backoffDelayMs(level), Math.min(failure.retryAfterMs ?? 0, 10 * 60_000))
      const deferredUntil = new Date(Date.now() + waitMs).toISOString()
      await admin.from('agent_tasks').update({
        status: 'pending',
        backoff_level: Math.min(level + 1, MAX_BACKOFF_LEVEL),
        deferred_until: deferredUntil,
        last_failure_reason: `لا نموذج متاح (قاطع الدائرة) — إرجاء ${backoffLabel(waitMs)}`,
        result_note: `مؤجلة — ${message} :: ${failure.gatewayReason ?? ''}`.slice(0, 500),
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
