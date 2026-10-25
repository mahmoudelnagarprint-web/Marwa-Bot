import { timingSafeEqual } from 'node:crypto'
import { NextRequest, NextResponse } from 'next/server'
import {
  cairoDay,
  cairoParts,
  persistTaskCompletion,
  runAgentTask,
  type RunFailure,
} from '@/lib/agent-task-runner'
import { releaseOrphanedTasks, runSupervisorSweep } from '@/lib/agent-task-supervisor'
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

/**
 * هل المهمة دورية «كل 48 ساعة»؟ الترميز: وجود وسم «[كل 48 ساعة]» في العنوان.
 * يستهدف مهمة الصيانة الدورية لصاصا تحديداً، فلا يؤثر على المهام اليومية/الأسبوعية الأخرى.
 */
function isEvery48h(title: string | null): boolean {
  return !!title && /\[كل\s*48\s*ساعة\]/i.test(title)
}

/**
 * استحقاق المهام الدورية. يدعم:
 *  - يجب أن يكون الوقت الحالي ≥ موعد المهمة (scheduled_time) في يوم القاهرة.
 *  - weekly: يوم محدد من الأسبوع.
 *  - كل 48 ساعة (وسم [كل 48 ساعة]): مستحقة حين يمضي ≥ 48 ساعة منذ last_run_at —
 *    أو إذا لم تُنفَّذ قط (last_run_at فارغ) وكان الوقت قد تعدّى موعدها. يُحتسب بالوقت الفعلي
 *    (Africa/Cairo) لا بعدد أيام، ولا يعاود في نفس اليوم بعد التنفيذ.
 */
