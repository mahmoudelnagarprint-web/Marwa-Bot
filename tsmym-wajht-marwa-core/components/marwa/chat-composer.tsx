'use client'

import { useId, useMemo, useRef, useState } from 'react'
import { ArrowUp, Paperclip, SlashSquare } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

/** أوامر السلاش المتاحة (Workspace OS) */
const SLASH_COMMANDS = [
  { cmd: '/task', desc: 'إسناد مهمة: /task @agent التفاصيل — تهبط في inbox_tasks وتُدفع لـSupabase' },
  { cmd: '/summon', desc: 'استدعاء وكيل فوراً: /summon @agent' },
  { cmd: '/status', desc: 'حالة الوكيل: /status @agent — ملفات العمل النشطة والمهام المعلقة' },
] as const

/** الوكلاء التسعة (alias نفسه الذي يتوقعه router_daemon) */
const AGENTS = [
  '@marwa', '@fares', '@salma', '@bebo', '@sasa',
  '@vision', '@koko', '@hakim', '@afkar',
] as const

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
  const [highlight, setHighlight] = useState(0)
  const taRef = useRef<HTMLTextAreaElement>(null)
  const id = useId()

  // حالة المنسدلة: من نوع أيٍّ يُظهرها؟ 'cmd' عند كتابة / أول السطر، 'agent' عند @ في النص
  const suggestionType: 'cmd' | 'agent' | null = useMemo(() => {
    const v = value
    if (v.trimStart().startsWith('/') && !v.includes(' ')) return 'cmd'
    const at = v.lastIndexOf('@')
    if (at >= 0 && !/\s/.test(v.slice(at + 1))) return 'agent'
    return null
  }, [value])

  const suggestions: readonly { label: string; desc?: string; insert: string }[] = useMemo(() => {
    if (suggestionType === 'cmd') {
      const typed = value.trimStart().slice(1).toLowerCase()
      return SLASH_COMMANDS
        .filter((c) => c.cmd.slice(1).startsWith(typed))
        .map((c) => ({ label: c.cmd, desc: c.desc, insert: `${c.cmd} ` }))
    }
    if (suggestionType === 'agent') {
      const typed = value.slice((value.lastIndexOf('@')) + 1).toLowerCase()
      return AGENTS.filter((a) => a.slice(1).startsWith(typed))
        .map((a) => ({ label: a, desc: 'وكيل', insert: `${a} ` }))
    }
    return []
  }, [suggestionType, value])

  function applySuggestion(input: { insert: string }) {
    const v = value
    if (suggestionType === 'agent') {
      const at = v.lastIndexOf('@')
      // استبدل من آخر @ حتى نهاية الإدخال بالغطاء الكامل
      setValue(v.slice(0, at) + input.insert)
    } else {
      // أوامر السلاش: استبدل من أول / في أول كلمة
      const firstSpace = v.indexOf(' ')
      setValue((firstSpace >= 0 ? v.slice(firstSpace + 1) : '') + input.insert)
    }
    requestAnimationFrame(() => taRef.current?.focus())
    setHighlight(0)
  }

  function submit() {
    const text = value.trim()
    if (!text) return
    onSend(text)
    setValue('')
    setHighlight(0)
  }

  const open = suggestions.length > 0 && (
    // لا تفتح المنسدلة المساعدة عندما يكون الأمر كاملاً ثم واكب الوكيل بلا وكيل بعد
    !(suggestionType === 'cmd' && value.trim().split(/\s+/).length > 1)
  )

  return (
    <div className="relative">
      {open ? (
        <ul
          role="listbox"
          aria-label="اقتراحات أوامر السلاش"
          className="absolute bottom-full z-50 mb-2 w-full overflow-hidden rounded-lg border border-border bg-popover/95 shadow-lg backdrop-blur"
        >
          {suggestions.map((s, i) => (
            <li key={s.label} role="option" aria-selected={i === highlight}>
              <button
                type="button"
                tabIndex={-1}
                onMouseDown={(e) => {
                  e.preventDefault() // لا تفقد تركيز الـtextarea
                  applySuggestion(s)
                }}
                onMouseEnter={() => setHighlight(i)}
                className={cn(
                  'flex w-full items-center gap-2 px-3 py-2 text-right text-sm',
                  i === highlight ? 'bg-accent text-accent-foreground' : 'hover:bg-accent/60',
                )}
              >
                <SlashSquare className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                <span className="font-mono shrink-0">{s.label}</span>
                {s.desc && <span className="truncate text-xs text-muted-foreground">{s.desc}</span>}
              </button>
            </li>
          ))}
        </ul>
      ) : null}

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
          ref={taRef}
          id={id}
          rows={2}
          value={value}
          onChange={(e) => {
            setValue(e.target.value)
            setHighlight(0)
          }}
          onKeyDown={(e) => {
            if (open && suggestions.length > 0) {
              if (e.key === 'ArrowDown') {
                e.preventDefault()
                setHighlight((h) => (h + 1) % suggestions.length)
                return
              }
              if (e.key === 'ArrowUp') {
                e.preventDefault()
                setHighlight((h) => (h - 1 + suggestions.length) % suggestions.length)
                return
              }
              if (e.key === 'Tab' || (e.key === 'Enter' && !e.shiftKey)) {
                e.preventDefault()
                applySuggestion(suggestions[highlight])
                return
              }
              if (e.key === 'Escape') {
                setValue(value + ' ') // كسر حالة الاقتراح دون فقدان النص
                return
              }
            }
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
    </div>
  )
}
