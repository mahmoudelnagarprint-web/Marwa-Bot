'use client'

import { useCallback, useEffect, useState } from 'react'
import {
  agentMap,
  agents,
  type AgentId,
} from '@/lib/marwa-data'
import { AlertCircle, Bell, Volume2, X } from 'lucide-react'
import { TopHeader } from './top-header'
import { AgentsSidebar } from './agents-sidebar'
import { OverviewDashboard } from './overview-dashboard'
import { AgentRoom } from './agent-room'
import { ReportsDialog } from './reports-dialog'
import { AchievementsDialog } from './achievements-dialog'
import { SettingsDialog } from './settings-dialog'
import { supabase, supabaseConfigured } from '@/lib/supabase'
import {
  subscribeUrgentAlerts,
  playAlertChime,
  type AlertRow,
} from '@/lib/agent-alerts'
import {
  fetchAgentTasks,
  fetchAgentUpdates,
  type AgentTask,
  type AgentUpdate,
} from '@/lib/agent-tasks'

type View = 'main' | AgentId
type DialogId = 'reports' | 'achievements' | 'settings' | null

const agentIds = agents.map((a) => a.id)

export function MarwaApp({ initialAgentId }: { initialAgentId?: string }) {
  const [isMounted, setIsMounted] = useState(false)
  const [view, setView] = useState<View>(() => {
    if (initialAgentId && agentIds.includes(initialAgentId as AgentId)) {
      return initialAgentId as AgentId
    }
    return 'main'
  })

  const [dialog, setDialog] = useState<DialogId>(null)
  const [tasks, setTasks] = useState<AgentTask[]>([])
  const [updates, setUpdates] = useState<AgentUpdate[]>([])
  const [urgentAgents, setUrgentAgents] = useState<Set<string>>(new Set())
  const [activeToast, setActiveToast] = useState<{
    id: string
    agentId: string
    agentName: string
    title: string
    body: string | null
  } | null>(null)

  // ترطيب أولي وفحص الـ URL Query
  useEffect(() => {
    setIsMounted(true)
    const q = new URLSearchParams(window.location.search).get('agent')
    if (q && agentIds.includes(q as AgentId)) {
      setView(q as AgentId)
    }
  }, [])

  // مزامنة عنوان المتصفح مع العرض الحالي
  const navigate = useCallback((next: View) => {
    setView(next)
    if (typeof window !== 'undefined') {
      const targetUrl = next === 'main' ? '/' : `/agent/${next}`
      window.history.pushState({}, '', targetUrl)
    }
  }, [])

  // تحميل البيانات الحية من Supabase
  const loadData = useCallback(async () => {
    if (!supabase) return
    const [{ tasks: allTasks }, { items: allUpdates }] = await Promise.all([
      fetchAgentTasks(supabase),
      fetchAgentUpdates(supabase),
    ])
    setTasks(allTasks)
    setUpdates(allUpdates)

    // استخراج الوكلاء الذين لديهم تنبيهات عاجلة مفتوحة
    const urgentSet = new Set<string>()
    allUpdates.forEach((u) => {
      if ((u.severity === 'عالي' || u.kind === 'alert') && u.status === 'pending') {
        urgentSet.add(u.agent_id)
      }
    })
    setUrgentAgents(urgentSet)
  }, [])

  useEffect(() => {
    void loadData()
  }, [loadData])

  // مستمع التنبيهات الاستباقية عبر Realtime مع تنبيه صوتي وToast
  useEffect(() => {
    if (!supabaseConfigured || !supabase) return

    const sub = subscribeUrgentAlerts(supabase, (row: AlertRow) => {
      const agent = agentMap[row.agent_id as AgentId]
      const agentName = agent?.name || row.agent_id

      // تفعيل Toast فوري
      setActiveToast({
        id: row.id,
        agentId: row.agent_id,
        agentName,
        title: row.title,
        body: row.body,
      })

      // إضافة الوكيل لقائمة الإنذارات العاجلة وتحديث البيانات
      setUrgentAgents((prev) => new Set([...prev, row.agent_id]))
      void loadData()
    })

    // اشتراك عام في جدول المهام للتحديث اللحظي
    const taskSub = supabase
      .channel('marwa-tasks-realtime')
      .on('postgres_changes', { event: '*', schema: 'public', table: 'agent_tasks' }, () => {
        void loadData()
      })
      .on('postgres_changes', { event: '*', schema: 'public', table: 'agent_updates' }, () => {
        void loadData()
      })
      .subscribe()

    return () => {
      sub.unsubscribe()
      void taskSub.unsubscribe()
    }
  }, [loadData])

  // عدادات المهام المفتوحة لكل وكيل
  const tasksCountByAgent = tasks.reduce<Record<string, number>>((acc, t) => {
    if (t.status === 'pending' || t.status === 'in_progress') {
      acc[t.agent_id] = (acc[t.agent_id] || 0) + 1
    }
    return acc
  }, {})

  const roomAgent = view !== 'main' ? agentMap[view] : null

  if (!isMounted) {
    return (
      <div className="flex h-dvh flex-col items-center justify-center bg-background text-foreground">
        <div className="flex items-center gap-3 text-sm text-muted-foreground">
          <span className="size-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          <span className="font-display">جاري تهيئة غرفة قيادة مروة كور…</span>
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-dvh flex-col overflow-hidden bg-background text-foreground" dir="rtl">
      {/* Toast الإنذارات الاستباقية العاجلة مع نقطة نبض وصوت */}
      {activeToast && (
        <div className="fixed top-4 start-1/2 -translate-x-1/2 z-50 flex items-center gap-3 rounded-xl border border-destructive/50 bg-card p-3.5 shadow-2xl gold-glow animate-in slide-in-from-top-4 duration-300 max-w-lg w-[92vw]">
          <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-destructive/20 text-destructive">
            <span className="pulse-dot size-3 rounded-full bg-destructive" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span className="font-display text-xs font-bold text-destructive">
                تنبيه عاجل من {activeToast.agentName}
              </span>
              <span className="text-[10px] text-muted-foreground font-mono">الآن</span>
            </div>
            <p className="text-sm font-semibold text-foreground line-clamp-1">{activeToast.title}</p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <button
              type="button"
              onClick={() => {
                navigate(activeToast.agentId as AgentId)
                setActiveToast(null)
              }}
              className="rounded-lg bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground hover:bg-primary/90 transition-colors"
            >
              عرض الغرفة
            </button>
            <button
              type="button"
              onClick={() => setActiveToast(null)}
              className="rounded-lg p-1 text-muted-foreground hover:text-foreground"
            >
              <X className="size-4" />
            </button>
          </div>
        </div>
      )}

      {/* الشريط العلوي */}
      <TopHeader
        onReports={() => setDialog('reports')}
        onAchievements={() => setDialog('achievements')}
        onOpenSettings={() => setDialog('settings')}
      />

      {/* المحتوى الرئيسي للشاشة: الشريط الجانبي + المساحة التفاعلية */}
      <div className="flex min-h-0 flex-1 flex-col md:flex-row overflow-hidden">
        {/* الشريط الجانبي (Sidebar) الثابت في الديسكتوب والأفقي في الموبايل */}
        <AgentsSidebar
          view={view}
          onNavigate={navigate}
          urgentAgents={urgentAgents}
          tasksCount={tasksCountByAgent}
        />

        {/* مساحة العمل: إما نظرة عامة (Overview) أو غرفة الوكيل (AgentRoom) */}
        <main className="flex min-w-0 flex-1 flex-col overflow-hidden">
          {roomAgent ? (
            <AgentRoom
              key={roomAgent.id}
              agent={roomAgent}
              onBack={() => navigate('main')}
            />
          ) : (
            <OverviewDashboard
              onSelectAgent={(id) => navigate(id)}
              pendingUpdates={updates.filter((u) => u.status === 'pending')}
              tasks={tasks}
              urgentAgents={urgentAgents}
              onRefresh={loadData}
            />
          )}
        </main>
      </div>

      <ReportsDialog open={dialog === 'reports'} onOpenChange={(v) => setDialog(v ? 'reports' : null)} />
      <AchievementsDialog open={dialog === 'achievements'} onOpenChange={(v) => setDialog(v ? 'achievements' : null)} />
      <SettingsDialog open={dialog === 'settings'} onOpenChange={(v) => setDialog(v ? 'settings' : null)} />
    </div>
  )
}
