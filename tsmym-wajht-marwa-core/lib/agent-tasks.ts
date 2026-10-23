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
  return { tasks: (data ?? []) as AgentTask[], error: null }
}

/** إضافة مهمة من الواجهة — INSERT حقيقي في agent_tasks */
export async function insertAgentTask(
  client: SupabaseClient,
  payload: { agent_id: string; title: string; description?: string; priority?: 'low' | 'normal' | 'high' | 'urgent' },
): Promise<{ ok: boolean; error: SupabaseError | null; row?: AgentTask }> {
  const row = {
    agent_id: payload.agent_id,
    title: payload.title.trim(),
    description: payload.description?.trim() || null,
    status: 'pending',
    priority: payload.priority || 'normal',
    source: 'ui' as const,
  }
  const { data, error } = await client.from('agent_tasks').insert(row).select().limit(1)
  if (error) return { ok: false, error }
  return { ok: true, error: null, row: data?.[0] as AgentTask }
}

/** تغيير حالة المهمة — حظر الحذف الإلزامي (Audit Trail) */
export async function updateAgentTaskStatus(
  client: SupabaseClient,
  taskId: string,
  newStatus: 'pending' | 'in_progress' | 'done' | 'rejected',
): Promise<{ ok: boolean; error: SupabaseError | null }> {
  const { error } = await client
    .from('agent_tasks')
    .update({ status: newStatus, updated_at: new Date().toISOString() })
    .eq('id', taskId)
  if (error) return { ok: false, error }
  return { ok: true, error: null }
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
