// lib/agent-task-supervisor.ts — المشرف العام (مروة) داخل محرك المهام
// ⚠️ التعيين برمجي: مروة هي المشرفة العامة، ولا تُطلب موافقة بشرية على أي قرار.
// مهامها الآلية:
//  1. مسح دوري للمهام المتعطلة والمتأخرة بلا قرار → إلغاء / أرشفة / إعادة توجيه.
//  2. التحقق من الاعتماديات قبل السماح للوكيل التالي بالبدء، وفكّ الأقفال الميتة.
// كل قرار يُوثَّق في agent_updates بسجل تدقيق كامل (لا حذف).

import type { SupabaseClient } from '@supabase/supabase-js'
import { AGENT_MAP, enqueueInboxTask } from '@/lib/agent-intelligence'
import { cairoDay } from '@/lib/agent-task-runner'

/** المشرف العام مُعيَّن برمجياً — مروة المايسترو */
export const SUPERVISOR_AGENT_ID = 'marwa'

export type SupervisorTask = {
  id: string
  agent_id: string
  title: string
  status: string
  dependency_id: string | null
  schedule_type: string | null
  archived_at: string | null
  attempt_count: number | null
  created_at: string
  updated_at: string
  last_run_at: string | null
  deferred_until: string | null
}

export type SupervisorDecision = {
  taskId: string
  agentId: string
  agentName: string
  title: string
  action: 'archive' | 'cancel' | 'redirect' | 'resume' | 'remind'
  reason: string
}

export type SweepReport = {
  ok: boolean
  day: string
  scanned: number
  decisions: SupervisorDecision[]
  reportId: string | null
  error?: string
}

const HOUR = 3_600_000
/** مهمة «معلّقة» بلاش حركة أطول من كذا = محتاجة تذكير الوكيل (إعادة توجيه) */
const REMIND_HOURS = Number(process.env.SUPERVISOR_REMIND_HOURS || 48)
/** مهمة «معلّقة» أطول من كذا بلا أي حركة = متعطلة فعلاً وتُلغى */
const STALE_HOURS = Number(process.env.SUPERVISOR_STALE_HOURS || 168)
/** مهمة «جارية» لم تتحدث أطول من كذا = عالقة ومصنعها توقف */
const STUCK_HOURS = Number(process.env.SUPERVISOR_STUCK_HOURS || 24)
/** مهمة مجدولة لم تعمل أطول من كذا يوم = ميتة */
const DEAD_SCHEDULE_DAYS = Number(process.env.SUPERVISOR_DEAD_SCHEDULE_DAYS || 3)

function ageHours(iso: string | null, now: number): number {
  if (!iso) return Number.POSITIVE_INFINITY
  const t = Date.parse(iso)
  if (Number.isNaN(t)) return Number.POSITIVE_INFINITY
  return (now - t) / HOUR
}

function agentName(agentId: string): string {
  return AGENT_MAP[agentId as keyof typeof AGENT_MAP]?.name || agentId
}

/**
 * المسح اليومي للمشرف العام.
 * deterministic بالكامل — لا يستهلك أي نموذج، فيعمل حتى لو كل المزودين في فترة تبريد.
 */
