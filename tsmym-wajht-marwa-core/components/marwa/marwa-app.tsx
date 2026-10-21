'use client'

import { useEffect, useState } from 'react'
import {
  agentMap,
  agents,
  initialMainMessages,
  nowTime,
  type AgentId,
  type Message,
} from '@/lib/marwa-data'
import { NotebookPen, Users } from 'lucide-react'
import { TopHeader } from './top-header'
import { AgentControlBar } from './agent-control-bar'
import { AgentsSidebar } from './agents-sidebar'
import { NotebookPanel } from './notebook-panel'
import { MainChat } from './main-chat'
import { AgentRoom } from './agent-room'
import { ReportsDialog } from './reports-dialog'
import { AchievementsDialog } from './achievements-dialog'
import { SettingsDialog } from './settings-dialog'
import { supabase, supabaseConfigured } from '@/lib/supabase'
import { subscribeUrgentAlerts, buildAlertText, type AlertRow } from '@/lib/agent-alerts'

type View = 'main' | AgentId
type DialogId = 'reports' | 'achievements' | 'settings' | null

const agentIds = agents.map((a) => a.id)

function byAgent<T>(make: (id: AgentId) => T) {
  return Object.fromEntries(agentIds.map((id) => [id, make(id)])) as Record<AgentId, T>
}

