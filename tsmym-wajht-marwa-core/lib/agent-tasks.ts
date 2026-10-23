// lib/agent-tasks.ts — الوصول الحي لجداول راصد السحابية (MARWA CORE)
// المخطط الرسمي: cloud/migrations/006_agent_workspace.sql
// anon يملك select/insert/update — لا حذف نهائياً (حظر الحذف الإلزامي Audit Trail).
//   agent_tasks(id, agent_id, title, description, status, priority, source,
//               created_by, result_note, op_id, created_at, updated_at)
//   agent_updates(id, agent_id, kind, title, body, severity, status,
//                 decided_by, decided_at, payload, op_id, created_at)

import type { SupabaseClient } from '@supabase/supabase-js'

export type AgentTask = {
  id: string
  agent_id: string
  title: string
  description: string | null
  status: 'pending' | 'in_progress' | 'done' | 'rejected' | string
  priority: 'low' | 'normal' | 'high' | 'urgent'
  source: string
  created_by: string
  result_note: string | null
  created_at: string
  updated_at: string
  dependency_id?: string | null
  archived_at?: string | null
  schedule_type?: 'none' | 'daily' | 'weekly' | string
  scheduled_time?: string | null
  schedule_day_of_week?: number | null
  schedule_timezone?: string
  last_run_at?: string | null
  attempt_count?: number
}

export type AgentUpdate = {
  id: string
  agent_id: string
  kind: 'suggestion' | 'complaint' | 'alert' | 'report' | string
  title: string
  body: string | null
  severity: 'عالي' | 'متوسط' | 'منخفض' | null
  status: 'pending' | 'approved' | 'rejected' | string
  decided_by: string | null
  created_at: string
  payload?: { task_id?: string; category?: string; actions?: { type: string; label: string; href?: string }[] } | null
}

export type SupabaseError = { message: string; code?: string }

export function isTableMissingErr(err: SupabaseError): boolean {
  const m = `${err.message} ${err.code ?? ''}`
  return (
    m.includes('42P01') ||
    m.includes('does not exist') ||
    m.includes('schema cache') ||
    m.includes('Could not find the table')
  )
}

/** عرض التوقيت بدقة بتوقيت القاهرة بصيغة hh:mm DD/MM */
export function formatCairoDate(iso?: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  try {
    const parts = new Intl.DateTimeFormat('en-GB', {
      timeZone: 'Africa/Cairo',
      hour: '2-digit',
      minute: '2-digit',
      day: '2-digit',
      month: '2-digit',
      hour12: false,
    }).formatToParts(d)
    const p = Object.fromEntries(parts.map((x) => [x.type, x.value]))
    return `${p.hour}:${p.minute} ${p.day}/${p.month}`
  } catch {
    return d.toLocaleTimeString('ar-EG', { hour: '2-digit', minute: '2-digit' })
  }
}

export async function fetchAgentTasks(
  client: SupabaseClient,
  agentId?: string,
): Promise<{ tasks: AgentTask[]; error: SupabaseError | null }> {
  let query = client
    .from('agent_tasks')
    .select('*')
    .order('created_at', { ascending: false })
    .limit(100)

  if (agentId) {
    query = query.eq('agent_id', agentId)
  }

  const { data, error } = await query
  if (error) return { tasks: [], error }
  return { tasks: ((data ?? []) as AgentTask[]).filter((task) => !task.archived_at), error: null }
}

/** إضافة مهمة من الواجهة — INSERT حقيقي في agent_tasks */
export async function insertAgentTask(
  client: SupabaseClient,
  payload: {
    agent_id: string
    title: string
    description?: string
    priority?: 'low' | 'normal' | 'high' | 'urgent'
    dependency_id?: string | null
    schedule_type?: 'none' | 'daily' | 'weekly'
    scheduled_time?: string | null
    schedule_day_of_week?: number | null
  },
): Promise<{ ok: boolean; error: SupabaseError | null; row?: AgentTask }> {
  const row = {
    agent_id: payload.agent_id,
    title: payload.title.trim(),
    description: payload.description?.trim() || null,
    status: 'pending',
    priority: payload.priority || 'normal',
    source: 'ui' as const,
    dependency_id: payload.dependency_id || null,
    schedule_type: payload.schedule_type || 'none',
    scheduled_time: payload.schedule_type === 'daily' || payload.schedule_type === 'weekly' ? payload.scheduled_time || null : null,
    schedule_day_of_week: payload.schedule_type === 'weekly' ? payload.schedule_day_of_week ?? null : null,
    schedule_timezone: 'Africa/Cairo',
  }
  let { data, error } = await client.from('agent_tasks').insert(row).select().limit(1)
  const migrationMissing = error?.message?.includes('schedule_type') || error?.message?.includes('dependency_id') || error?.message?.includes('schedule_day_of_week')
  if (error && migrationMissing && !payload.dependency_id && payload.schedule_type === 'none') {
    const legacyRow = { ...row }
    delete (legacyRow as Partial<typeof legacyRow>).dependency_id
    delete (legacyRow as Partial<typeof legacyRow>).schedule_type
    delete (legacyRow as Partial<typeof legacyRow>).scheduled_time
    delete (legacyRow as Partial<typeof legacyRow>).schedule_timezone
    delete (legacyRow as Partial<typeof legacyRow>).schedule_day_of_week
    const fallback = await client.from('agent_tasks').insert(legacyRow).select().limit(1)
    data = fallback.data
    error = fallback.error
  }
  if (error) return { ok: false, error }
  return { ok: true, error: null, row: data?.[0] as AgentTask }
}

