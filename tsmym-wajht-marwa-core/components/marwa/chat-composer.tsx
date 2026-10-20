'use client'

import { useId, useState } from 'react'
import { ArrowUp, Paperclip } from 'lucide-react'
import { Button } from '@/components/ui/button'

export function ChatComposer({
  placeholder,
  onSend,
  hint,
}: {
  placeholder: string
  onSend: (text: string) => void
  hint?: React.ReactNode
}) {
  const [value, setValue] = useState('')
  const id = useId()

  function submit() {
    const text = value.trim()
    if (!text) return
    onSend(text)
    setValue('')
  }

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        submit()
      }}
      className="rounded-xl border border-border bg-card p-2 focus-within:border-foreground/20"
    >
      <label htmlFor={id} className="sr-only">
        {placeholder}
      </label>
      <textarea
        id={id}
        rows={2}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && !e.shiftKey) {
            if (e.nativeEvent.isComposing || e.keyCode === 229) return
            e.preventDefault()
            submit()
          }
        }}
        placeholder={placeholder}
        className="w-full resize-none bg-transparent px-2 py-1.5 text-sm leading-relaxed text-foreground outline-none placeholder:text-muted-foreground"
      />
      <div className="flex items-center justify-between gap-2 px-1">
        <div className="flex min-w-0 items-center gap-2 text-xs text-muted-foreground">
          <Button type="button" variant="ghost" size="icon-sm" aria-label="إرفاق ملف">
            <Paperclip />
          </Button>
          <span className="truncate">{hint}</span>
        </div>
        <Button type="submit" size="icon-sm" disabled={!value.trim()} aria-label="إرسال">
          <ArrowUp />
        </Button>
      </div>
    </form>
  )
}
