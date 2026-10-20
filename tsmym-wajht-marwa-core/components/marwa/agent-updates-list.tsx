'use client'

// components/marwa/agent-updates-list.tsx — عرض حي لـagent_updates
// (اقتراحات/شكاوى/تنبيهات — migration 006). القراءة + أزرار ✅/❌ التنفيذية (task-3).
import { useCallback, useEffect, useRef, useState } from 'react'
import { CloudOff, Loader2, MessageSquarePlus, ThumbsDown, ThumbsUp } from 'lucide-react'
import { cn } from '@/lib/utils'
import { supabase, supabaseConfigured } from '@/lib/supabase'
import { fetchAgentUpdates, updateAgentUpdateStatus, type AgentUpdate } from '@/lib/agent-tasks'
import { formatCairoTime } from '@/lib/live'

type ListState =
  | { phase: 'loading' }
  | { phase: 'no-env' }
  | { phase: 'missing' }
  | { phase: 'error'; error: string }
  | { phase: 'ready'; items: AgentUpdate[] }

const kindIcons = {
  suggestion: MessageSquarePlus,
  complaint: CloudOff,
  alert: CloudOff,
  report: MessageSquarePlus,
} as const

const severityChip: Record<string, string> = {
  عالي: 'border-rose-400/20 bg-rose-400/10 text-rose-300',
  متوسط: 'border-amber-400/20 bg-amber-400/10 text-amber-300',
  منخفض: 'border-zinc-400/20 bg-zinc-400/10 text-zinc-300',
}

const statusChip: Record<string, string> = {
  pending: 'border-zinc-400/20 bg-zinc-400/10 text-zinc-300',
  approved: 'border-emerald-400/20 bg-emerald-400/10 text-emerald-300',
  rejected: 'border-rose-400/20 bg-rose-400/10 text-rose-300',
}

const statusLabel: Record<string, string> = {
  pending: 'بانتظار قرار المالك',
  approved: 'معتمد',
  rejected: 'مرفوض',
}

const kindLabel: Record<string, string> = {
  suggestion: 'اقتراح',
  complaint: 'شكوى',
  alert: 'تنبيه',
  report: 'تقرير',
}