/** تغيير حالة المهمة — حظر الحذف الإلزامي (Audit Trail) */
export async function updateAgentTaskStatus(
  client: SupabaseClient,
  taskId: string,
  newStatus: 'pending' | 'in_progress' | 'done' | 'rejected',
): Promise<{ ok: boolean; error: SupabaseError | null }> {
  const patch: Record<string, unknown> = { status: newStatus, updated_at: new Date().toISOString() }
  if (newStatus === 'pending') patch.attempt_count = 0
  let { error } = await client.from('agent_tasks').update(patch).eq('id', taskId)
  if (error?.message?.includes('attempt_count')) {
    const fallback = await client.from('agent_tasks')
      .update({ status: newStatus, updated_at: patch.updated_at })
      .eq('id', taskId)
    error = fallback.error
  }
  if (error) return { ok: false, error }
  return { ok: true, error: null }
}

export async function insertTaskCompletionReport(
  client: SupabaseClient,
  task: Pick<AgentTask, 'id' | 'agent_id' | 'title' | 'result_note'>,
): Promise<{ ok: boolean; error: SupabaseError | null }> {
  const now = new Date().toISOString()
  const { error } = await client.from('agent_updates').upsert({
    agent_id: task.agent_id,
    kind: 'report',
    title: `إنجاز المهمة: ${task.title}`,
    body: task.result_note || `• المهمة «${task.title}» اتعلمت منجزة يدويًا.`,
    severity: 'منخفض',
    status: 'approved',
    decided_by: 'mahmoud',
    decided_at: now,
    op_id: `manual-task-report:${task.id}:${now.slice(0, 10)}`,
    payload: {
      task_id: task.id,
      category: task.agent_id,
      actions: [
        { type: 'navigate', label: 'فتح غرفة الوكيل', href: `/agent/${task.agent_id}` },
        { type: 'copy', label: 'نسخ التقرير' },
      ],
    },
  }, { onConflict: 'op_id', ignoreDuplicates: true })
  return error ? { ok: false, error } : { ok: true, error: null }
}

/** تعديل بيانات المهمة مع فلترة الحقول المسموح بها؛ لا يوجد حذف فعلي. */
export async function updateAgentTask(
  client: SupabaseClient,
  taskId: string,
  values: Partial<Pick<AgentTask, 'title' | 'description' | 'priority' | 'dependency_id' | 'schedule_type' | 'scheduled_time' | 'schedule_day_of_week'>>,
): Promise<{ ok: boolean; error: SupabaseError | null }> {
  const patch: Record<string, unknown> = { ...values, updated_at: new Date().toISOString() }
  if (values.title !== undefined) patch.title = values.title.trim()
  if (values.description !== undefined) patch.description = values.description?.trim() || null
  if (values.schedule_type === 'none') {
    patch.scheduled_time = null
    patch.schedule_day_of_week = null
  }
  if (values.schedule_type === 'daily') patch.schedule_day_of_week = null
  if (values.schedule_type === 'daily' || values.schedule_type === 'weekly') patch.schedule_timezone = 'Africa/Cairo'
  const { error } = await client.from('agent_tasks').update(patch).eq('id', taskId)
  return error ? { ok: false, error } : { ok: true, error: null }
}

/** أرشفة المهمة بدل حذفها نهائيًا للحفاظ على سجل التدقيق. */
export async function archiveAgentTask(
  client: SupabaseClient,
  taskId: string,
): Promise<{ ok: boolean; error: SupabaseError | null }> {
  const now = new Date().toISOString()
  const { error } = await client.from('agent_tasks')
    .update({ archived_at: now, updated_at: now })
    .eq('id', taskId)
    .is('archived_at', null)
  return error ? { ok: false, error } : { ok: true, error: null }
}

