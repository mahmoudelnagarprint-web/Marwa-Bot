'use client'

import { useState } from 'react'
import { Bot, Check, Copy, Pencil, Timer, Undo2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import { agentMap, type Message } from '@/lib/marwa-data'
import { AgentAvatar, marwaProfile } from './agent-avatar'

export function ChatMessage({
  message,
  onAction,
  onEdit,
}: {
  message: Message
  onAction?: (messageId: string, actionId: string, label: string) => void
  onEdit?: (messageId: string, newText: string) => void
}) {
  const [copied, setCopied] = useState(false)
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(message.text)

  /** نسخ نص الرسالة للحافظة بضغطة (أمر المالك 2026-10-21) */
  async function copyText() {
    try {
      await navigator.clipboard.writeText(message.text)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch { /* الحافظة غير متاحة */ }
  }

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
      <div className="group flex justify-end">
        <div className="flex max-w-[78%] flex-col items-end gap-1">
          {editing ? (
            <div className="w-full min-w-64 rounded-2xl rounded-es-md border border-sky-400/40 bg-secondary p-2">
              <textarea
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                rows={Math.min(6, Math.max(2, Math.ceil(draft.length / 60)))}
                autoFocus
                aria-label="تعديل الرسالة"
                className="w-full resize-none bg-transparent text-sm leading-relaxed text-secondary-foreground outline-none"
              />
              <div className="mt-1.5 flex justify-end gap-1.5">
                <button
                  type="button"
                  onClick={() => { setEditing(false); setDraft(message.text) }}
                  className="flex items-center gap-1 rounded-md px-2 py-1 text-xs text-muted-foreground hover:text-foreground"
                >
                  <Undo2 className="size-3" /> إلغاء
                </button>
                <button
                  type="button"
                  disabled={!draft.trim()}
                  onClick={() => { setEditing(false); onEdit?.(message.id, draft.trim()) }}
                  className="flex items-center gap-1 rounded-md bg-sky-400/20 px-2 py-1 text-xs text-sky-200 transition-colors hover:bg-sky-400/30 disabled:opacity-40"
                >
                  <Check className="size-3" /> حفظ وإعادة الإرسال
                </button>
              </div>
            </div>
          ) : (
            <div className="rounded-2xl rounded-es-md bg-secondary px-4 py-2.5">
              <p className="text-sm leading-relaxed text-secondary-foreground">{message.text}</p>
              <p className="mt-1 text-[11px] text-muted-foreground">{message.time}</p>
            </div>
          )}
          {!editing && (
            <div className="flex items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100">
              <button
                type="button"
                onClick={() => void copyText()}
                aria-label="نسخ الرسالة"
                title="نسخ"
                className="flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] text-muted-foreground hover:text-foreground"
              >
                {copied ? <Check className="size-3 text-emerald-300" /> : <Copy className="size-3" />}
                {copied ? 'تم النسخ' : 'نسخ'}
              </button>
              {onEdit && (
                <button
                  type="button"
                  onClick={() => setEditing(true)}
                  aria-label="تعديل الرسالة وإعادة إرسالها"
                  title="تعديل"
                  className="flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] text-muted-foreground hover:text-foreground"
                >
                  <Pencil className="size-3" /> تعديل
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    )
  }

  const agent = message.author === 'marwa' ? null : agentMap[message.author]
  const profile = agent ?? marwaProfile
  const label = agent ? `${agent.name} ${agent.code}` : 'مروة المايسترو'

  return (
    <div className="group flex gap-3">
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

        {/* شارة هوية النموذج ووقت الاستجابة — من ردود الذكاء الحقيقية فقط (أمر المالك 2026-10-21) */}
        {message.meta && (
          <p className="mt-1 flex flex-wrap items-center gap-2 text-[10px] text-muted-foreground" dir="ltr">
            <span className="inline-flex items-center gap-1 rounded bg-muted/60 px-1.5 py-0.5 font-mono">
              <Bot className="size-3" aria-hidden="true" /> {message.meta.model}
            </span>
            <span className="inline-flex items-center gap-1 rounded bg-muted/60 px-1.5 py-0.5 font-mono">
              <Timer className="size-3" aria-hidden="true" /> {(message.meta.ms / 1000).toFixed(1)}s
            </span>
          </p>
        )}

        <div className="mt-1 flex items-center gap-1">
          <button
            type="button"
            onClick={() => void copyText()}
            aria-label="نسخ الرد"
            title="نسخ"
            className="flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100 hover:text-foreground"
          >
            {copied ? <Check className="size-3 text-emerald-300" /> : <Copy className="size-3" />}
            {copied ? 'تم النسخ' : 'نسخ'}
          </button>
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
