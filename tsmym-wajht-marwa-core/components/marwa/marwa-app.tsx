'use client'

import { useEffect, useRef, useState } from 'react'
import {
  agentMap,
  agents,
  initialMainMessages,
  models,
  nowTime,
  type AgentId,
  type Message,
} from '@/lib/marwa-data'
import { TopHeader } from './top-header'
import { AgentControlBar } from './agent-control-bar'
import { AgentsSidebar } from './agents-sidebar'
import { NotebookPanel } from './notebook-panel'
import { MainChat } from './main-chat'
import { AgentRoom } from './agent-room'
import { ReportsDialog } from './reports-dialog'
import { AchievementsDialog } from './achievements-dialog'
import { HandoverDialog } from './handover-dialog'
import { supabase, supabaseConfigured } from '@/lib/supabase'
import { subscribeUrgentAlerts, buildAlertText, type AlertRow } from '@/lib/agent-alerts'

type View = 'main' | AgentId
type DialogId = 'reports' | 'achievements' | 'handover' | null

const agentIds = agents.map((a) => a.id)

function byAgent<T>(make: (id: AgentId) => T) {
  return Object.fromEntries(agentIds.map((id) => [id, make(id)])) as Record<AgentId, T>
}

const marwaLines = [
  'تمام، وزعت المهمة على الوكلاء وجمعت السياق من النوت بوك وآخر التقارير.',
  'فهمت. هذا ملخص ما عند الفريق، واخترت لك أنسب الإجراءات.',
  'تم. راجعت الأولويات: الطلبات العاجلة أولاً ثم الإنتاج المتأخر.',
]

const agentActions: Record<AgentId, string> = {
  salma: 'إبلاغ العميل عبر واتساب',
  fares: 'تسوية حساب العميل',
  bebo: 'اعتماد مقايسة بيبو',
  koko: 'إطلاق حملة ترويجية',
  sasa: 'تشغيل عجلة الأجهزة',
  hakim: 'استشارة سريعة',
  afkar: 'عصف ذهني',
  rased: 'تفعيل تنبيه فوري',
  vision: 'بدء الأتمتة',
}

