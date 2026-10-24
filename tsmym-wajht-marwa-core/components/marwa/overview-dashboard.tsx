'use client'

import { useState, useTransition } from 'react'
import {
  AlertCircle,
  ArrowUpRight,
  CheckCircle2,
  Clock,
  Coins,
  CreditCard,
  FileText,
  Loader2,
  TrendingUp,
  XCircle,
  Zap,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { agents, type Agent, type AgentId } from '@/lib/marwa-data'
import { formatCairoDate, updateAgentUpdateStatus, type AgentTask, type AgentUpdate } from '@/lib/agent-tasks'
import { supabase } from '@/lib/supabase'

export function OverviewDashboard({
  onSelectAgent,
  pendingUpdates,
  tasks,
  urgentAgents,
  onRefresh,
}: {
  onSelectAgent: (id: AgentId) => void
  pendingUpdates: AgentUpdate[]
  tasks: AgentTask[]
  urgentAgents: Set<string>
  onRefresh?: () => void
}) {
  const [decidingId, setDecidingId] = useState<string | null>(null)
  const [isPending, startTransition] = useTransition()

  // 📱 مقترحات السوشيال ميديا — إسناد فوري عبر محرك السلاش (/task → صندوق الوكيل + Supabase)
  const [slashBusy, setSlashBusy] = useState<string | null>(null)
  const [slashMsg, setSlashMsg] = useState<string | null>(null)
  const runSlashTask = async (agentName: string, command: string) => {
    setSlashBusy(command)
    setSlashMsg(null)
    try {
      const res = await fetch('/api/slash', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command }),
      })
      const data = await res.json()
      setSlashMsg(
        data?.ok
          ? `✓ تمت الإسناد إلى ${agentName} — المهمة في صندوقه وستظهر في غرفته`
          : `✗ فشل الإسناد: ${data?.error ?? data?.reason ?? 'خطأ غير معروف'}`,
      )
      onRefresh?.()
    } catch (e) {
      setSlashMsg('فشل الاتصال بمحرك المهام: ' + (e instanceof Error ? e.message : String(e)))
    } finally {
      setSlashBusy(null)
    }
  }

  // احتساب المهام الجارية لحظياً والقرارات المعلقة
  const inProgressTasksCount = tasks.filter((t) => t.status === 'in_progress').length
  const pendingDecisionsCount = pendingUpdates.filter((u) => u.status === 'pending').length

  const handleDecision = (id: string, decision: 'approved' | 'rejected') => {
    if (!supabase) return
    setDecidingId(id)
    startTransition(async () => {
      await updateAgentUpdateStatus(supabase!, id, decision)
      setDecidingId(null)
      onRefresh?.()
    })
  }

  // عدّاد المهام المفتوحة لكل وكيل
  const openTasksByAgent = tasks.reduce<Record<string, number>>((acc, t) => {
    if (t.status === 'pending' || t.status === 'in_progress') {
      acc[t.agent_id] = (acc[t.agent_id] || 0) + 1
    }
    return acc
  }, {})

  return (
    <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-6 scrollbar-thin">
      {/* 1. الترويسة الترحيبية */}
      <div className="space-y-1.5 border-b border-border/60 pb-5">
        <h1 className="font-display text-3xl md:text-4xl font-bold tracking-tight text-foreground">
          صباح الخير يا محمود
        </h1>
        <p className="text-sm md:text-base text-muted-foreground flex flex-wrap items-center gap-2">
          <span>غرفة قيادة مروة كور جاهزة.</span>
          <span className="inline-flex items-center gap-1.5 rounded-full bg-secondary/80 px-2.5 py-0.5 text-xs font-medium text-foreground">
            <span className="size-2 rounded-full bg-warning" />
            <span>{pendingDecisionsCount} قرارات معلقة بانتظارك</span>
          </span>
          <span className="inline-flex items-center gap-1.5 rounded-full bg-secondary/80 px-2.5 py-0.5 text-xs font-medium text-foreground">
            <span className="size-2 rounded-full bg-primary animate-pulse" />
            <span>{inProgressTasksCount} مهام جارية لحظياً</span>
          </span>
        </p>
      </div>

      {/* 2. بطاقات المؤشرات المالية (KPI Cards) بالتأثير الذهبي */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* بطاقة الخزنة */}
        <div className="relative overflow-hidden rounded-xl border border-primary/40 bg-card p-4 md:p-5 gold-glow transition-all">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-muted-foreground">الخزنة النقدية الحالية</span>
            <div className="flex size-9 items-center justify-center rounded-lg bg-primary/20 text-primary">
              <Coins className="size-5" />
            </div>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span
              dir="ltr"
              className="font-display text-2xl md:text-3xl font-bold tracking-tight text-primary"
            >
              7,380.00
            </span>
            <span className="font-display text-sm font-semibold text-primary">ج</span>
          </div>
          <p className="mt-2 text-[11px] text-muted-foreground flex items-center gap-1">
            <span className="text-emerald-400 font-mono">5,625.00 ج</span>
            <span>افتتاحي + دخل الخزنة الفعلي</span>
          </p>
        </div>

        {/* بطاقة دخل أكتوبر */}
        <div className="relative overflow-hidden rounded-xl border border-primary/40 bg-card p-4 md:p-5 gold-glow transition-all">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-muted-foreground">دخل أكتوبر (النافذة الرسمية)</span>
            <div className="flex size-9 items-center justify-center rounded-lg bg-primary/20 text-primary">
              <TrendingUp className="size-5" />
            </div>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span
              dir="ltr"
              className="font-display text-2xl md:text-3xl font-bold tracking-tight text-primary"
            >
              1,755.00
            </span>
            <span className="font-display text-sm font-semibold text-primary">ج</span>
          </div>
          <p className="mt-2 text-[11px] text-muted-foreground flex items-center gap-1">
            <span>محسوب بدقة من</span>
            <span className="font-mono text-foreground/80">2026-10-01</span>
          </p>
        </div>

        {/* بطاقة الآجل */}
        <div className="relative overflow-hidden rounded-xl border border-primary/40 bg-card p-4 md:p-5 gold-glow transition-all">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-muted-foreground">الآجل المعلق (مديونيات العملاء)</span>
            <div className="flex size-9 items-center justify-center rounded-lg bg-primary/20 text-primary">
              <CreditCard className="size-5" />
            </div>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span
              dir="ltr"
              className="font-display text-2xl md:text-3xl font-bold tracking-tight text-primary"
            >
              790.00
            </span>
            <span className="font-display text-sm font-semibold text-primary">ج</span>
          </div>
          <p className="mt-2 text-[11px] text-muted-foreground flex items-center gap-1">
            <span>أرصدة موجبة فقط لصالح المطبعة</span>
          </p>
        </div>
      </div>

      {/* 2.5 📱 ويدجت مقترحات السوشيال ميديا — مهام جاهزة بإسناد بضغطة واحدة */}
      <div className="rounded-xl border border-sky-400/20 bg-sky-400/[0.04] p-4 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="font-display text-base md:text-lg font-bold text-foreground flex items-center gap-2">
            📱 مقترحات السوشيال ميديا
          </h2>
          <span className="text-[11px] text-muted-foreground">مهام جاهزة — إسناد بضغطة واحدة عبر محرك التفويض</span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-2.5">
          {[
            {
              agent: 'كوكو',
              label: 'حلل أداء بوستات الأمس',
              cmd: '/task @koko حلل أداء منشورات فيسبوك للأمس وجهز تقرير أداء كامل بأفضل البوستات والمقترحات',
            },
            {
              agent: 'سلمى',
              label: 'جهزي ردود التعليقات المعلقة',
              cmd: '/task @salma افحصي تعليقات فيسبوك المعلقة وجهزي الردود المقترحة لاعتماد المالك',
            },
            {
              agent: 'أفكار',
              label: 'اقترحي بوست على التريند',
              cmd: '/task @afkar اقترحي بوست تسويقي جديد بناءً على آخر التريند لمنتجات الورشة',
            },
          ].map((s) => {
            const busy = slashBusy === s.cmd
            return (
              <button
                key={s.agent}
                type="button"
                disabled={slashBusy !== null}
                onClick={() => void runSlashTask(s.agent, s.cmd)}
                className="group rounded-lg border border-border bg-card p-3 text-start transition-all hover:border-sky-400/40 hover:bg-sky-400/[0.06] disabled:opacity-50"
              >
                <p className="flex items-center gap-1.5 text-xs font-semibold text-foreground">
                  {busy ? <Loader2 className="size-3.5 animate-spin text-primary" /> : <Zap className="size-3.5 text-sky-300" />}
                  <span>
                    يا {s.agent}: {s.label}
                  </span>
                </p>
                <p className="mt-1 text-[10px] text-muted-foreground">إسناد فوري عبر صندوق مهام الوكيل + Supabase</p>
              </button>
            )
          })}
        </div>
        {slashMsg && (
          <p className={cn('rounded-lg border px-2 py-1 text-xs', slashMsg.startsWith('✓') ? 'border-emerald-400/20 bg-emerald-400/10 text-emerald-300' : 'border-rose-400/20 bg-rose-400/10 text-rose-300')}>
            {slashMsg}
          </p>
        )}
      </div>

      {/* 3. شبكة بطاقات الوكلاء العشرة (Agent Grid) */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="font-display text-lg md:text-xl font-bold text-foreground flex items-center gap-2">
            <span>أسطول الوكلاء العشرة</span>
            <span className="text-xs font-normal text-muted-foreground">(انقر للدخول إلى غرفة الوكيل)</span>
          </h2>
          <span className="text-xs text-primary font-medium">10 متصلين</span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3.5">
          {agents.map((agent) => {
            const hasUrgent = urgentAgents.has(agent.id)
            const openTasks = openTasksByAgent[agent.id] || 0

            return (
              <button
                key={agent.id}
                type="button"
                onClick={() => onSelectAgent(agent.id)}
                className="group relative flex flex-col justify-between rounded-xl border border-border bg-card p-3.5 text-start transition-all duration-200 hover:border-primary hover:bg-card/90 hover:shadow-lg focus:outline-none focus:ring-1 focus:ring-primary"
              >
                {/* نقطة النبض الحمراء في الزاوية إذا كان لديه تنبيه عاجل */}
                {hasUrgent && (
                  <span
                    className="pulse-dot absolute top-2.5 start-2.5 size-2.5 rounded-full bg-destructive ring-2 ring-background z-10"
                    title="تنبيه عاجل يتطلب انتباهك"
                  />
                )}

                <div>
                  <div className="flex items-center justify-between mb-2.5">
                    {/* شارة الوكيل المربعة بالحرف الأول (Glyph) */}
                    <div className="flex size-9 items-center justify-center rounded-lg border border-border bg-secondary font-display text-base font-bold text-foreground transition-transform group-hover:scale-105 group-hover:border-primary/50 group-hover:bg-primary/20 group-hover:text-primary">
                      {agent.glyph}
                    </div>

                    {/* عداد المهام المفتوحة */}
                    <span
                      className={cn(
                        'rounded-full px-2 py-0.5 text-[10px] font-mono border transition-colors',
                        openTasks > 0
                          ? 'border-primary/30 bg-primary/10 text-primary font-semibold'
                          : 'border-border bg-card text-muted-foreground',
                      )}
                    >
                      {openTasks} مهام
                    </span>
                  </div>

                  {/* اسم الوكيل */}
                  <h3 className="font-display text-sm md:text-base font-bold text-foreground group-hover:text-primary transition-colors flex items-center justify-between">
                    <span>{agent.name}</span>
                    <ArrowUpRight className="size-3.5 opacity-0 group-hover:opacity-100 transition-opacity text-primary" />
                  </h3>

                  {/* الوصف الوظيفي (مقطوع عند سطرين) */}
                  <p className="mt-1 text-xs text-muted-foreground line-clamp-2 leading-relaxed">
                    {agent.role}
                  </p>
                </div>

                <div className="mt-3 pt-2 border-t border-border/50 flex items-center justify-between text-[11px] text-muted-foreground">
                  <span className="flex items-center gap-1">
                    <span className="size-1.5 rounded-full bg-emerald-400" />
                    <span>نشط</span>
                  </span>
                  <span className="font-mono text-[10px] text-muted-foreground/80">{agent.code}</span>
                </div>
              </button>
            )
          })}
        </div>
      </div>

      {/* 4. قسم القرارات المعلقة (Pending Decisions) */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h2 className="font-display text-lg md:text-xl font-bold text-foreground">
              القرارات المعلقة بانتظار اعتماد المالك
            </h2>
            <span className="rounded-full bg-warning/20 px-2.5 py-0.5 text-xs font-bold text-warning border border-warning/30">
              {pendingDecisionsCount}
            </span>
          </div>
          <span className="text-xs text-muted-foreground">التوقيت: إفريقيا / القاهرة</span>
        </div>

        {pendingUpdates.length === 0 ? (
          <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border bg-card/40 p-8 text-center">
            <CheckCircle2 className="size-8 text-emerald-400/80 mb-2" />
            <p className="font-display text-sm font-semibold text-foreground">لا توجد قرارات معلقة حالياً</p>
            <p className="text-xs text-muted-foreground mt-0.5">
              كافة التحديثات والمقترحات تم اعتمادها أو رفضها، والمنظومة تعمل بكامل انسيابيتها.
            </p>
          </div>
        ) : (
          <div className="space-y-2.5">
            {pendingUpdates.map((item) => {
              const isDeciding = decidingId === item.id
              const agent = agents.find((a) => a.id === item.agent_id)

              return (
                <div
                  key={item.id}
                  className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 rounded-xl border border-border bg-card p-4 transition-colors hover:border-border/80"
                >
                  <div className="flex items-start gap-3 min-w-0">
                    <div className="flex size-8 shrink-0 items-center justify-center rounded-lg border border-border bg-secondary font-display text-sm font-bold text-primary">
                      {agent?.glyph || 'و'}
                    </div>

                    <div className="min-w-0 space-y-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-display text-sm font-bold text-foreground">
                          {agent?.name || item.agent_id}
                        </span>
                        <span className="rounded bg-secondary px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
                          {item.kind}
                        </span>
                        {item.severity && (
                          <span
                            className={cn(
                              'rounded px-1.5 py-0.5 text-[10px] font-semibold',
                              item.severity === 'عالي'
                                ? 'bg-destructive/20 text-destructive border border-destructive/30'
                                : 'bg-warning/20 text-warning',
                            )}
                          >
                            أهمية: {item.severity}
                          </span>
                        )}
                        <span className="flex items-center gap-1 text-[11px] text-muted-foreground font-mono">
                          <Clock className="size-3" />
                          <span>{formatCairoDate(item.created_at)}</span>
                        </span>
                      </div>

                      <h4 className="text-sm font-semibold text-foreground">{item.title}</h4>
                      {item.body && (
                        <p className="text-xs text-muted-foreground leading-relaxed">
                          {item.body}
                        </p>
                      )}
                    </div>
                  </div>

                  {/* زري اعتماد مباشر (Approved) ورفض (Rejected) */}
                  <div className="flex items-center gap-2 shrink-0 self-end sm:self-center">
                    <button
                      type="button"
                      disabled={isDeciding}
                      onClick={() => handleDecision(item.id, 'approved')}
                      className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-500/15 px-3 py-1.5 text-xs font-semibold text-emerald-300 border border-emerald-500/30 transition-all hover:bg-emerald-500/25 disabled:opacity-50"
                    >
                      {isDeciding ? (
                        <Loader2 className="size-3.5 animate-spin" />
                      ) : (
                        <CheckCircle2 className="size-3.5" />
                      )}
                      <span>اعتماد</span>
                    </button>

                    <button
                      type="button"
                      disabled={isDeciding}
                      onClick={() => handleDecision(item.id, 'rejected')}
                      className="inline-flex items-center gap-1.5 rounded-lg bg-destructive/15 px-3 py-1.5 text-xs font-semibold text-destructive border border-destructive/30 transition-all hover:bg-destructive/25 disabled:opacity-50"
                    >
                      <XCircle className="size-3.5" />
                      <span>رفض</span>
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
