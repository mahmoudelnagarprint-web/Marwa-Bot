'use client'

// components/marwa/agent-room.tsx — غرفة الوكيل (MARWA CORE)
// task-2 (فيجن): غرفة فارس تعرض الأرقام الحية «محسوب من البرنامج» بدل الإحصائيات
// الوهمية + قسم المهام الجارية (Supabase agent_tasks + Realtime).
// كل المصفوفات (news/reports/suggestions/complaints) فارغة افتراضياً — بلا بيانات متخيلة.

import { useEffect, useState } from 'react'
import Image from 'next/image'
import { AlertTriangle, ArrowRight, FileText, Lightbulb, ListTodo, Newspaper, UserPlus, Zap } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { agents, type Agent, type AgentId, type Message } from '@/lib/marwa-data'
import { AgentAvatar } from './agent-avatar'
import { MessageList } from './main-chat'
import { ChatComposer } from './chat-composer'
import { FaresLiveCards } from './fares-live-cards'
import { AgentTasksPanel } from './agent-tasks-panel'
import { AgentUpdatesList } from './agent-updates-list'

type TabId = 'news' | 'reports' | 'suggestions' | 'complaints' | 'tasks'

const severityStyle = {
  عالي: 'border-rose-400/20 bg-rose-400/10 text-rose-300',
  متوسط: 'border-amber-400/20 bg-amber-400/10 text-amber-300',
  منخفض: 'border-zinc-400/20 bg-zinc-400/10 text-zinc-300',
} as const

const statusLabel = { online: 'متصل الآن', busy: 'مشغول بمهمة', idle: 'خامل' } as const

const EMPTY_STATE = 'لا توجد بيانات هنا بعد — القسم يُملأ من الطبقة الحية عند تفعيله (لا بيانات وهمية).'

