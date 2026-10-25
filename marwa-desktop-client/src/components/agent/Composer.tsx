'use client'

// components/agent/Composer.tsx — صندوق الكتابة (Enter إرسال • Shift+Enter سطر جديد)
import { useState } from 'react'
import { Send } from 'lucide-react'
import { cn } from '@/lib/utils'

export function Composer({
  placeholder,
  disabled,
  onSend,
}: {
  placeholder: string
  disabled?: boolean
  onSend: (text: string) => void
}) {
  const [text, setText] = useState('')

  const submit = () => {
    const t = text.trim()
    if (!t || disabled) return
    onSend(t)
    setText('')
  }

  return (
    <div className="flex items-end gap-2 border-t border-matte-700 bg-matte-900/80 p-3 backdrop-blur">
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault()
            submit()
          }
        }}
        placeholder={placeholder}
        rows={1}
        className="max-h-32 min-h-11 w-full resize-none rounded-xl border border-matte-600 bg-matte-850 px-4 py-3 text-sm text-foreground outline-none transition-colors placeholder:text-matte-600 focus:border-gold-600 scrollbar-thin"
      />
      <button
        type="button"
        onClick={submit}
        disabled={disabled || !text.trim()}
        className="flex h-11 shrink-0 items-center gap-2 rounded-xl bg-gold-400 px-4 text-sm font-bold text-matte-950 transition-all hover:bg-gold-300 disabled:opacity-40"
      >
        <Send className="size-4 rotate-180" aria-hidden="true" />
        إرسال
      </button>
    </div>
  )
}
