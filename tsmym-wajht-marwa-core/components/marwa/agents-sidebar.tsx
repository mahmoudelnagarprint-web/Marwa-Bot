'use client'

import { LayoutDashboard } from 'lucide-react'
import { cn } from '@/lib/utils'
import { agents, type AgentId } from '@/lib/marwa-data'

export function AgentsSidebar({
  view,
  onNavigate,
  unread = {},
  urgentAgents = new Set(),
  tasksCount = {},
}: {
  view: 'main' | AgentId
  onNavigate: (v: 'main' | AgentId) => void
  unread?: Partial<Record<AgentId, number>>
  urgentAgents?: Set<string>
  tasksCount?: Partial<Record<AgentId, number>>
}) {
  return (
    <aside
      className="flex w-full flex-col border-b border-sidebar-border bg-sidebar md:h-full md:w-64 md:shrink-0 md:border-b-0 md:border-e"
      aria-label="غرفة القيادة والوكلاء"
    >
      {/* شعار المنظومة أعلى الشريط */}
      <div className="flex items-center gap-3 border-b border-sidebar-border px-4 py-3.5">
        <div className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-primary font-display text-xl font-bold text-primary-foreground shadow-sm gold-glow">
          م
        </div>
        <div className="flex flex-col min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-display text-base font-bold text-foreground">مروة كور</span>
            <span className="inline-block size-2 rounded-full bg-emerald-400 animate-pulse" title="متصل بالطبقة الحية" />
          </div>
          <span className="text-xs font-medium text-primary">غرفة القيادة</span>
        </div>
      </div>

      {/* قائمة التنقل (أفقية في الموبايل، رأسية ثابتة في الديسكتوب) */}
      <nav className="flex min-h-0 flex-1 flex-row gap-1.5 overflow-x-auto p-3 scrollbar-thin md:flex-col md:overflow-y-auto">
        {/* رابط نظرة عامة */}
        <button
          type="button"
          onClick={() => onNavigate('main')}
          aria-current={view === 'main' ? 'page' : undefined}
          className={cn(
            'group flex shrink-0 items-center gap-3 rounded-xl px-3 py-2.5 text-start transition-all',
            view === 'main'
              ? 'bg-primary/15 text-primary border border-primary/30 shadow-sm'
              : 'text-foreground/80 hover:bg-sidebar-accent hover:text-foreground border border-transparent',
          )}
        >
          <div
            className={cn(
              'flex size-8 shrink-0 items-center justify-center rounded-lg border transition-colors',
              view === 'main'
                ? 'border-primary/40 bg-primary/20 text-primary'
                : 'border-border bg-card/60 text-muted-foreground group-hover:text-foreground',
            )}
          >
            <LayoutDashboard className="size-4" />
          </div>
          <div className="min-w-0 flex-1">
            <span className="block font-display text-sm font-semibold">نظرة عامة</span>
            <span className="hidden text-[11px] text-muted-foreground md:block">لوحة التحكم والمؤشرات</span>
          </div>
        </button>

        {/* عنوان الوكلاء العشرة */}
        <div className="hidden items-center justify-between px-3 pt-3 pb-1 md:flex">
          <span className="text-[11px] font-semibold tracking-wider text-muted-foreground uppercase">
            الوكلاء العشرة (10)
          </span>
          <span className="rounded-md bg-secondary px-1.5 py-0.5 text-[10px] font-mono text-muted-foreground">
            RTL Live
          </span>
        </div>

        {/* قائمة الوكلاء العشرة */}
        {agents.map((agent) => {
          const selected = view === agent.id
          const hasUrgent = urgentAgents.has(agent.id)
          const unreadCount = unread[agent.id] ?? 0
          const openTasks = tasksCount[agent.id] ?? 0

          return (
            <button
              key={agent.id}
              type="button"
              onClick={() => onNavigate(agent.id)}
              aria-current={selected ? 'page' : undefined}
              className={cn(
                'group relative flex shrink-0 items-center gap-3 rounded-xl px-3 py-2 text-start transition-all',
                selected
                  ? 'bg-sidebar-accent border border-primary/40 text-foreground shadow-sm'
                  : 'text-foreground/75 hover:bg-sidebar-accent/60 hover:text-foreground border border-transparent',
              )}
            >
              {/* شارة الوكيل المربعة بالحرف الأول (Glyph) */}
              <div
                className={cn(
                  'relative flex size-8 shrink-0 items-center justify-center rounded-lg border font-display text-sm font-bold transition-transform group-hover:scale-105',
                  selected
                    ? 'border-primary/50 bg-primary/20 text-primary'
                    : 'border-border/80 bg-card text-foreground/90',
                )}
              >
                {agent.glyph}
                {/* نقطة النبض الحمراء للإنذارات العاجلة */}
                {hasUrgent && (
                  <span className="pulse-dot absolute -top-1 -end-1 size-2.5 rounded-full bg-destructive ring-2 ring-background" />
                )}
              </div>

              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between gap-1">
                  <span className={cn('block font-display text-sm font-medium', selected && 'text-primary font-bold')}>
                    {agent.name}
                  </span>
                  <div className="flex items-center gap-1">
                    {openTasks > 0 && (
                      <span
                        className="rounded-full bg-card px-1.5 py-0.2 text-[10px] font-mono text-muted-foreground border border-border"
                        title={`${openTasks} مهام مفتوحة`}
                      >
                        {openTasks}
                      </span>
                    )}
                    {unreadCount > 0 && (
                      <span className="rounded-full bg-primary px-1.5 text-[10px] font-bold text-primary-foreground">
                        {unreadCount}
                      </span>
                    )}
                  </div>
                </div>
                <span className="hidden truncate text-[11px] text-muted-foreground md:block">
                  {agent.role}
                </span>
              </div>
            </button>
          )
        })}
      </nav>

      {/* شريط معلومات المالك والمطبعة أسفل الشريط */}
      <div className="hidden border-t border-sidebar-border p-3 md:block">
        <div className="rounded-xl border border-border bg-card/50 p-2.5">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-foreground">ورشة النجار برنت</span>
            <span className="text-[10px] text-primary">توقيت القاهرة</span>
          </div>
          <span className="mt-0.5 block text-[11px] text-muted-foreground">
            الإدارة المركزية: محمود
          </span>
        </div>
      </div>
    </aside>
  )
}