export function MarwaApp() {
  // deep-link مباشر لغرفة وكيل (?agent=fares) — يُطبَّق بعد الترطيب فقط
  // لتفادي اختلاف SSR/عميل (hydration mismatch).
  const [view, setView] = useState<View>('main')
  useEffect(() => {
    const q = new URLSearchParams(window.location.search).get('agent')
    if (q && agentIds.includes(q as AgentId)) setView(q as AgentId)
  }, [])

  // الشات الاستباقي (task-4): أي تنبيه عاجل في العقل السحابي (severity='عالي' أو kind='alert')
  // يظهر فوراً كرسالة من الوكيل في غرفته — بلا أي تدخل من المالك.
  useEffect(() => {
    if (!supabaseConfigured || !supabase) return
    const sub = subscribeUrgentAlerts(supabase, (row: AlertRow) => {
      if (!agentIds.includes(row.agent_id as AgentId)) return
      const id = row.agent_id as AgentId
      pushRoom(id, make(id, buildAlertText(row, agentMap[id].name)))
      setUnread((prev) => ({ ...prev, [id]: (prev[id] ?? 0) + 1 }))
    })
    return () => sub.unsubscribe()
  }, [])
  const [activeAgents, setActiveAgents] = useState<AgentId[]>(['fares'])
  const [autoMode, setAutoMode] = useState(true)
  const [model, setModel] = useState(models[0].id)
  const [dialog, setDialog] = useState<DialogId>(null)
  const [mainMessages, setMainMessages] = useState<Message[]>(initialMainMessages)
  const [mainTyping, setMainTyping] = useState<Message['author'] | null>(null)
  const [roomMessages, setRoomMessages] = useState(() =>
    byAgent<Message[]>((id) => [
      {
        id: `${id}-hello`,
        author: id,
        text: `غرفة ${agentMap[id].name} جاهزة. الأرقام المالية على الكروت تُقرأ حيًّا من البرنامج وموسومة «محسوب من البرنامج» — اكتب طلبك هنا.`,
        time: '09:00',
      },
    ]),
  )
  const [roomTyping, setRoomTyping] = useState(() => byAgent<Message['author'] | null>(() => null))
  const [guests, setGuests] = useState(() => byAgent<AgentId[]>(() => []))
  const [unread, setUnread] = useState(() => byAgent((id) => agentMap[id].unread))
  const replyIndex = useRef(1)

  const nextReply = (id: AgentId) => {
    const list = agentMap[id].replies
    if (list.length === 0) {
      // لا ردود وهمية — بديل صادق حتى تفعيل الدماغ السحابي لكل وكيل
      return 'سجلت طلبك. الواجهة الحالية إثبات عمل (PoC) — الردود الحية تُفعَّل عند ربط الدماغ السحابي للوكيل.'
    }
    return list[replyIndex.current++ % list.length]
  }

  const make = (author: Message['author'], text: string, actions?: string[]): Message => ({
    id: crypto.randomUUID(),
    author,
    text,
    time: nowTime(),
    actions: actions?.map((label) => ({ id: crypto.randomUUID(), label })),
  })

  function pushMain(msg: Message) {
    setMainMessages((prev) => [...prev, msg])
  }

  function pushRoom(room: AgentId, msg: Message) {
    setRoomMessages((prev) => ({ ...prev, [room]: [...prev[room], msg] }))
  }

  function activate(ids: AgentId[]) {
    setActiveAgents((prev) => Array.from(new Set([...prev, ...ids])))
  }

  function runSequence(steps: { author: Message['author']; build: () => Message }[], setTyping: (a: Message['author'] | null) => void, push: (m: Message) => void) {
    let delay = 0
    steps.forEach((step, i) => {
      setTimeout(() => setTyping(step.author), delay)
      delay += 900
      setTimeout(() => {
        push(step.build())
        if (i === steps.length - 1) setTyping(null)
      }, delay)
      delay += 150
    })
  }

  function sendMain(text: string) {
    pushMain(make('user', text))
    // Workspace OS: أمر السلاش من الشات الرئيسي أيضاً يذهب للمحرك الحقيقي
    if (text.trim().startsWith('/')) {
      setMainTyping('marwa')
      void (async () => {
        let out: { ok?: boolean; executed?: boolean; message?: string; file?: string; push?: string } = {}
        try {
          const res = await fetch('/api/slash', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text }),
          })
          out = (await res.json()) as typeof out
        } catch {
          out = { ok: false, message: 'فشل الاتصال بمحرك التوجيه' }
        }
        const parts: string[] = []
        if (out.executed) {
          if (out.file) parts.push(`📄 ${out.file.split('\\').pop()}`)
          if (out.push) parts.push(`☁️ ${out.push === 'OK' ? 'دُفع لـSupabase' : out.push}`)
        }
        if (out.message) parts.push(out.message)
        pushMain(make('system', out.ok ? `⚡ أمر ${text.split(' ')[0]} نُفّذ. ${parts.join(' • ')}` : `⚠️ ${out.message || 'الأمر رُفض'}`))
      })()
      setMainTyping(null)
      return
    }
    const detected = autoMode
      ? agents.filter((a) => a.keywords.some((k) => text.includes(k))).map((a) => a.id)
      : []
    const newlyActivated = detected.filter((id) => !activeAgents.includes(id))
    const responders = Array.from(new Set([...detected, ...activeAgents])).slice(0, 3)
    if (newlyActivated.length) activate(newlyActivated)

    const intro = newlyActivated.length
      ? `وضع أوتو: فعّلت ${newlyActivated.map((id) => agentMap[id].name).join(' و')} تلقائياً. `
      : ''
    const actions = responders.map((id) => agentActions[id]).slice(0, 3)

    runSequence(
      [
        ...responders.map((id) => ({ author: id as Message['author'], build: () => make(id, nextReply(id)) })),
        {
          author: 'marwa' as const,
          build: () =>
            make(
              'marwa',
              intro + (responders.length ? marwaLines[replyIndex.current % marwaLines.length] : 'لا يوجد وكلاء مفعّلون. فعّل وكيلاً أو شغّل وضع أوتو وسأتولى التوزيع.'),
              actions.length ? actions : undefined,
            ),
        },
      ],
      setMainTyping,
      pushMain,
    )
  }

  function handleMainAction(messageId: string, actionId: string, label: string) {
    setMainMessages((prev) =>
      prev.map((m) =>
        m.id === messageId
          ? { ...m, actions: m.actions?.map((a) => (a.id === actionId ? { ...a, done: true } : a)) }
          : m,
      ),
    )
    pushMain(make('system', `تم تنفيذ: ${label}`))

    const mentioned = agents.filter((a) => label.includes(a.name)).map((a) => a.id)
    if (mentioned.length > 1) {
      activate(mentioned)
      pushMain(make('system', `تم تفعيل ${mentioned.map((id) => agentMap[id].name).join(' و')} في الشات`))
      return
    }
    const owner = mentioned[0] ?? (Object.keys(agentActions) as AgentId[]).find((id) => agentActions[id] === label)
    if (owner) {
      runSequence(
        [{ author: owner, build: () => make(owner, `تم يا فندم، بدأت التنفيذ: ${label}. هبلغك أول ما يخلص.`) }],
        setMainTyping,
        pushMain,
      )
    }
  }

  function toggleAgent(id: AgentId) {
    setActiveAgents((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))
  }

  function navigate(next: View) {
    setView(next)
    if (next !== 'main') setUnread((prev) => ({ ...prev, [next]: 0 }))
  }

  function sendRoom(room: AgentId, text: string) {
    pushRoom(room, make('user', text))
    // Workspace OS: أمر السلاش يذهب للمحرك الحقيقي (router_daemon) عبر /api/slash
    if (text.trim().startsWith('/')) {
      runSequence(
        [
          {
            author: 'marwa' as const,
            build: () => make('marwa', 'جارٍ تنفيذ أمر السلاش…'),
          },
        ],
        (a) => setRoomTyping((prev) => ({ ...prev, [room]: a })),
        (m) => pushRoom(room, m),
      )
      void (async () => {
        try {
          const res = await fetch('/api/slash', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text }),
          })
          const out = (await res.json()) as { ok?: boolean; executed?: boolean; message?: string; file?: string; push?: string }
          const parts: string[] = []
          if (out.executed) {
            if (out.file) parts.push(`📄 الملف: ${out.file.split('\\').pop()}`)
            if (out.push) parts.push(`☁️ السحابة: ${out.push === 'OK' ? 'دُفع لـSupabase بنجاح' : out.push}`)
          }
          if (out.message) parts.push(out.message)
          pushRoom(
            room,
            make(
              'system',
              out.ok
                ? `⚡ أمر ${text.split(' ')[0]} نُفّذ. ${parts.join(' • ')}`
                : `⚠️ ${out.message || 'الأمر رُفض'}`,
            ),
          )
        } catch {
          pushRoom(room, make('system', '⚠️ فشل الاتصال بمحرك التوجيه — المحرك غير متاح'))
        }
      })()
      return
    }
    const participants = [room, ...guests[room]]
    runSequence(
      participants.map((id) => ({ author: id, build: () => make(id, nextReply(id)) })),
      (a) => setRoomTyping((prev) => ({ ...prev, [room]: a })),
      (m) => pushRoom(room, m),
    )
  }

  function invite(room: AgentId, guest: AgentId) {
    setGuests((prev) => ({ ...prev, [room]: [...prev[room], guest] }))
    pushRoom(room, make('system', `انضم ${agentMap[guest].name} إلى غرفة ${agentMap[room].name}`))
    runSequence(
      [
        {
          author: guest,
          build: () =>
            make(guest, `أهلاً ${agentMap[room].name}، معاكم. ${agentMap[guest].tagline} قولولي محتاجين إيه من ناحيتي.`),
        },
      ],
      (a) => setRoomTyping((prev) => ({ ...prev, [room]: a })),
      (m) => pushRoom(room, m),
    )
  }

  function delegateToMarwa(text: string) {
    setView('main')
    sendMain(text)
  }

  function changeModel(id: string) {
    if (id === model) return
    setModel(id)
    pushMain(make('system', `تم التبديل إلى ${models.find((m) => m.id === id)?.label} — يُنصح بتسليم السياق`))
  }

  function completeHandover(target: string) {
    setModel(target)
    pushMain(make('system', `اكتمل تسليم السياق إلى ${models.find((m) => m.id === target)?.label}`))
  }

  const roomAgent = view !== 'main' ? agentMap[view] : null

  return (
    <div className="flex h-dvh flex-col overflow-hidden">
      <TopHeader
        model={model}
        onModelChange={changeModel}
        onHandover={() => setDialog('handover')}
        onReports={() => setDialog('reports')}
        onAchievements={() => setDialog('achievements')}
      />

      <div className="flex min-h-0 flex-1">
        <AgentsSidebar view={view} onNavigate={navigate} unread={unread} activeAgents={activeAgents} />

        <main className="flex min-w-0 flex-1 flex-col">
          {roomAgent ? (
            <AgentRoom
              key={roomAgent.id}
              agent={roomAgent}
              messages={roomMessages[roomAgent.id]}
              typing={roomTyping[roomAgent.id]}
              guests={guests[roomAgent.id]}
              isActive={activeAgents.includes(roomAgent.id)}
              onBack={() => navigate('main')}
              onSend={(t) => sendRoom(roomAgent.id, t)}
              onInvite={(g) => invite(roomAgent.id, g)}
              onToggleActive={() => toggleAgent(roomAgent.id)}
              onEscalate={delegateToMarwa}
            />
          ) : (
            <>
              <AgentControlBar
                autoMode={autoMode}
                onAutoModeChange={setAutoMode}
                activeAgents={activeAgents}
                onToggleAgent={toggleAgent}
              />
              <MainChat
                messages={mainMessages}
                typing={mainTyping}
                onSend={sendMain}
                onAction={handleMainAction}
                autoMode={autoMode}
              />
            </>
          )}
        </main>

        <NotebookPanel onDelegate={delegateToMarwa} />
      </div>

      <ReportsDialog open={dialog === 'reports'} onOpenChange={(v) => setDialog(v ? 'reports' : null)} />
      <AchievementsDialog open={dialog === 'achievements'} onOpenChange={(v) => setDialog(v ? 'achievements' : null)} />
      <HandoverDialog
        open={dialog === 'handover'}
        onOpenChange={(v) => setDialog(v ? 'handover' : null)}
        currentModel={model}
        messageCount={mainMessages.length}
        activeCount={activeAgents.length}
        onComplete={completeHandover}
      />
    </div>
  )
}
