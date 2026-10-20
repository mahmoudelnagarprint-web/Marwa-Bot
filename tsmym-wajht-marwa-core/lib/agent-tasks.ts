// lib/agent-tasks.ts — الوصول الحي لجداول راصد السحابية (MARWA CORE task-2)
// المخطط الرسمي: cloud/migrations/006_agent_workspace.sql (طبّقته مروة بأمر
// المالك 2026-10-20). anon يملك select/insert/update — لا حذف (W3).
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
  kind: 'suggestion' | 'complaint' | 'alert' | 'report'
  title: string
  body: string | null
  severity: 'عالي' | 'متوسط' | 'منخفض' | null
  status: 'pending' | 'approved' | 'rejected'
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

export async function fetchAgentTasks(
  client: SupabaseClient,
  agentId: string,
): Promise<{ tasks: AgentTask[]; error: SupabaseError | null }> {
  const { data, error } = await client
    .from('agent_tasks')
    .select('*')
    .eq('agent_id', agentId)
    .order('created_at', { ascending: false })
    .limit(50)
  if (error) return { tasks: [], error }
  return { tasks: (data ?? []) as AgentTask[], error: null }
}

/** إضافة مهمة من الواجهة — INSERT حقيقي في agent_tasks (سياسة anon: مسموح) */
export async function insertAgentTask(
  client: SupabaseClient,
  payload: { agent_id: string; title: string; description?: string },
): Promise<{ ok: boolean; error: SupabaseError | null; row?: AgentTask }> {
  const row = {
    agent_id: payload.agent_id,
    title: payload.title.trim(),
    description: payload.description?.trim() || null,
    status: 'pending',
    priority: 'normal',
    source: 'ui' as const,
  }
  const { data, error } = await client.from('agent_tasks').insert(row).select().limit(1)
  if (error) return { ok: false, error }
  return { ok: true, error: null }
}

export async function fetchAgentUpdates(
  client: SupabaseClient,
  agentId: string,
): Promise<{ items: AgentUpdate[]; error: SupabaseError | null }> {
  const { data, error } = await client
    .from('agent_updates')
    .select('*')
    .eq('agent_id', agentId)
    .order('created_at', { ascending: false })
    .limit(50)
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

const DONE_STATUSES = new Set(['done', 'rejected'])
export const isDoneStatus = (s: string | null | undefined) => s === 'done' || s === 'rejected'
export const isRunningStatus = (s: string | null | undefined) => s === 'in_progress'

/** تحديث قرار المالك على اقتراح/شكوى/تنبيه — UPDATE عبر سياسة anon (no delete) */
export async function updateAgentUpdateStatus(
  client: SupabaseClient,
  id: string,
  status: 'approved' | 'rejected',
  decided_by = 'mahmoud',
): Promise<{ ok: boolean; error: SupabaseError | null }> {
  const now = new Date().toISOString()
  const { data, error } = await client
    .from('agent_updates')
    .update({ status, decided_by, decided_at: now })
    .eq('id', id)
    .select()
    .limit(1)
  if (error) return { ok: false, error }
  return { ok: true, error: null, row: data?.[0] }
}
