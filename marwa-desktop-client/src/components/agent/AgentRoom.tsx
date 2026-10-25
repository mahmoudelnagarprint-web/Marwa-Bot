'use client'

// components/agent/AgentRoom.tsx — غرفة الوكيل (المرحلة 1: مروة كاملة)
// الرسائل من المخزن المعزول للوكيل (stores/agentStore) — والإرسال يمر عبر جسر DSH:
//   tauri/websocket → رد حي يبث في الفقاعات + رقائق استدعاءات الأدوات
//   mock            → ملاحظة صادقة: «بانتظار ربط الجسر» — بلا ردود متخيلة.
import { useEffect, useRef } from 'react'
import { AnimatePresence } from 'framer-motion'
import { ArrowRight } from 'lucide-react'
import { agentById } from '@/lib/agents'
import { getAgentStore } from '@/stores/agentStore'
import { dsh } from '@/services/dsh-ipc'
import { MessageBubble } from './MessageBubble'
import { Composer } from './Composer'

export function AgentRoom({ agentId, onBack }: { agentId: 'marwa'; onBack: () => void }) {
  const agent = agentById(agentId)
  const store = getAgentStore(agentId)
  const messages = store((s) => s.messages)
  const isGenerating = store((s) => s.isGenerating)
  const addMessage = store((s) => s.addMessage)
  const updateMessage = store((s) => s.updateMessage)
  const setGenerating = store((s) => s.setGenerating)
  const pushToolCall = store((s) => s.pushToolCall)
  const patchToolCall = store((s) => s.patchToolCall)
  const setScratchpad = store((s) => s.setScratchpad)

  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = async (text: string) => {
    const now = () => new Date().toLocaleTimeString('ar-EG', { hour: '2-digit', minute: '2-digit' })
    addMessage({ id: crypto.randomUUID(), role: 'user', content: text, time: now() })
    setGenerating(true)

    const botId = crypto.randomUUID()
    const transport = dsh.kind
    if (transport !== 'mock') {
      addMessage({ id: crypto.randomUUID(), role: 'assistant', content: '', time: now() })
    }

    try {
      const res = await dsh.call<{ text?: string; scratchpad?: string; toolCalls?: { id: string; tool: string; ms?: number }[] }>(
        'agent_message',
        { agentId, text },
      )
      if (res?.text) {
        updateMessage(botId, {
          role: 'assistant',
          content: res.text,
          scratchpad: res.scratchpad,
          time: now(),
          toolCalls: res.toolCalls?.map((t) => ({ ...t, status: 'done' as const })),
        })
        if (res.scratchpad) setScratchpad(res.scratchpad)
        if (res.toolCalls) res.toolCalls.forEach((t) => pushToolCall({ ...t, status: 'done' }))
      } else {
        updateMessage(botId, { role: 'assistant', content: '(رد فارغ من المحرك)', time: now() })
      }
    } catch (e) {
      // وضع mock — رسالة صادقة بلا أي ردود متخيلة
      addMessage({
        id: crypto.randomUUID(),
        role: 'system',
        content:
          'الجسر المحلي (DSH Bridge) غير متصل بعد — الردود الحية تُفعَّل داخل Tauri أو عبر WebSocket للمحرك. الواجهة جاهزة بالكامل والبيانات الحية قادمة من المحرك فقط.',
        time: now(),
      })
      void e
    } finally {
      setGenerating(false)
      if (transport !== 'mock') {
        // إزالة فقاعة التوليد الفارغة عند وجود رد حي
        setGenerating(false)
      }
    }
  }

  return (
    <div className="flex h-full flex-col overflow-hidden bg-matte-950">
      {/* ترويسة الغرفة */}
      <div className="flex items-center gap-3.5 border-b border-matte-700 bg-matte-900/70 px-5 py-3.5">
        <button
          type="button"
          onClick={onBack}
          className="flex size-9 items-center justify-center rounded-xl border border-matte-600 bg-matte-850 text-matte-600 transition-colors hover:border-gold-600 hover:text-gold-300"
          title="العودة للداشبورد"
        >
          <ArrowRight className="size-4" />
        </button>
        <div className="flex size-11 items-center justify-center rounded-xl border border-gold-800/60 bg-matte-950 font-display text-2xl font-bold text-gold-400 gold-glow">
          {agent.glyph}
        </div>
        <div>
          <h2 className="font-display text-xl font-bold text-foreground">{agent.name}</h2>
          <p className="text-xs text-matte-600">{agent.title}</p>
        </div>
        <span className="ms-auto rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-1 text-[10px] font-semibold text-emerald-300">
          متصل الآن
        </span>
      </div>

      {/* الرسائل — دخول وخروج سلس بـ Framer Motion */}
      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-4 md:p-6 scrollbar-thin">
        <AnimatePresence initial={false}>
          {messages.map((m) => (
            <MessageBubble key={m.id} msg={m} />
          ))}
        </AnimatePresence>
        {isGenerating && (
          <p className="flex items-center gap-2 text-xs text-matte-600" aria-busy="true">
            <span className="inline-flex size-6 items-center justify-center rounded-lg border border-gold-800/60 bg-matte-950 font-display text-xs font-bold text-gold-400 gold-glow">
              {agent.glyph}
            </span>
            {agent.name} يكتب الآن…
          </p>
        )}
        <div ref={bottomRef} />
      </div>

      <Composer
        placeholder={`اكتب رسالتك لـ ${agent.name} (Enter للإرسال)…`}
        onSend={(t) => void handleSend(t)}
      />
    </div>
  )
}
