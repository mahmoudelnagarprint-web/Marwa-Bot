import { Check } from 'lucide-react'
import { cn } from '@/lib/utils'
import { agentMap, type Message } from '@/lib/marwa-data'
import { AgentAvatar, marwaProfile } from './agent-avatar'

export function ChatMessage({
  message,
  onAction,
}: {
  message: Message
  onAction?: (messageId: string, actionId: string, label: string) => void
}) {
  if (message.author === 'system') {
    return (
      <div className="flex justify-center py-1">
        <p className="rounded-full border border-border bg-card/60 px-3 py-1 text-xs text-muted-foreground">
          {message.text}
        </p>
      </div>
    )
  }

  if (message.author === 'user') {
    return (
      <div className="flex justify-end">
        <div className="max-w-[78%] rounded-2xl rounded-es-md bg-secondary px-4 py-2.5">
          <p className="text-sm leading-relaxed text-secondary-foreground">{message.text}</p>
          <p className="mt-1 text-[11px] text-muted-foreground">{message.time}</p>
        </div>
      </div>
    )
  }

  const agent = message.author === 'marwa' ? null : agentMap[message.author]
  const profile = agent ?? marwaProfile
  const label = agent ? `${agent.name} ${agent.code}` : 'مروة المايسترو'

  return (
    <div className="flex gap-3">
      <AgentAvatar agent={profile} size={32} className="mt-0.5" />
      <div className="min-w-0 max-w-[82%] flex-1">
        <div className="mb-1 flex items-center gap-2">
          <span className={cn('text-sm font-medium', profile.tone.text)}>{label}</span>
          <span className="text-[11px] text-muted-foreground">{message.time}</span>
        </div>
        <div
          className={cn(
            'rounded-2xl rounded-ss-md border px-4 py-2.5',
            agent ? cn(agent.tone.border, agent.tone.softBg) : 'border-border bg-card',
          )}
        >
          <p className="text-sm leading-relaxed text-foreground/90">{message.text}</p>
        </div>
        {message.actions && message.actions.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1.5" role="group" aria-label="إجراءات سريعة">
            {message.actions.map((action) => (
              <button
                key={action.id}
                type="button"
                disabled={action.done}
                onClick={() => onAction?.(message.id, action.id, action.label)}
                className={cn(
                  'inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs transition-colors',
                  action.done
                    ? 'border-emerald-400/20 bg-emerald-400/10 text-emerald-300'
                    : 'border-border bg-background text-muted-foreground hover:border-foreground/20 hover:bg-accent hover:text-foreground',
                )}
              >
                {action.done && <Check className="size-3" aria-hidden="true" />}
                {action.label}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export function TypingIndicator({ author }: { author: Message['author'] }) {
  if (author === 'user' || author === 'system') return null
  const profile = author === 'marwa' ? marwaProfile : agentMap[author]
  return (
    <div className="flex items-center gap-3" aria-live="polite">
      <AgentAvatar agent={profile} size={28} />
      <div className="flex items-center gap-1 rounded-full border border-border bg-card px-3 py-2">
        <span className="sr-only">{profile.name} يكتب</span>
        {[0, 150, 300].map((delay) => (
          <span
            key={delay}
            className="size-1.5 animate-bounce rounded-full bg-muted-foreground"
            style={{ animationDelay: `${delay}ms` }}
            aria-hidden="true"
          />
        ))}
      </div>
    </div>
  )
}