export async function runSupervisorSweep(admin: SupabaseClient): Promise<SweepReport> {
  const now = Date.now()
  const day = cairoDay(new Date(now))
  const decisions: SupervisorDecision[] = []

  const { data: rows, error } = await admin
    .from('agent_tasks')
    .select('id,agent_id,title,status,dependency_id,schedule_type,archived_at,attempt_count,created_at,updated_at,last_run_at,deferred_until')
    .is('archived_at', null)
    .in('status', ['pending', 'in_progress'])
    .order('updated_at', { ascending: true })
    .limit(300)

  if (error) return { ok: false, day, scanned: 0, decisions, reportId: null, error: error.message }

  const tasks = (rows ?? []) as SupervisorTask[]
  if (!tasks.length) {
    return { ok: true, day, scanned: 0, decisions, reportId: null }
  }

  // اعتماديات: نحتاج حالة كل مهمة يُعتمد عليها لاتخاذ قرار الفك أو المنع
  const dependencyIds = [...new Set(tasks.flatMap((t) => (t.dependency_id ? [t.dependency_id] : [])))]
  const depState = new Map<string, { status: string; archived_at: string | null }>()
  if (dependencyIds.length) {
    const { data: deps } = await admin
      .from('agent_tasks')
      .select('id,status,archived_at')
      .in('id', dependencyIds)
    for (const dep of deps ?? []) {
      depState.set(dep.id, { status: dep.status, archived_at: dep.archived_at ?? null })
    }
  }

  for (const task of tasks) {
    const name = agentName(task.agent_id)
    const idleHours = ageHours(task.updated_at, now)

    // (أ) اعتمادية ميتة (مرفوضة أو مؤرشفة أو محذوفة): فكّ القفل وإعادة توجيه المهمة للوكيل
    if (task.dependency_id) {
      const dep = depState.get(task.dependency_id)
      const dead = !dep || !!dep.archived_at || dep.status === 'rejected'
      if (dead) {
        const { error: fixError } = await admin.from('agent_tasks').update({
          dependency_id: null,
          result_note: `المشرف العام فكّ الاعتمادية الميتة ${task.dependency_id.slice(0, 8)} — المهمة صارت جاهزة للتنفيذ.`,
          updated_at: new Date().toISOString(),
        }).eq('id', task.id)
        if (!fixError) {
          decisions.push({
            taskId: task.id, agentId: task.agent_id, agentName: name, title: task.title,
            action: 'redirect',
            reason: dep ? 'الاعتمادية مرفوضة/مؤرشفة ففككت القفل وأعدت التوجيه' : 'الاعتمادية غير موجودة ففككت القفل',
          })
          task.dependency_id = null
        }
        continue
      }
    }

    // (ب) مهمة جارية عالقة: المصنع توقف عنها — نرجعها للطابور بدل تجميدها للأبد
    if (task.status === 'in_progress' && idleHours >= STUCK_HOURS) {
      const { error: resumeError } = await admin.from('agent_tasks').update({
        status: 'pending',
        result_note: `المشرف العام أعاد المهمة للطابور بعد ${Math.round(idleHours)} ساعة بلا حركة.`,
        updated_at: new Date().toISOString(),
      }).eq('id', task.id).eq('status', 'in_progress')
      if (!resumeError) {
        decisions.push({
          taskId: task.id, agentId: task.agent_id, agentName: name, title: task.title,
          action: 'resume',
          reason: `عالقة ${Math.round(idleHours)} ساعة في التنفيذ بلا تحديث`,
        })
      }
      continue
    }

    // (ج) مهمة مجدولة ميتة: تجاوزت محاولاتها ولم تعمل من أيام → أرشفة
    if (task.schedule_type && task.schedule_type !== 'none') {
      const lastTouch = task.last_run_at || task.created_at
      const deadDays = ageHours(lastTouch, now) / 24
      const burned = Number(task.attempt_count || 0) >= 3
      if (deadDays >= DEAD_SCHEDULE_DAYS && burned) {
        const { error: archiveError } = await admin.from('agent_tasks').update({
          archived_at: new Date().toISOString(),
          result_note: `المشرف العام أرشف المهمة المجدولة بعد ${Math.round(deadDays)} يوم بلا تنفيذ ناجح و${task.attempt_count} محاولات فاشلة.`,
          updated_at: new Date().toISOString(),
        }).eq('id', task.id)
        if (!archiveError) {
          decisions.push({
            taskId: task.id, agentId: task.agent_id, agentName: name, title: task.title,
            action: 'archive',
            reason: `جدولة ميتة ${Math.round(deadDays)} يوم و${task.attempt_count} محاولة فاشلة`,
          })
        }
        continue
      }
    }

    // (د) مهمة معلّقة مهملة بلا اعتمادية: سلّم تدريجي —
    //     أولاً تذكير الوكيل وإعادة توجيهها له (خطر منخفض جداً)،
    //     ثم إلغاء صريح (انتقال حالة وأرشفة، بلا حذف) لو ما ردّش.
    if (task.status === 'pending' && !task.dependency_id) {
      // التذكير: يشتغل مرة كل فترة سماح، ويُسجَّل في صندوق الوكيل كي يراه فعلاً
      if (idleHours >= REMIND_HOURS && idleHours < STALE_HOURS) {
        const reminded = task.agent_id in AGENT_MAP
          ? enqueueInboxTask({
              from: SUPERVISOR_AGENT_ID,
              to: task.agent_id as keyof typeof AGENT_MAP,
              type: 'task',
              body: `تذكير من المشرف العام: المهمة «${task.title}» معلّقة ${Math.round(idleHours / 24)} يوم بلا تنفيذ. ابدأ فيها أو ارجع بمانع واضح.`,
            })
          : { ok: false, error: 'وكيل غير مسجّل في صندوق الوارد المحلي' }
        const { error: remindError } = await admin.from('agent_tasks').update({
          result_note: `المشرف العام ذكّر ${name} بالمهمة — معلّقة ${Math.round(idleHours / 24)} يوم بلا تنفيذ.`,
          updated_at: new Date().toISOString(),
        }).eq('id', task.id).eq('status', 'pending')
        if (!remindError) {
          decisions.push({
            taskId: task.id, agentId: task.agent_id, agentName: name, title: task.title,
            action: 'remind',
            reason: `معلّقة ${Math.round(idleHours / 24)} يوم — ${reminded.ok ? 'تذكير أُرسل لصندوق الوكيل' : 'تعذر إرسال التذكير المحلي'}`,
          })
        }
        continue
      }

      // الإلغاء: فقط للمهمة الميتة فعلاً (تجاوزت حد الإهمال الطويل)
      if (idleHours >= STALE_HOURS) {
        const { error: cancelError } = await admin.from('agent_tasks').update({
          status: 'rejected',
          archived_at: new Date().toISOString(),
          result_note: `المشرف العام ألغى المهمة بعد ${Math.round(idleHours / 24)} يوم بلا قرار ولا تنفيذ — تُحفظ في الأرشيف لا تُحذف.`,
          updated_at: new Date().toISOString(),
        }).eq('id', task.id).eq('status', 'pending')
        if (!cancelError) {
          decisions.push({
            taskId: task.id, agentId: task.agent_id, agentName: name, title: task.title,
            action: 'cancel',
            reason: `معلّقة ${Math.round(idleHours / 24)} يوم بلا قرار بشري ولا اعتمادية`,
          })
        }
      }
    }
  }

  // تقرير المشرف العام: سجل تدقيق يومي واحد (idempotent بنفس op_id)
  const body = decisions.length
    ? decisions.map((d) => {
        const verb = d.action === 'cancel' ? 'ألغيت' : d.action === 'archive' ? 'أرشفت' : d.action === 'resume' ? 'أعدت للطابور' : d.action === 'remind' ? 'ذكّرت' : 'أعدت توجيه'
        return `• ${verb} مهمة «${d.title}» لـ${d.agentName} — ${d.reason}`
      }).join('\n')
    : '• لا مهام متعطلة ولا معلّقة ولا اعتماديات ميتة — المنظومة انسيابية.'

  const { data: reportRow, error: reportError } = await admin.from('agent_updates').upsert({
    agent_id: SUPERVISOR_AGENT_ID,
    kind: 'report',
    title: `قرارات المشرف العام — ${day} (${decisions.length} قرار)`,
    body,
    severity: decisions.some((d) => d.action === 'cancel') ? 'متوسط' : 'منخفض',
    status: 'approved',
    decided_by: 'marwa',
    decided_at: new Date().toISOString(),
    op_id: `supervisor:${day}`,
    payload: {
      scanned: tasks.length,
      decisions: decisions.map((d) => ({ task_id: d.taskId, agent: d.agentId, action: d.action, reason: d.reason })),
      actions: [{ type: 'navigate', label: 'فتح غرفة مروة', href: '/agent/marwa' }],
    },
  }, { onConflict: 'op_id' }).select('id').maybeSingle()

  return {
    ok: true,
    day,
    scanned: tasks.length,
    decisions,
    reportId: reportRow?.id ?? null,
    error: reportError?.message,
  }
}