export function AgentRoom({
  agent,
  messages,
  typing,
  guests,
  isActive,
  onBack,
  onSend,
  onInvite,
  onToggleActive,
  onEscalate,
}: {
  agent: Agent
  messages: Message[]
  typing: Message['author'] | null
  guests: AgentId[]
  isActive: boolean
  onBack: () => void
  onSend: (text: string) => void
  onInvite: (guest: AgentId) => void
  onToggleActive: () => void
  onEscalate: (text: string) => void
}) {
  const [tab, setTab] = useState<TabId | null>('news')
  const [approved, setApproved] = useState<string[]>([])

  // deep-link للتبويب (?agent=fares&tab=tasks) — بعد الترطيب فقط لتفادي اختلاف SSR
  useEffect(() => {
    const q = new URLSearchParams(window.location.search).get('tab')
    if (!q) return
    if (q === 'tasks' && agent.id !== 'fares') return
    if ((['news', 'reports', 'suggestions', 'complaints', 'tasks'] as const).includes(q as TabId)) {
      setTab(q as TabId)
    }
  }, [agent.id])

  const tabs: { id: TabId; label: string; icon: typeof Newspaper; count: number; preview: string }[] = [
    {
      id: 'news',
      label: 'الأخبار والإحصائيات',
      icon: Newspaper,
      count: agent.news.length,
      preview:
        agent.id === 'fares'
          ? 'كروت حية — محسوب من البرنامج'
          : agent.stats[0]
            ? `${agent.stats[0].value} ${agent.stats[0].label}`
            : 'بانتظار البيانات الحية',
    },
    {
      id: 'reports',
      label: 'التقارير',
      icon: FileText,
      count: agent.reports.length,
      preview: agent.reports[0]?.title ?? 'لا تقارير رسمية بعد',
    },
    {
      id: 'suggestions',
      label: 'المقترحات',
      icon: Lightbulb,
      count: agent.suggestions.length,
      preview: agent.suggestions[0]?.title ?? 'لا مقترحات مسجلة',
    },
    {
      id: 'complaints',
      label: 'الشكاوى',
      icon: AlertTriangle,
      count: agent.complaints.length,
      preview: agent.complaints[0]?.title ?? 'لا شكاوى مسجلة',
    },
  ]

  // تبويب المهام — PoC في غرفة فارس (يُعمم على كل الوكلاء في task-3)
  if (agent.id === 'fares') {
    tabs.push({ id: 'tasks', label: 'المهام الجارية', icon: ListTodo, count: 0, preview: 'Supabase agent_tasks — حي' })
  }

  const invitable = agents.filter((a) => a.id !== agent.id && !guests.includes(a.id))
  const isLiveAgent = agent.id === 'fares'

  return (
    <section className="flex min-h-0 flex-1 flex-col" aria-label={`غرفة ${agent.name}`}>
      <div className={cn('shrink-0 border-b border-border bg-linear-to-b to-transparent', agent.tone.gradient)}>
        <div className="mx-auto max-w-4xl px-5 pt-4 pb-4">
          <div className="flex items-start gap-4">
            <div className={cn('relative size-20 shrink-0 overflow-hidden rounded-2xl ring-1', agent.tone.ring)}>
              <Image src={agent.image} alt={`صورة ${agent.name}`} fill sizes="80px" className="object-cover" priority />
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <h1 className="text-xl font-semibold">{agent.name}</h1>
                <span
                  className={cn('rounded-md border px-1.5 py-0.5 font-mono text-[11px]', agent.tone.border, agent.tone.text)}
                  dir="ltr"
                >
                  {agent.code}
                </span>
                <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <span
                    className={cn(
                      'size-1.5 rounded-full',
                      agent.status === 'online' ? 'bg-emerald-400' : agent.status === 'busy' ? 'bg-amber-400' : 'bg-zinc-500',
                    )}
                    aria-hidden="true"
                  />
                  {statusLabel[agent.status]}
                </span>
              </div>
              <p className="mt-0.5 text-sm text-muted-foreground">{agent.role}</p>
              <p className="mt-2 text-sm text-foreground/80">{agent.tagline}</p>
            </div>
            <div className="flex shrink-0 flex-col items-end gap-2">
              <Button variant="ghost" size="sm" onClick={onBack} className="gap-1.5 text-muted-foreground">
                <ArrowRight className="size-3.5" aria-hidden="true" />
                الشات الرئيسي
              </Button>
              <Button variant={isActive ? 'secondary' : 'outline'} size="sm" onClick={onToggleActive} className="gap-1.5">
                <Zap className={cn('size-3.5', isActive && agent.tone.text)} aria-hidden="true" />
                {isActive ? 'مفعّل في الشات الرئيسي' : 'تفعيل في الشات الرئيسي'}
              </Button>
            </div>
          </div>

          <div className="mt-4 grid grid-cols-2 gap-2 md:grid-cols-5" role="tablist" aria-label={`بطاقات ${agent.name}`}>
            {tabs.map((t) => {
              const selected = tab === t.id
              return (
                <button
                  key={t.id}
                  type="button"
                  role="tab"
                  aria-selected={selected}
                  aria-controls="agent-tab-panel"
                  onClick={() => setTab(selected ? null : t.id)}
                  className={cn(
                    'rounded-xl border p-3 text-start transition-colors',
                    selected ? cn(agent.tone.border, 'bg-card') : 'border-border bg-card/40 hover:bg-card',
                  )}
                >
                  <span className="flex items-center justify-between gap-2">
                    <span className="flex items-center gap-1.5 text-xs font-medium">
                      <t.icon className={cn('size-3.5', selected ? agent.tone.text : 'text-muted-foreground')} aria-hidden="true" />
                      {t.label}
                    </span>
                    <span className="text-[11px] tabular-nums text-muted-foreground">{t.count}</span>
                  </span>
                  <span className="mt-1.5 block truncate text-xs text-muted-foreground">{t.preview}</span>
                </button>
              )
            })}
          </div>

          {tab && (
            <div
              id="agent-tab-panel"
              role="tabpanel"
              className={cn(
                'mt-2 overflow-y-auto rounded-xl border border-border bg-card p-3 scrollbar-thin',
                tab === 'tasks' ? 'max-h-[420px]' : 'max-h-60',
              )}
            >
              {tab === 'news' && (
                <div className="flex flex-col gap-3">
                  {isLiveAgent ? (
                    <FaresLiveCards />
                  ) : (
                    <p className="py-3 text-center text-xs text-muted-foreground">{EMPTY_STATE}</p>
                  )}
                  {agent.news.length > 0 && (
                    <ul className="flex flex-col divide-y divide-border">
                      {agent.news.map((n) => (
                        <li key={n.text} className="flex items-center justify-between gap-3 py-2 text-sm">
                          <span className="flex items-center gap-2">
                            <span className={cn('size-1.5 shrink-0 rounded-full', agent.tone.dot)} aria-hidden="true" />
                            {n.text}
                          </span>
                          <span className="shrink-0 text-[11px] text-muted-foreground">{n.time}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}

              {tab === 'tasks' && <AgentTasksPanel agentId={agent.id} agentName={agent.name} toneDot={agent.tone.dot} />}

              {tab === 'reports' && (
                <ul className="flex flex-col divide-y divide-border">
                  {agent.reports.length === 0 && (
                    <li className="py-6 text-center text-xs text-muted-foreground">{EMPTY_STATE}</li>
                  )}
                  {agent.reports.map((r) => (
                    <li key={r.title} className="flex items-center justify-between gap-3 py-2.5">
                      <div className="min-w-0">
                        <p className="text-sm font-medium">{r.title}</p>
                        <p className="text-xs text-muted-foreground">{r.summary}</p>
                      </div>
                      <div className="flex shrink-0 items-center gap-2">
                        <span className="text-[11px] text-muted-foreground">{r.date}</span>
                        <Button variant="outline" size="xs" onClick={() => onSend(`لخص لي "${r.title}"`)}>
                          ناقش
                        </Button>
                      </div>
                    </li>
                  ))}
                </ul>
              )}

              {tab === 'suggestions' && (
                <div className="flex flex-col divide-y divide-border">
                  <AgentUpdatesList agentId={agent.id} kind="suggestion" />
                  {agent.suggestions.map((s) => {
                    const done = approved.includes(s.title)
                    return (
                      <li key={s.title} className="flex items-center justify-between gap-3 py-2.5">
                        <div className="min-w-0">
                          <p className="text-sm font-medium">{s.title}</p>
                          <p className={cn('text-xs', agent.tone.text)}>{s.impact}</p>
                        </div>
                        <Button
                          variant={done ? 'secondary' : 'outline'}
                          size="xs"
                          disabled={done}
                          onClick={() => {
                            setApproved((p) => [...p, s.title])
                            onSend(`اعتمدت المقترح: ${s.title}`)
                          }}
                        >
                          {done ? 'معتمد' : 'اعتماد'}
                        </Button>
                      </li>
                    )
                  })}
                </div>
              )}

              {tab === 'complaints' && (
                <div className="flex flex-col divide-y divide-border">
                  <AgentUpdatesList agentId={agent.id} kind="complaint" />
                  {agent.complaints.map((c) => (
                    <li key={c.title} className="flex items-center justify-between gap-3 py-2.5">
                      <div className="flex min-w-0 items-center gap-2">
                        <span className={cn('shrink-0 rounded border px-1.5 py-0.5 text-[10px]', severityStyle[c.severity])}>
                          {c.severity}
                        </span>
                        <p className="text-sm">{c.title}</p>
                      </div>
                      <Button variant="outline" size="xs" onClick={() => onEscalate(`${agent.name} تشتكي: ${c.title}`)}>
                        تصعيد لمروة
                      </Button>
                    </li>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      <div className="flex shrink-0 items-center gap-2 overflow-x-auto border-b border-border px-5 py-2 scrollbar-thin">
        <span className="shrink-0 text-xs text-muted-foreground">في الغرفة:</span>
        <span className="flex shrink-0 items-center -space-x-2 space-x-reverse">
          <AgentAvatar agent={agent} size={22} />
          {guests.map((g) => {
            const guest = agents.find((a) => a.id === g)!
            return <AgentAvatar key={g} agent={guest} size={22} />
          })}
        </span>
        {invitable.length > 0 && (
          <>
            <span className="mx-1 h-4 w-px shrink-0 bg-border" aria-hidden="true" />
            <span className="flex shrink-0 items-center gap-1 text-xs text-muted-foreground">
              <UserPlus className="size-3.5" aria-hidden="true" />
              استدعاء:
            </span>
            {invitable.map((a) => (
              <button
                key={a.id}
                type="button"
                onClick={() => onInvite(a.id)}
                className="inline-flex shrink-0 items-center gap-1.5 rounded-full border border-border px-2 py-0.5 text-xs text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
              >
                <span className={cn('size-1.5 rounded-full', a.tone.dot)} aria-hidden="true" />
                {a.name}
              </button>
            ))}
          </>
        )}
      </div>

      <MessageList messages={messages} typing={typing} />
      <div className="mx-auto w-full max-w-3xl px-5 pb-5">
        <ChatComposer
          placeholder={`تحدث مباشرة مع ${agent.name}...`}
          onSend={onSend}
          hint={guests.length > 0 ? `${guests.length + 1} وكلاء في المحادثة` : `محادثة خاصة مع ${agent.name}`}
        />
      </div>
    </section>
  )
}
