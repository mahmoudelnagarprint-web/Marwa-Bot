'use client'

import { Sparkles } from 'lucide-react'
import { Switch } from '@/components/ui/switch'
import { cn } from '@/lib/utils'
import { agents, type AgentId } from '@/lib/marwa-data'

export function AgentControlBar({
  autoMode,
  onAutoModeChange,
  activeAgents,
  onToggleAgent,
}: {
  autoMode: boolean
  onAutoModeChange: (v: boolean) => void
  activeAgents: AgentId[]
  onToggleAgent: (id: AgentId) => void
}) {
  return (
    <div className="flex shrink-0 items-center gap-3 overflow-x-auto border-b border-border px-5 py-2.5 scrollbar-thin">
      <label
        className={cn(
          'flex shrink-0 cursor-pointer items-center gap-2.5 rounded-lg border px-3 py-1.5 transition-colors',
          autoMode ? 'border-foreground/15 bg-accent' : 'border-border',
        )}
      >
        <Sparkles className={cn('size-3.5', autoMode ? 'text-amber-200' : 'text-muted-foreground')} aria-hidden="true" />
        <span className="text-xs font-medium">
          وضع أوتو{' '}
          <span className="font-mono text-[10px] text-muted-foreground" dir="ltr">
            Auto-Orchestrate
          </span>
        </span>
        <Switch checked={autoMode} onCheckedChange={onAutoModeChange} size="sm" dir="ltr" aria-label="وضع أوتو" />
      </label>

      <span className="h-5 w-px shrink-0 bg-border" aria-hidden="true" />

      <div className="flex items-center gap-1.5" role="group" aria-label="تفعيل الوكلاء يدوياً">
        {agents.map((agent) => {
          const active = activeAgents.includes(agent.id)
          return (
            <button
              key={agent.id}
              type="button"
              aria-pressed={active}
              onClick={() => onToggleAgent(agent.id)}
              className={cn(
                'inline-flex shrink-0 items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs transition-colors',
                active
                  ? cn(agent.tone.border, agent.tone.activeBg, agent.tone.text)
                  : 'border-border text-muted-foreground hover:bg-accent hover:text-foreground',
              )}
            >
              <span
                className={cn('size-1.5 rounded-full', active ? agent.tone.dot : 'bg-muted-foreground/40')}
                aria-hidden="true"
              />
              {agent.name}
              <span className="font-mono text-[10px] opacity-70" dir="ltr">
                {agent.code}
              </span>
            </button>
          )
        })}
      </div>

      <span className="ms-auto shrink-0 text-[11px] text-muted-foreground">
        {activeAgents.length > 0 ? `${activeAgents.length} وكلاء مفعّلون` : 'لا يوجد وكلاء مفعّلون'}
      </span>
    </div>
  )
}