export function AgentUpdatesList({
  agentId,
  kind,
}: {
  agentId: string
  kind: 'suggestion' | 'complaint'
}) {
  const [state, setState] = useState<ListState>({ phase: 'loading' })
  const channelRef = useRef<{ unsubscribe: () => void } | null>(null)

  const load = useCallback(async () => {
    if (!supabase) return
    const { items, error } = await fetchAgentUpdates(supabase, agentId)
    if (error) {
      const m = error.message ?? ''
      if (m.includes('42P01') || m.includes('does not exist') || m.includes('schema cache')) {
        setState({ phase: 'missing' })
      } else {
        setState({ phase: 'error', error: m })
      }
      return
    }
    const filtered = items.filter((i) => i.kind === kind)
    setState({ phase: 'ready', items: filtered })
  }, [agentId, kind])

  // أزرار قرار المالك: ✅ اعتماد / ❌ رفض (المرحلة 2 — تنفيذ سحابي عبر updateAgentUpdateStatus)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [rowError, setRowError] = useState<{ id: string; message: string } | null>(null)

  const decide = useCallback(
    async (id: string, decision: 'approved' | 'rejected') => {
      if (!supabase) return
      setBusyId(id)
      setRowError(null)
      const { ok, error } = await updateAgentUpdateStatus(supabase, id, decision)
      setBusyId(null)
      if (!ok) {
        setRowError({ id, message: error?.message ?? 'فشل تنفيذ القرار في السحابة' })
        return
      }
      void load()
    },
    [load],
  )
  const handleApprove = useCallback((id: string) => decide(id, 'approved'), [decide])
  const handleReject = useCallback((id: string) => decide(id, 'rejected'), [decide])

  useEffect(() => {
    if (!supabaseConfigured || !supabase) {
      setState({ phase: 'no-env' })
      return
    }
    void load()
    const ch = supabase
      .channel('agent-updates-live')
      .on(
        'postgres_changes',
        { event: '*', schema: 'public', table: 'agent_updates' },
        () => {
          void load()
        },
      )
      .subscribe()
    channelRef.current = ch
    return () => {
      ch.unsubscribe()
    }
  }, [load])

  if (state.phase === 'loading') {
    return (
      <p className="flex items-center gap-2 py-3 text-sm text-muted-foreground" aria-busy="true">
        <Loader2 className="size-4 animate-spin" aria-hidden="true" />
        جارٍ الاتصال بجدول agent_updates السحابي...
      </p>
    )
  }

  if (state.phase === 'no-env') {
    return <p className="py-2 text-xs text-muted-foreground">الإعدادات السحابية غير مهيأة (.env.local) — لا يمكن قراءة agent_updates.</p>
  }

  if (state.phase === 'missing') {
    return <p className="py-2 text-xs text-muted-foreground">جدول agent_updates غير جاهز بعد (migration 006 — راصد/مروة).</p>
  }

  if (state.phase === 'error') {
    return <p className="py-2 text-xs text-rose-200">خطأ في قراءة agent_updates: {state.error}</p>
  }

  const { items } = state
  if (items.length === 0) {
    return (
      <p className="py-6 text-center text-xs text-muted-foreground">
        لا {kind === 'suggestion' ? 'مقترحات' : 'شكاوى'} حية مسجلة لـ{agentId} الآن — تُضاف من أدوات الوكلاء (fast_ops) أو مروة.
      </p>
    )
  }

  return (
    <ul className="flex flex-col divide-y divide-border">
      {items.map((u) => {
        const Icon = kindIcons[u.kind] ?? MessageSquarePlus
        return (
          <li key={u.id} className="flex items-start justify-between gap-3 py-2.5">
            <div className="min-w-0">
              <p className="flex items-center gap-2 text-sm font-medium">
                <Icon className="size-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
                <span className="truncate">{u.title}</span>
              </p>
              {u.body && <p className="mt-0.5 truncate text-xs text-muted-foreground">{u.body}</p>}
              <p className="mt-0.5 text-[10px] text-muted-foreground">
                {u.agent_id} • {formatCairoTime(u.created_at)}
              </p>
            </div>
            <div className="flex shrink-0 items-center gap-1.5">
              {u.severity && (
                <span className={cn('rounded border px-1.5 py-0.5 text-[10px]', severityChip[u.severity] ?? '')}>
                  {u.severity}
                </span>
              )}
              <span
                className={cn(
                  'inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[10px]',
                  statusChip[u.status] ?? 'border-border text-muted-foreground',
                )}
              >
                {u.status === 'approved' ? (
                  <ThumbsUp className="size-3" aria-hidden="true" />
                ) : u.status === 'rejected' ? (
                  <ThumbsDown className="size-3" aria-hidden="true" />
                ) : null}
                {statusLabel[u.status] ?? u.status}
              </span>
              {u.status === 'pending' && (
                <>
                  <button
                    type="button"
                    onClick={() => handleApprove(u.id)}
                    disabled={busyId !== null}
                    aria-label="اعتماد وتنفيذ"
                    title="اعتماد وتنفيذ في السحابة"
                    className="inline-flex items-center gap-1 rounded-md border border-emerald-400/30 bg-emerald-400/10 px-2 py-0.5 text-[10px] font-medium text-emerald-300 transition-colors hover:bg-emerald-400/20 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {busyId === u.id ? <Loader2 className="size-3 animate-spin" aria-hidden="true" /> : <ThumbsUp className="size-3" aria-hidden="true" />}
                    اعتماد ✅
                  </button>
                  <button
                    type="button"
                    onClick={() => handleReject(u.id)}
                    disabled={busyId !== null}
                    aria-label="رفض"
                    title="رفض الاقتراح"
                    className="inline-flex items-center gap-1 rounded-md border border-rose-400/30 bg-rose-400/10 px-2 py-0.5 text-[10px] font-medium text-rose-300 transition-colors hover:bg-rose-400/20 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <ThumbsDown className="size-3" aria-hidden="true" />
                    رفض ❌
                  </button>
                </>
              )}
            </div>
            {rowError?.id === u.id && (
              <p className="w-full text-left text-[10px] text-rose-300" role="alert">
                {rowError.message}
              </p>
            )}
          </li>
        )
      })}
    </ul>
  )
}