/**
 * بوابة الاعتماديات الخادمية: هل يُسمح لهذا الوكيل بالبدء الآن؟
 * العامل والواجهة كلاهما يمرّان من هنا — لا اعتماد للحكم على المتصفح.
 */
export async function checkDependencies(
  admin: SupabaseClient,
  taskId: string,
): Promise<{ allowed: boolean; blockedBy: string | null; reason: string | null }> {
  const { data: task } = await admin
    .from('agent_tasks')
    .select('id,dependency_id')
    .eq('id', taskId)
    .maybeSingle()
  if (!task?.dependency_id) return { allowed: true, blockedBy: null, reason: null }

  const { data: dep } = await admin
    .from('agent_tasks')
    .select('id,title,status,archived_at')
    .eq('id', task.dependency_id)
    .maybeSingle()

  if (!dep) return { allowed: false, blockedBy: task.dependency_id, reason: 'الاعتمادية غير موجودة — يحتاج المشرف العام لفكّ القفل.' }
  if (dep.archived_at || dep.status === 'rejected') {
    return { allowed: false, blockedBy: dep.id, reason: `الاعتمادية «${dep.title}» ملغاة أو مؤرشفة — يحتاج المشرف العام لفكّ القفل.` }
  }
  if (dep.status !== 'done') {
    return { allowed: false, blockedBy: dep.id, reason: `المهمة مقفولة لحد ما «${dep.title}» تكتمل.` }
  }
  return { allowed: true, blockedBy: null, reason: null }
}
