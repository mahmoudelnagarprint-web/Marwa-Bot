// lib/agent-alerts.ts — الشات الاستباقي (ماركة السحاب عبر Realtime)
// MARWA CORE task-4 (أمر المالك 2026-10-20): أي صف جديد في agent_updates
// بـ severity='عالي' أو kind='alert' يظهر فوراً كرسالة من الوكيل في شات غرفته —
// بلا أي تدخل من المالك. المصدر: Supabase Realtime (نفس اشتراك جدول المهام).
import type { SupabaseClient } from '@supabase/supabase-js'

export type AlertRow = {
  id: string
  agent_id: string
  kind: string
  title: string
  body: string | null
  severity: string | null
  status: string
  created_at: string
}

/** شرط التنبيه العاجل كما حدده المالك: severity='عالي' أو kind='alert' */
export const isUrgent = (r: { kind?: string | null; severity?: string | null }) =>
  r.severity === 'عالي' || r.kind === 'alert'

export function buildAlertText(r: AlertRow, agentName: string): string {
  const head = `🚨 تنبيه عالي — ${agentName}`
  return r.body ? `${head}:\n${r.title}\n${r.body}` : `${head}:\n${r.title}`
}

/**
 * اشتراك واحد على INSERT في agent_updates. أي صف عاجل يمرر للواجهة فوراً.
 * ملاحظة: القرارات (✅/❌) على التحديث لا تُعاد كرسائل — تظهر في قائمة القرارات فقط.
 */
export function subscribeUrgentAlerts(
  client: SupabaseClient,
  onAlert: (row: AlertRow) => void,
): { unsubscribe: () => void } {
  const ch = client
    .channel('marwa-proactive-alerts')
    .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'agent_updates' }, (payload) => {
      const row = payload.new as AlertRow
      if (isUrgent(row)) onAlert(row)
    })
    .subscribe()
  return {
    unsubscribe: () => {
      void ch.unsubscribe()
    },
  }
}
