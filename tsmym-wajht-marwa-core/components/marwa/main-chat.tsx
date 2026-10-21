'use client'

import { useEffect, useRef } from 'react'
import type { Message } from '@/lib/marwa-data'
import { ChatMessage, TypingIndicator } from './chat-message'
import { ChatComposer } from './chat-composer'

export function MessageList({
  messages,
  typing,
  onAction,
  onEdit,
}: {
  messages: Message[]
  typing: Message['author'] | null
  onAction?: (messageId: string, actionId: string, label: string) => void
  onEdit?: (messageId: string, newText: string) => void
}) {
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages.length, typing])

  return (
    <div className="min-h-0 flex-1 overflow-y-auto scrollbar-thin" role="log" aria-live="polite">
      <div className="mx-auto flex max-w-3xl flex-col gap-5 px-5 py-6">
        {messages.map((m) => (
          <ChatMessage key={m.id} message={m} onAction={onAction} onEdit={onEdit} />
        ))}
        {typing && <TypingIndicator author={typing} />}
        <div ref={endRef} />
      </div>
    </div>
  )
}

export function MainChat({
  messages,
  typing,
  onSend,
  onAction,
  onEdit,
  autoMode,
}: {
  messages: Message[]
  typing: Message['author'] | null
  onSend: (text: string) => void
  onAction: (messageId: string, actionId: string, label: string) => void
  onEdit: (messageId: string, newText: string) => void
  autoMode: boolean
}) {
  return (
    <section className="flex min-h-0 flex-1 flex-col" aria-label="الشات الرئيسي">
      <MessageList messages={messages} typing={typing} onAction={onAction} onEdit={onEdit} />
      <div className="mx-auto w-full max-w-3xl px-5 pb-5">
        <ChatComposer
          placeholder="اكتب لمروة... مثلاً: اعرض دخل أكتوبر والآجل الحالي من البرنامج"
          onSend={onSend}
          hint={autoMode ? 'وضع أوتو: مروة ستستدعي الوكلاء المناسبين تلقائياً' : 'يرد فقط الوكلاء المفعّلون يدوياً'}
        />
      </div>
    </section>
  )
}