function dueToday(
  time: string | null,
  lastRunAt: string | null,
  now: Date,
  scheduleType: string,
  scheduleDay: number | null,
  title: string | null,
): boolean {
  if (!time) return false
  const today = cairoParts(now)
  const lastDate = lastRunAt ? cairoParts(new Date(lastRunAt)) : null
  if (scheduleType === 'weekly') {
    const dayName = new Intl.DateTimeFormat('en-US', { timeZone: 'Africa/Cairo', weekday: 'short' }).format(now)
    const dayNumber = ({ Sun: 0, Mon: 1, Tue: 2, Wed: 3, Thu: 4, Fri: 5, Sat: 6 } as Record<string, number>)[dayName]
    if (scheduleDay === null || scheduleDay !== dayNumber) return false
  }
  const target = time.slice(0, 5)
  const pastTime = `${today.hour}:${today.minute}` >= target

  // كل 48 ساعة: مبني على انقضاء الوقت الفعلي منذ آخر تشغيل.
  if (isEvery48h(title)) {
    if (!pastTime) return false
    if (!lastRunAt) return true // لم تُنفَّذ قط بعد تعدّي موعدها → تُلتقط الآن
    const elapsedMs = now.getTime() - new Date(lastRunAt).getTime()
    return elapsedMs >= 48 * 60 * 60 * 1000
  }

  return pastTime &&
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

  // ═══ 1) تحرير المهام العالقة — أول خطوة في كل نبضة، قبل أي قراءة للطابور ═══
  // المهمة اللي عاملها مات ترجع 'pending' هنا فوراً (حد 15 دقيقة)، فتُلتقط في نفس
  // النبضة بالأسفل بدل أن تبقى «جارية» للأبد. deterministic بالكامل — بلا استهلاك نموذج.
  let orphans: { released: number; poisoned: number; scanned: number } = { released: 0, poisoned: 0, scanned: 0 }
  try {
    const report = await releaseOrphanedTasks(admin)
    orphans = { released: report.released.length, poisoned: report.poisoned.length, scanned: report.scanned }
    if (orphans.released || orphans.poisoned) {
      console.log(`[Worker] تحرير مهام عالقة: ${orphans.released} رجعت للطابور، ${orphans.poisoned} أُرشفت`)
    }
  } catch {
    // فشل التحرير لا يوقف النبضة — يُعاد في النبضة التالية
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
  // ═══ 2) قراءة الطابور: مهام الإسناد السريع (schedule_type='none') + المهام المجدولة ═══
  // سابقاً كان الاستعلام محصوراً في daily/weekly فقط، فمهام أزرار الوكلاء (none) كانت
  // تُحفظ 'pending' ولا يلتقطها أحد أبداً. الآن الطابوران يُقرآن معاً في نبضة واحدة.
  const CANDIDATE_COLUMNS = 'id,agent_id,title,description,status,priority,dependency_id,schedule_type,scheduled_time,schedule_day_of_week,schedule_timezone,last_run_at,attempt_count,archived_at,deferred_until,backoff_level,created_at'

  const { data: adhocRows, error: adhocError } = await admin
    .from('agent_tasks')
    .select(CANDIDATE_COLUMNS)
    .eq('schedule_type', 'none')
    .eq('status', 'pending')
    .is('archived_at', null)
    .lt('attempt_count', 3)
    .order('created_at', { ascending: true })   // الأقدم أولاً — لا تجويع للمهام القديمة
    .limit(50)

  if (adhocError) return NextResponse.json({ ok: false, error: 'تعذر قراءة طابور الإسناد السريع' }, { status: 503 })

  const { data: scheduledRows, error: readError } = await admin
    .from('agent_tasks')
    .select(CANDIDATE_COLUMNS)
    .in('schedule_type', ['daily', 'weekly'])
    .in('status', ['pending', 'done'])
    .is('archived_at', null)
    .lt('attempt_count', 3)
    .order('scheduled_time', { ascending: true })
    .limit(100)

  if (readError) return NextResponse.json({ ok: false, error: 'تعذر قراءة قائمة المهام المجدولة' }, { status: 503 })

  const candidates = [...(adhocRows ?? []), ...(scheduledRows ?? [])]
  // الإرجاء المتزايد: أي مهمة داخل فترة الإرجاء لا تُلمس قبل انتهائها
  const notDeferred = candidates.filter(
    (task) => !task.deferred_until || Date.parse(task.deferred_until) <= now.getTime(),
  )
  const deferredCount = candidates.length - notDeferred.length
  // الإسناد السريع مستحق دائماً؛ المجدول يُفحص بموعده فقط
  const dueCandidates = notDeferred.filter((task) => task.schedule_type === 'none'
    || dueToday(task.scheduled_time, task.last_run_at, now, task.schedule_type, task.schedule_day_of_week, task.title))
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
    blocked_dependencies: [...blockedDependencies], supervisor, orphans,
  })

  // الحجز يُثبت هوية الحاجز ولحظته (claimed_by/claimed_at) — بهما يعرف المُحرِّر
  // مَن كان يملك المهمة ومتى بدأ الحجز، فيتحرر من مالك ميت لا من عامل شغّال.
  const { data: claimed, error: claimError } = await admin.from('agent_tasks')
    .update({
      status: 'in_progress',
      claimed_by: 'worker',
      claimed_at: now.toISOString(),
      updated_at: now.toISOString(),
    })
    .eq('id', due.id).eq('status', due.status).is('archived_at', null)
    .select('id,agent_id,title,description,schedule_type,scheduled_time,last_run_at,attempt_count,backoff_level').maybeSingle()
  if (claimError || !claimed) return NextResponse.json({ ok: true, claimed: null, supervisor, orphans })

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
      trimmed: result.trimmed ?? null, supervisor, orphans,
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
        claimed_by: null,        // الحجز انتهى — المهمة رجعت للطابور بلا مالك
        claimed_at: null,
        backoff_level: Math.min(level + 1, MAX_BACKOFF_LEVEL),
        deferred_until: deferredUntil,
        last_failure_reason: `لا نموذج متاح (قاطع الدائرة) — إرجاء ${backoffLabel(waitMs)}`,
        result_note: `مؤجلة — ${message} :: ${failure.gatewayReason ?? ''}`.slice(0, 500),
        updated_at: new Date().toISOString(),
      }).eq('id', claimed.id).eq('status', 'in_progress')
      console.warn(`[Worker] إرجاء مهمة ${claimed.id} لمدة ${backoffLabel(waitMs)} (المستوى ${level + 1})`)
      return NextResponse.json({
        ok: false, claimed: claimed.id, deferred_ms: waitMs, deferred_until: deferredUntil,
        backoff_level: level + 1, error: message, orphans,
      }, { status: 202 })
    }

    // فشل آخر: يبقى محاولة عادية بلا إرجاء طويل
    await admin.from('agent_tasks').update({
      status: 'pending', attempt_count: attempts,
      claimed_by: null,
      claimed_at: null,
      last_failure_reason: message.slice(0, 200),
      result_note: message.slice(0, 500),
      updated_at: new Date().toISOString(),
    }).eq('id', claimed.id).eq('status', 'in_progress')
    return NextResponse.json({ ok: false, claimed: claimed.id, error: message, orphans }, { status: 502 })
  }
}