export async function fetchAgentUpdates(
  client: SupabaseClient,
  agentId?: string,
): Promise<{ items: AgentUpdate[]; error: SupabaseError | null }> {
  let query = client
    .from('agent_updates')
    .select('*')
    .order('created_at', { ascending: false })
    .limit(100)

  if (agentId) {
    query = query.eq('agent_id', agentId)
  }

  const { data, error } = await query
  if (error) return { items: [], error }
  return { items: (data ?? []) as AgentUpdate[], error: null }
}

/** سجل خطوات موحد لغرفة الوكيل — يُطبع كل خطوة في الكونسول ويرجع النص للعرض */
export type RoomLog = (step: string, detail?: string) => void

export const makeRoomLog =
  (agentId: string): RoomLog =>
  (step, detail) => {
    const line = `[غرفة ${agentId}] ${step}${detail ? ' — ' + detail : ''}`
    if (typeof console !== 'undefined') console.info(line)
  }

/** اشتراك حي على مهام وكيل واحد: INSERT و UPDATE تظهر فوراً بلا تحديث الصفحة */
export function subscribeAgentTasks(
  client: SupabaseClient,
  agentId: string,
  handlers: { onInsert?: (row: AgentTask) => void; onUpdate?: (row: AgentTask) => void; onStatus?: (s: string) => void },
): { unsubscribe: () => void } {
  const ch = client
    .channel(`agent-tasks-${agentId}-${Math.random().toString(36).slice(2, 8)}`)
    .on(
      'postgres_changes',
      { event: 'INSERT', schema: 'public', table: 'agent_tasks', filter: `agent_id=eq.${agentId}` },
      (p) => handlers.onInsert?.(p.new as AgentTask),
    )
    .on(
      'postgres_changes',
      { event: 'UPDATE', schema: 'public', table: 'agent_tasks', filter: `agent_id=eq.${agentId}` },
      (p) => handlers.onUpdate?.(p.new as AgentTask),
    )
    .subscribe((status) => handlers.onStatus?.(status))

  return { unsubscribe: () => void ch.unsubscribe() }
}

/** اشتراك حي على تحديثات وكيل واحد: أي إدراج/قرار يظهر فوراً */
export function subscribeAgentUpdates(
  client: SupabaseClient,
  agentId: string,
  handlers: { onInsert?: (row: AgentUpdate) => void; onUpdate?: (row: AgentUpdate) => void; onStatus?: (s: string) => void },
): { unsubscribe: () => void } {
  const ch = client
    .channel(`agent-updates-${agentId}-${Math.random().toString(36).slice(2, 8)}`)
    .on(
      'postgres_changes',
      { event: 'INSERT', schema: 'public', table: 'agent_updates', filter: `agent_id=eq.${agentId}` },
      (p) => handlers.onInsert?.(p.new as AgentUpdate),
    )
    .on(
      'postgres_changes',
      { event: 'UPDATE', schema: 'public', table: 'agent_updates', filter: `agent_id=eq.${agentId}` },
      (p) => handlers.onUpdate?.(p.new as AgentUpdate),
    )
    .subscribe((status) => handlers.onStatus?.(status))

  return { unsubscribe: () => void ch.unsubscribe() }
}

export const statusLabel: Record<string, string> = {
  pending: 'معلقة',
  in_progress: 'جارية',
  done: 'منجزة',
  rejected: 'مرفوضة',
}

export const statusLabelUpdate: Record<string, string> = {
  pending: 'بانتظار قرار المالك',
  approved: 'معتمد ✅',
  rejected: 'مرفوض ❌',
}

export const isDoneStatus = (s: string | null | undefined) => s === 'done' || s === 'rejected'
export const isRunningStatus = (s: string | null | undefined) => s === 'in_progress'

/** تحديث قرار المالك على تحديث (اعتماد / رفض) — لا حذف نهائياً */
export async function updateAgentUpdateStatus(
  client: SupabaseClient,
  id: string,
  status: 'approved' | 'rejected',
  decided_by = 'mahmoud',
): Promise<{ ok: boolean; error: SupabaseError | null }> {
  const now = new Date().toISOString()
  const { error } = await client
    .from('agent_updates')
    .update({ status, decided_by, decided_at: now })
    .eq('id', id)
  if (error) return { ok: false, error }
  return { ok: true, error: null }
}
