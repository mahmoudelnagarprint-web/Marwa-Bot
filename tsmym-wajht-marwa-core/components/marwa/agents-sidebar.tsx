'use client'

import { useState } from 'react'
import { FolderTree, MessagesSquare, PanelRightClose, Users } from 'lucide-react'
import { cn } from '@/lib/utils'
import { agents, type AgentId } from '@/lib/marwa-data'
import { AgentAvatar, marwaProfile } from './agent-avatar'
import { WorkspaceFiles } from './workspace-files'

const statusLabel = { online: 'متصل', busy: 'مشغول', idle: 'خامل' } as const

type SidebarTab = 'agents' | 'files'

export function AgentsSidebar({
  view,
  onNavigate,
  unread,
  activeAgents,
  onCollapse,
}: {
  view: 'main' | AgentId
  onNavigate: (v: 'main' | AgentId) => void
  unread: Record<AgentId, number>
  activeAgents: AgentId[]
  onCollapse?: () => void
}) {
  const [tab, setTab] = useState<SidebarTab>('agents')
  const selectedAgent: AgentId | undefined = view === 'main' ? undefined : view

  return (
    <aside className="hidden w-64 shrink-0 flex-col border-s border-border bg-sidebar lg:flex" aria-label="الوكلاء">
      <div className="flex gap-1 border-b border-border p-2" role="tablist" aria-label="أقسام الشريط الجانبي">
        <button
          type="button"
          role="tab"
          aria-selected={tab === 'agents'}
          onClick={() => setTab('agents')}
          className={cn(
            'flex flex-1 items-center justify-center gap-1.5 rounded-lg px-2 py-1.5 text-xs font-medium transition-colors',
            tab === 'agents' ? 'bg-sidebar-accent text-foreground' : 'text-muted-foreground hover:bg-sidebar-accent/60',
          )}
        >
          <Users className="size-3.5" aria-hidden="true" />
          الوكلاء
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === 'files'}
          onClick={() => setTab('files')}
          className={cn(
            'flex flex-1 items-center justify-center gap-1.5 rounded-lg px-2 py-1.5 text-xs font-medium transition-colors',
            tab === 'files' ? 'bg-sidebar-accent text-foreground' : 'text-muted-foreground hover:bg-sidebar-accent/60',
          )}
        >
          <FolderTree className="size-3.5" aria-hidden="true" />
          ملفات الوكيل
        </button>
        {onCollapse && (
          <button
            type="button"
            onClick={onCollapse}
            aria-label="طي قائمة الوكلاء"
            title="طي القائمة"
            className="flex size-7 shrink-0 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:text-foreground"
          >
            <PanelRightClose className="size-3.5" aria-hidden="true" />
          </button>
        )}
      </div>

      {tab === 'files' ? (
        <div className="flex min-h-0 flex-1 flex-col">
          <WorkspaceFiles agentId={selectedAgent} />
        </div>
      ) : (
        <nav className="flex min-h-0 flex-1 flex-col gap-1 overflow-y-auto p-3 scrollbar-thin">
          <button
            type="button"
            onClick={() => onNavigate('main')}
            aria-current={view === 'main' ? 'page' : undefined}
            className={cn(
              'flex items-center gap-3 rounded-lg px-2.5 py-2 text-start transition-colors',
              view === 'main' ? 'bg-sidebar-accent' : 'hover:bg-sidebar-accent/60',
            )}
          >
            <AgentAvatar agent={marwaProfile} size={34} showStatus />
            <span className="min-w-0 flex-1">
              <span className="block text-sm font-medium">الشات الرئيسي</span>
              <span className="block truncate text-xs text-muted-foreground">مروة تنسق كل الوكلاء</span>
            </span>
            <MessagesSquare className="size-4 text-muted-foreground" aria-hidden="true" />
          </button>

          <p className="mt-4 mb-1 px-2.5 text-[11px] font-medium tracking-wide text-muted-foreground">
            غرف الوكلاء
          </p>

          {agents.map((agent) => {
            const selected = view === agent.id
            const count = unread[agent.id]
            const active = activeAgents.includes(agent.id)
            return (
              <button
                key={agent.id}
                type="button"
                onClick={() => onNavigate(agent.id)}
                aria-current={selected ? 'page' : undefined}
                className={cn(
                  'group relative flex items-center gap-3 rounded-lg px-2.5 py-2 text-start transition-colors',
                  selected ? cn('bg-sidebar-accent') : 'hover:bg-sidebar-accent/60',
                )}
              >
                {selected && (
                  <span
                    className={cn('absolute inset-y-2 start-0 w-0.5 rounded-full', agent.tone.dot)}
                    aria-hidden="true"
                  />
                )}
                <AgentAvatar agent={agent} size={34} showStatus />
                <span className="min-w-0 flex-1">
                  <span className="flex items-center gap-1.5">
                    <span className={cn('text-sm font-medium', selected && agent.tone.text)}>{agent.name}</span>
                    <span className="font-mono text-[10px] text-muted-foreground" dir="ltr">
                      {agent.code}
                    </span>
                  </span>
                  <span className="block truncate text-xs text-muted-foreground">
                    {agent.role} · {statusLabel[agent.status]}
                  </span>
                </span>
                {count > 0 ? (
                  <span
                    className={cn(
                      'flex min-w-5 items-center justify-center rounded-full px-1.5 text-[11px] font-medium tabular-nums',
                      agent.tone.softBg,
                      agent.tone.text,
                    )}
                  >
                    {count}
                    <span className="sr-only"> رسائل غير مقروءة</span>
                  </span>
                ) : (
                  active && <span className={cn('size-1.5 rounded-full', agent.tone.dot)} aria-label="مفعّل" />
                )}
              </button>
            )
          })}
        </nav>
      )}

      <div className="border-t border-border p-3">
        <div className="rounded-lg border border-border bg-card/50 p-3">
          <p className="text-xs text-muted-foreground">{tab === 'files' ? 'الملفات' : 'الوكلاء'}</p>
          <p className="mt-2 flex justify-between text-[11px] text-muted-foreground">
            <span>
              {tab === 'files'
                ? selectedAgent
                  ? 'مكتب الوكيل المختار مُبرز بالبنفسجي'
                  : 'اختر وكيلاً لإبراز مكتبه'
                : `${activeAgents.length} من ${agents.length} مفعّل`}
            </span>
            <span className="font-mono" dir="ltr">
              MARWA CORE
            </span>
          </p>
        </div>
      </div>
    </aside>
  )
}
