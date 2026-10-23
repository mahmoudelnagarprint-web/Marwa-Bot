// lib/agent-alerts.ts — الشات الاستباقي ومستمع التنبيهات (Proactive Alerts)
// استماع حي لجدول agent_updates عبر Realtime
// عند إدراج تحديث بدرجة أهمية "عالي" أو نوع "alert" يتم إطلاق تنبيه صوتي وتنبيه Toast فوري.

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

/** تشغيل تنبيه صوتي فخم ونقي (Web Audio API) بدون ملفات خارجية */
export function playAlertChime() {
  if (typeof window === 'undefined') return
  try {
    const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext
    if (!AudioCtx) return
    const ctx = new AudioCtx()
    if (ctx.state === 'suspended') {
      void ctx.resume()
    }
    const now = ctx.currentTime

    const osc1 = ctx.createOscillator()
    const gain1 = ctx.createGain()
    osc1.type = 'sine'
    osc1.frequency.setValueAtTime(880, now) // A5
    osc1.frequency.exponentialRampToValueAtTime(1174.66, now + 0.15) // D6
    gain1.gain.setValueAtTime(0.2, now)
    gain1.gain.exponentialRampToValueAtTime(0.01, now + 0.25)
    osc1.connect(gain1)
    gain1.connect(ctx.destination)
    osc1.start(now)
    osc1.stop(now + 0.25)

    const osc2 = ctx.createOscillator()
    const gain2 = ctx.createGain()
    osc2.type = 'triangle'
    osc2.frequency.setValueAtTime(1318.51, now + 0.12) // E6
    osc2.frequency.exponentialRampToValueAtTime(1760, now + 0.35) // A6
    gain2.gain.setValueAtTime(0.18, now + 0.12)
    gain2.gain.exponentialRampToValueAtTime(0.005, now + 0.45)
    osc2.connect(gain2)
    gain2.connect(ctx.destination)
    osc2.start(now + 0.12)
    osc2.stop(now + 0.45)
  } catch {
    // نتجاهل أي قيود أمنية للـ audio policy
  }
}

/**
 * اشتراك واحد على INSERT في agent_updates. أي صف عاجل يمرر للواجهة فوراً مع تشغيل الصوت.
 */
export function subscribeUrgentAlerts(
  client: SupabaseClient,
  onAlert: (row: AlertRow) => void,
): { unsubscribe: () => void } {
  const ch = client
    .channel('marwa-proactive-alerts')
    .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'agent_updates' }, (payload) => {
      const row = payload.new as AlertRow
      if (isUrgent(row)) {
        playAlertChime()
        onAlert(row)
      }
    })
    .subscribe()
  return {
    unsubscribe: () => {
      void ch.unsubscribe()
    },
  }
}
