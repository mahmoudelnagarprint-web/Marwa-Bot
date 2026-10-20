'use client'

// components/marwa/agent-tasks-panel.tsx — قسم «المهام الجارية وإضافة مهمة»
// (MARWA CORE task-2 — فيجن). المصدر الحي: Supabase public.agent_tasks
// (migration 006 — راصد/مروة). العرض + إضافة مهمة (INSERT بمفتاح publishable
// عبر سياسة anon) + تحديث لحظي عبر Realtime channel. بلا أي بيانات وهمية.

import { useCallback, useEffect, useRef, useState, type ComponentType } from 'react'
import { CloudOff, Database, ListPlus, ListTodo, Loader2, Plus, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { supabase, supabaseConfigured } from '@/lib/supabase'
import {
  fetchAgentTasks,
  insertAgentTask,
  isDoneStatus,
  isTableMissingErr,
  statusLabel,
  type AgentTask,
} from '@/lib/agent-tasks'
import { formatCairoTime } from '@/lib/live'

type PanelState =
  | { phase: 'loading' }
  | { phase: 'no-env' }
  | { phase: 'table-missing'; error: string }
  | { phase: 'error'; error: string }
  | { phase: 'ready' }

function PanelShell({
  icon: Icon,
  title,
  count,
  children,
}: {
  icon: typeof ListPlus
  title?: string
  count?: number
  children: React.ReactNode
}) {
  return (
    <div className="rounded-xl border border-border bg-card p-3">
      <p className="mb-2 flex items-center gap-1.5 text-xs font-medium">
        <Icon className="size-3.5 text-muted-foreground" aria-hidden="true" />
        {title ?? 'المهام الجارية'}
        {typeof count === 'number' && count > 0 && (
          <span className="rounded-full bg-violet-400/15 px-1.5 text-[10px] tabular-nums text-violet-300">{count}</span>
        )}
      </p>
      {children}
    </div>
  )
}

const statusChip: Record<string, string> = {
  pending: 'border-zinc-400/20 bg-zinc-400/10 text-zinc-300',
  in_progress: 'border-amber-400/20 bg-amber-400/10 text-amber-300',
  done: 'border-emerald-400/20 bg-emerald-400/10 text-emerald-300',
  rejected: 'border-rose-400/20 bg-rose-400/10 text-rose-300',
}

const priorityLabel: Record<string, string> = {
  low: 'منخفضة',
  normal: 'عادية',
  high: 'عالية',
  urgent: 'عاجلة',
}

export function AgentTasksPanel({
  agentId,
  agentName,
  toneDot,
}: {
  /** معرّف الوكيل كما في عمود agent_id (مثل fares) */
  agentId: string
  agentName: string
  /** لون نقطة الحالة بلون الوكيل (tailwind class) */
  toneDot?: string
}) {
  const [tasks, setTasks] = useState<AgentTask[]>([])
  const [state, setState] = useState<PanelState>({ phase: 'loading' })
  const [draft, setDraft] = useState('')
  const [adding, setAdding] = useState(false)
  const [addMsg, setAddMsg] = useState<string | null>(null)
  const channelRef = useRef<{ unsubscribe: () => void } | null>(null)

  const load = useCallback(async () => {
    if (!supabase) return
    const { tasks: next, error } = await fetchAgentTasks(supabase, agentId)
    if (error) {
      if (isTableMissingErr(error)) {
        setState({ phase: 'table-missing', error: error.message })
      } else {
        setState({ phase: 'error', error: error.message })
      }
      return
    }
    setTasks(next)
    setState({ phase: 'ready' })
  }, [agentId])

  // تحديث لحظي عبر Realtime channel (الجدول منشور في publication supabase_realtime)
  const subscribe = useCallback(() => {
    if (!supabase) return
    channelRef.current?.unsubscribe()
    const ch = supabase
      .channel('agent-tasks-live')
      .on(
        'postgres_changes',
        { event: '*', schema: 'public', table: 'agent_tasks' },
        () => {
          void load()
        },
      )
      .subscribe()
    channelRef.current = ch
  }, [load])

  useEffect(() => {
    if (!supabaseConfigured || !supabase) {
      setState({ phase: 'no-env' })
      return
    }
    void load()
    subscribe()
    return () => {
      channelRef.current?.unsubscribe()
      channelRef.current = null
    }
  }, [load, subscribe])

  async function addTask() {
    const title = draft.trim()
    if (!title || !supabase) return
    setAdding(true)
    setAddMsg(null)
    const { ok, error } = await insertAgentTask(supabase, { agent_id: agentId, title })
    setAdding(false)
    if (!ok) {
      setAddMsg(`تعذر الإدراج في agent_tasks: ${error?.message ?? '—'}`)
      return
    }
    setDraft('')
    setAddMsg('تم حفظ المهمة في جدول agent_tasks السحابي ✓')
    await load()
  }

  if (state.phase === 'no-env') {
    return (
      <PanelShell icon={CloudOff}>
        <p className="text-xs text-muted-foreground">
          الإعدادات السحابية (.env.local: NEXT_PUBLIC_SUPABASE_URL / NEXT_PUBLIC_SUPABASE_ANON_KEY) غير مهيأة — لا يمكن قراءة agent_tasks.
        </p>
      </PanelShell>
    )
  }

  if (state.phase === 'table-missing') {
    return (
      <PanelShell icon={Database}>
        <p className="text-sm font-medium">جداول راصد السحابية غير جاهزة بعد</p>
        <p className="mt-1 text-xs text-muted-foreground">
          جدول agent_tasks غير موجود في Supabase حتى الآن — راصد ينفذ task-1 (migration 006_agent_workspace). القسم يشتغل تلقائياً فور جاهزية الجداول، وبلا أي بيانات وهمية بديلة.
        </p>
        <p className="mt-1 break-all font-mono text-[10px] text-muted-foreground" dir="ltr">
          {state.error}
        </p>
        <Button variant="outline" size="xs" className="mt-3" onClick={() => void load()}>
          <RefreshCw className="size-3" aria-hidden="true" />
          إعادة محاولة الاتصال بالجداول
        </Button>
      </PanelShell>
    )
  }

  if (state.phase === 'error') {
    return (
      <PanelShell icon={CloudOff}>
        <p className="text-sm text-rose-200">خطأ في قراءة agent_tasks: {state.error}</p>
        <Button variant="outline" size="xs" className="mt-3" onClick={() => void load()}>
          إعادة المحاولة
        </Button>
      </PanelShell>
    )
  }

  if (state.phase === 'loading') {
    return (
      <PanelShell icon={ListPlus}>
        <p className="flex items-center gap-2 py-4 text-sm text-muted-foreground" aria-busy="true">
          <Loader2 className="size-4 animate-spin" aria-hidden="true" />
          جارٍ الاتصال بجدول agent_tasks السحابي...
        </p>
      </PanelShell>
    )
  }

  const openCount = tasks.filter((t) => !isDoneStatus(t.status)).length

  return (
    <PanelShell icon={ListTodo} title="المهام الجارية" count={openCount}>
      <ul className="flex flex-col divide-y divide-border">
        {tasks.length === 0 && (
          <li className="py-6 text-center text-xs text-muted-foreground">
            لا توجد مهام مسجلة لـ{agentName} بعد — أضف أول مهمة من الحقل أدناه (INSERT في جدول agent_tasks السحابي).
          </li>
        )}
        {tasks.map((t) => (
          <li key={t.id} className="flex items-start justify-between gap-3 py-2">
            <div className="min-w-0">
              <p className="flex items-center gap-2 text-sm">
                {isDoneStatus(t.status) ? (
                  <span className="flex size-4 shrink-0 items-center justify-center rounded-full border border-emerald-400/30 bg-emerald-400/15 text-[10px] text-emerald-300">
                    ✓
                  </span>
                ) : (
                  <span
                    className={cn('size-1.5 shrink-0 rounded-full', toneDot ?? 'bg-muted-foreground/50')}
                    aria-hidden="true"
                  />
                )}
                <span className="truncate">{t.title}</span>
              </p>
              <p className="mt-0.5 text-[10px] text-muted-foreground">
                {statusLabel[t.status] ?? t.status}
                {t.priority !== 'normal' && ` • أولوية ${t.priority}`}
                {` • ${t.source}`}
                {t.created_at ? ` • ${formatCairoTime(t.created_at)}` : ''}
              </p>
            </div>
            <span
              className={cn(
                'shrink-0 rounded border px-1.5 py-0.5 text-[10px]',
                t.status === 'done'
                  ? 'border-emerald-400/20 bg-emerald-400/10 text-emerald-300'
                  : t.status === 'in_progress'
                    ? 'border-amber-400/20 bg-amber-400/10 text-amber-300'
                    : 'border-border text-muted-foreground',
              )}
            >
              {statusLabel[t.status] ?? t.status}
            </span>
          </li>
        ))}
      </ul>

      <div className="mt-3 flex items-center gap-2 rounded-lg border border-border bg-background/60 p-2">
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault()
              void addTask()
            }
          }}
          placeholder={`مهمة جديدة لـ${agentName}...`}
          aria-label="عنوان المهمة الجديدة"
          className="min-w-0 flex-1 bg-transparent px-1 text-sm outline-none placeholder:text-muted-foreground"
        />
        <Button size="xs" disabled={!draft.trim() || adding} onClick={() => void addTask()} className="gap-1.5">
          {adding ? (
            <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
          ) : (
            <Plus className="size-3.5" aria-hidden="true" />
          )}
          إضافة
        </Button>
      </div>

      <p className="mt-1.5 text-[10px] text-muted-foreground">
        تحديث لحظي عبر Supabase Realtime (قناة agent-tasks) — الكتابة بمفتاح publishable وفق سياسات anon (بلا حذف — W3).
      </p>
      {addMsg && <p className="mt-1 rounded bg-background/60 px-2 py-1 text-[11px] text-muted-foreground">{addMsg}</p>}
    </PanelShell>
  )
}