// تطهير (أمر المالك 2026-10-21): الردود المعلبة marwaLines وnextReply حُذفت —
// كل رد يأتي من مزود الذكاء الحي عبر /api/chat، وعند غياب المزود رسالة نظام
// صادقة توجّه لـ ⚙️ الإعدادات العامة (لا محاكاة ولا نصوص متخيلة).

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
  const [isMounted, setIsMounted] = useState(false)
  useEffect(() => {
    setIsMounted(true)
  }, [])
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
  // أمر المالك 2026-10-21: الأشرطة الجانبية قابلة للطي — الافتراضي مغلق لتوسيع الشات
  const [rightOpen, setRightOpen] = useState(false)
  const [leftOpen, setLeftOpen] = useState(false)

  const make = (author: Message['author'], text: string, actions?: string[], meta?: { model: string; ms: number }): Message => ({
    id: crypto.randomUUID(),
    author,
    text,
    time: nowTime(),
    actions: actions?.map((label) => ({ id: crypto.randomUUID(), label })),
    meta,
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

  /** الشات الحي عبر بوابة الذكاء الاصطناعي (Enterprise AI Gateway).
   * 'ai' = رد حي من مزود • 'noprovider' = لا مزودين — رسالة نظام صادقة • 'error' = فشل مُعلن.
   * تطهير 2026-10-21: لا محاكاة ولا ردود معلبة بعد اليوم. */
  async function askAI(
    agentKey: AgentId | 'marwa',
    history: Message[],
    push: (m: Message) => void,
  ): Promise<'ai' | 'noprovider' | 'error'> {
    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          agent: agentKey,
          messages: history.slice(-10).map((m) => ({
            role: m.author === 'user' ? 'user' : 'assistant',
            content: m.text,
          })),
        }),
      })
      const j = (await res.json()) as {
        ok?: boolean; text?: string; reason?: string; compacted?: boolean
        provider?: { name?: string; model?: string }; latency_ms?: number
      }
      if (j.ok && j.text) {
        // شارة هوية النموذج وزمن الاستجابة — من المزود الفعلي فقط (أمر المالك 2026-10-21)
        const meta = j.provider?.model
          ? { model: j.provider.model, ms: j.latency_ms ?? 0 }
          : undefined
        push(make(agentKey as Message['author'], j.text, undefined, meta))
        if (j.compacted) push(make('system', '🗜️ السجل كان أطول من حد المزود — اتعمل له Auto-Compact تلقائياً (ملخص الحالة + آخر الرسائل)'))
        return 'ai'
      }
      if ((j.reason ?? '').includes('لا مزودين')) return 'noprovider'
      push(make('system', `⚠️ ${j.reason ?? 'محرك الذكاء غير متاح'} — راجع «أسطول الذكاء» في ⚙️ الإعدادات العامة`))
      return 'error'
    } catch {
      push(make('system', '⚠️ فشل الاتصال بمحرك الشات — أعد المحاولة'))
      return 'error'
    }
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
    if (newlyActivated.length) activate(newlyActivated)

    // الشات الحي حصرياً (تطهير 2026-10-21): الرد من مزود الأسطول — لا محاكاة
    const history = [...mainMessages, make('user', text)]
    setMainTyping('marwa')
    void (async () => {
      const mode = await askAI('marwa', history, pushMain)
      setMainTyping(null)
      if (mode === 'noprovider') {
        pushMain(make('system', 'لم يُضف مزود ذكاء اصطناعي بعد — افتح ⚙️ الإعدادات العامة وأضف مزوداً ليعمل الشات الحي.'))
      }
    })()
  }

  function handleMainAction(messageId: string, actionId: string, label: string) {
    setMainMessages((prev) =>
      prev.map((m) =>
        m.id === messageId
          ? { ...m, actions: m.actions?.map((a) => (a.id === actionId ? { ...a, done: true } : a)) }
          : m,
      ),
    )
    // تطهير 2026-10-21: لا رد معلب — الإجراء يمر كطلب حقيقي إلى الذكاء الحي
    const mentioned = agents.filter((a) => label.includes(a.name)).map((a) => a.id)
    if (mentioned.length > 1) {
      activate(mentioned)
      pushMain(make('system', `تم تفعيل ${mentioned.map((id) => agentMap[id].name).join(' و')} في الشات`))
    }
    sendMain(label)
  }

  /** تعديل رسالة المالك وإعادة إرسالها — يقصّ السياق من نقطة التعديل ويحدّثه (أمر المالك 2026-10-21) */
  function editMain(messageId: string, newText: string) {
    const idx = mainMessages.findIndex((m) => m.id === messageId)
    if (idx === -1) return
    setMainMessages((prev) => prev.slice(0, idx))
    sendMain(newText)
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
    // الشات الحي حصرياً (تطهير 2026-10-21) — لا محاكاة
    const history = [...roomMessages[room], make('user', text)]
    setRoomTyping((prev) => ({ ...prev, [room]: agentMap[room].name }))
    void (async () => {
      const mode = await askAI(room, history, (m) => pushRoom(room, m))
      setRoomTyping((prev) => ({ ...prev, [room]: null }))
      if (mode === 'noprovider') {
        pushRoom(room, make('system', 'لم يُضف مزود ذكاء اصطناعي بعد — افتح ⚙️ الإعدادات العامة وأضف مزوداً ليعمل الشات الحي.'))
      }
    })()
  }

  /** تعديل رسالة المالك داخل غرفة وكيل — يقصّ السياق من نقطة التعديل (أمر المالك 2026-10-21) */
  function editRoom(room: AgentId, messageId: string, newText: string) {
    const list = roomMessages[room]
    const idx = list.findIndex((m) => m.id === messageId)
    if (idx === -1) return
    setRoomMessages((prev) => ({ ...prev, [room]: prev[room].slice(0, idx) }))
    sendRoom(room, newText)
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

  // تطهير 2026-10-21: changeModel/completeHandover حُذفا — قائمة الموديلات الوهمية
  // (Claude/GPT-5/Gemini) ومسرحية Handover أصبحا بلا معنى؛ المزود الفعلي يُدار
  // من ⚙️ الإعدادات العامة والشارة الحية في الشريط العلوي.

  const roomAgent = view !== 'main' ? agentMap[view] : null

  if (!isMounted) {

    return (

      <div className="flex h-dvh flex-col items-center justify-center bg-background text-foreground" suppressHydrationWarning>

        <div className="flex items-center gap-3 text-sm text-muted-foreground" suppressHydrationWarning>

          <span className="size-4 animate-spin rounded-full border-2 border-sky-400 border-t-transparent" />

          <span>جاري تهيئة منظومة مروة كور…</span>

        </div>

      </div>

    )

  }


  return (

    <div className="flex h-dvh flex-col overflow-hidden" suppressHydrationWarning>
      <TopHeader
        onReports={() => setDialog('reports')}
        onAchievements={() => setDialog('achievements')}
        onOpenSettings={() => setDialog('settings')}
      />

      <div className="flex min-h-0 flex-1">
        {/* البار الأيمن (الوكلاء) — قابل للطي، الافتراضي مغلق (أمر المالك 2026-10-21) */}
        {rightOpen ? (
          <AgentsSidebar view={view} onNavigate={navigate} unread={unread} activeAgents={activeAgents} onCollapse={() => setRightOpen(false)} />
        ) : (
          <button
            type="button"
            onClick={() => setRightOpen(true)}
            aria-label="فتح قائمة الوكلاء"
            title="قائمة الوكلاء"
            className="flex w-9 shrink-0 flex-col items-center gap-3 border-e border-border bg-sidebar py-3 text-muted-foreground transition-colors hover:text-foreground"
          >
            <Users className="size-4" aria-hidden="true" />
            <span className="text-[10px] font-medium [writing-mode:vertical-rl]">الوكلاء</span>
          </button>
        )}

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
              onEdit={(mid, t) => editRoom(roomAgent.id, mid, t)}
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
                onEdit={editMain}
                autoMode={autoMode}
              />
            </>
          )}
        </main>

        {/* البار الأيسر (النوت بوك) — قابل للطي، الافتراضي مغلق */}
        {leftOpen ? (
          <NotebookPanel onDelegate={delegateToMarwa} onCollapse={() => setLeftOpen(false)} />
        ) : (
          <button
            type="button"
            onClick={() => setLeftOpen(true)}
            aria-label="فتح النوت بوك"
            title="النوت بوك"
            className="flex w-9 shrink-0 flex-col items-center gap-3 border-s border-border bg-sidebar py-3 text-muted-foreground transition-colors hover:text-foreground"
          >
            <NotebookPen className="size-4" aria-hidden="true" />
            <span className="text-[10px] font-medium [writing-mode:vertical-rl]">النوت بوك</span>
          </button>
        )}
      </div>

      <ReportsDialog open={dialog === 'reports'} onOpenChange={(v) => setDialog(v ? 'reports' : null)} />
      <AchievementsDialog open={dialog === 'achievements'} onOpenChange={(v) => setDialog(v ? 'achievements' : null)} />
      <SettingsDialog open={dialog === 'settings'} onOpenChange={(v) => setDialog(v ? 'settings' : null)} />
    </div>
  )
}
