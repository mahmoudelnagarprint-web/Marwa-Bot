'use client'

import { useState } from 'react'
import { AlertOctagon, Check, Clock, NotebookPen, Plus, RefreshCw, Send, StickyNote, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

type Category = 'urgent' | 'warning' | 'sync' | 'note'

type NoteItem = {
  id: string
  category: Category
  title: string
  body?: string
  people?: { name: string; count: number }[]
  delegate?: string
  done?: boolean
}

const categoryMeta: Record<Category, { label: string; icon: typeof AlertOctagon; style: string; iconStyle: string }> = {
  urgent: { label: 'عاجل', icon: AlertOctagon, style: 'border-rose-400/20 bg-rose-400/[0.06]', iconStyle: 'text-rose-300' },
  warning: { label: 'تنبيه', icon: Clock, style: 'border-amber-400/20 bg-amber-400/[0.05]', iconStyle: 'text-amber-300' },
  sync: { label: 'مزامنة', icon: RefreshCw, style: 'border-border bg-card', iconStyle: 'text-sky-300' },
  note: { label: 'ملاحظة', icon: StickyNote, style: 'border-border bg-card', iconStyle: 'text-muted-foreground' },
}

// مُطهَّر (task-2 فيجن): لا ملاحظات أو تنبيهات متخيلة — الدفتر يبدأ فارغاً
// وتُملأ عناصره من التسجيلات الحقيقية. حالة المزامنة تعرض «بانتظار الربط»
// حتى تفعيل النبض الحي بالمرحلة 3 (FARES_CFO_STATE §6) — لا ادعاء مزامنة غير مثبتة.
const initialItems: NoteItem[] = []

const syncNodes = [
  { name: 'LAPTOP', label: 'هذا الجهاز', progress: 0, state: 'بانتظار الربط الحي' },
  { name: 'OFFICE', label: 'المكتب', progress: 0, state: 'بانتظار الربط' },
  { name: 'STORE', label: 'المخزن', progress: 0, state: 'بانتظار الربط' },
  { name: 'CLOUD', label: 'السحابة', progress: 0, state: 'بانتظار الربط' },
]

const filters: { id: 'all' | Category; label: string }[] = [
  { id: 'all', label: 'الكل' },
  { id: 'urgent', label: 'عاجل' },
  { id: 'warning', label: 'تنبيه' },
  { id: 'sync', label: 'مزامنة' },
  { id: 'note', label: 'ملاحظات' },
]

export function NotebookPanel({ onDelegate }: { onDelegate: (text: string) => void }) {
  const [items, setItems] = useState(initialItems)
  const [filter, setFilter] = useState<'all' | Category>('all')
  const [adding, setAdding] = useState(false)
  const [draft, setDraft] = useState('')
  const [syncing, setSyncing] = useState(false)

  const visible = items.filter((i) => filter === 'all' || i.category === filter)
  const openUrgent = items.filter((i) => i.category === 'urgent' && !i.done).length

  function addNote() {
    const title = draft.trim()
    if (!title) return
    setItems((prev) => [{ id: crypto.randomUUID(), category: 'note', title }, ...prev])
    setDraft('')
    setAdding(false)
  }

  function toggleDone(id: string) {
    setItems((prev) => prev.map((i) => (i.id === id ? { ...i, done: !i.done } : i)))
  }

  function triggerSync() {
    // لا مزامنة وهمية: زر مزامنة الآن معطّل حتى تفعيل النبض الحي (المرحلة 3)
    setSyncing(true)
    setTimeout(() => setSyncing(false), 600)
  }

  return (
    <aside className="hidden w-80 shrink-0 flex-col border-e border-border bg-sidebar xl:flex" aria-label="النوت بوك">
      <div className="flex items-center justify-between gap-2 border-b border-border px-4 py-3">
        <div className="flex items-center gap-2">
          <NotebookPen className="size-4 text-muted-foreground" aria-hidden="true" />
          <h2 className="text-sm font-semibold">النوت بوك</h2>
          {openUrgent > 0 && (
            <span className="rounded-full bg-rose-400/15 px-1.5 text-[11px] font-medium text-rose-300">{openUrgent} عاجل</span>
          )}
        </div>
        <Button variant="ghost" size="icon-sm" onClick={() => setAdding((v) => !v)} aria-label="إضافة ملاحظة">
          {adding ? <X /> : <Plus />}
        </Button>
      </div>

      <div className="flex gap-1 overflow-x-auto border-b border-border px-3 py-2 scrollbar-thin" role="group" aria-label="تصفية">
        {filters.map((f) => (
          <button
            key={f.id}
            type="button"
            aria-pressed={filter === f.id}
            onClick={() => setFilter(f.id)}
            className={cn(
              'shrink-0 rounded-md px-2 py-1 text-xs transition-colors',
              filter === f.id ? 'bg-sidebar-accent text-foreground' : 'text-muted-foreground hover:text-foreground',
            )}
          >
            {f.label}
          </button>
        ))}
      </div>

      <div className="flex min-h-0 flex-1 flex-col gap-2.5 overflow-y-auto p-3 scrollbar-thin">
        {adding && (
          <div className="rounded-xl border border-foreground/15 bg-card p-2">
            <label htmlFor="new-note" className="sr-only">
              ملاحظة جديدة
            </label>
            <textarea
              id="new-note"
              autoFocus
              rows={2}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  if (e.nativeEvent.isComposing || e.keyCode === 229) return
                  e.preventDefault()
                  addNote()
                }
              }}
              placeholder="اكتب ملاحظة سريعة..."
              className="w-full resize-none bg-transparent px-1 text-sm outline-none placeholder:text-muted-foreground"
            />
            <div className="flex justify-end">
              <Button size="xs" onClick={addNote} disabled={!draft.trim()}>
                حفظ
              </Button>
            </div>
          </div>
        )}

        {visible.map((item) => {
          const meta = categoryMeta[item.category]
          return (
            <article
              key={item.id}
              className={cn('rounded-xl border p-3 transition-opacity', meta.style, item.done && 'opacity-50')}
            >
              <header className="flex items-start justify-between gap-2">
                <div className="flex items-center gap-2">
                  <meta.icon className={cn('size-3.5 shrink-0', meta.iconStyle)} aria-hidden="true" />
                  <h3 className={cn('text-sm font-medium', item.done && 'line-through')}>{item.title}</h3>
                </div>
                <button
                  type="button"
                  onClick={() => toggleDone(item.id)}
                  aria-label={item.done ? 'إلغاء الإنجاز' : 'تم'}
                  className={cn(
                    'flex size-5 shrink-0 items-center justify-center rounded border transition-colors',
                    item.done ? 'border-emerald-400/30 bg-emerald-400/15 text-emerald-300' : 'border-border hover:bg-accent',
                  )}
                >
                  {item.done && <Check className="size-3" />}
                </button>
              </header>
              {item.body && <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">{item.body}</p>}
              {item.people && (
                <ul className="mt-2.5 flex flex-col gap-1">
                  {item.people.map((p) => (
                    <li key={p.name} className="flex items-center justify-between rounded-md bg-background/50 px-2 py-1 text-xs">
                      <span>{p.name}</span>
                      <span className={cn('font-mono tabular-nums', meta.iconStyle)}>{p.count}</span>
                    </li>
                  ))}
                </ul>
              )}
              {item.delegate && !item.done && (
                <Button
                  variant="outline"
                  size="xs"
                  className="mt-2.5 w-full gap-1.5"
                  onClick={() => {
                    onDelegate(item.delegate!)
                    toggleDone(item.id)
                  }}
                >
                  <Send className="size-3" aria-hidden="true" />
                  إحالة لمروة
                </Button>
              )}
            </article>
          )
        })}

        {(filter === 'all' || filter === 'sync') && (
          <article className={cn('rounded-xl border p-3', categoryMeta.sync.style)}>
            <header className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <RefreshCw
                  className={cn('size-3.5', categoryMeta.sync.iconStyle, syncing && 'animate-spin')}
                  aria-hidden="true"
                />
                <h3 className="text-sm font-medium">حالة المزامنة</h3>
              </div>
              <Button variant="ghost" size="xs" onClick={triggerSync} disabled>
                مزامنة الآن — تُفعَّل بالمرحلة 3
              </Button>
            </header>
            <ul className="mt-2.5 flex flex-col gap-2">
              {syncNodes.map((n) => {
                const progress = syncing ? Math.min(100, n.progress + 10) : n.progress
                const lagging = progress < 100
                return (
                  <li key={n.name}>
                    <div className="flex items-center justify-between text-xs">
                      <span className="flex items-center gap-1.5">
                        <span className="font-mono text-[11px] text-muted-foreground" dir="ltr">
                          {n.name}
                        </span>
                        {n.label}
                      </span>
                      <span className={lagging ? 'text-amber-300' : 'text-muted-foreground'}>
                        {lagging ? n.state : 'متزامن'}
                      </span>
                    </div>
                    <div className="mt-1 h-1 overflow-hidden rounded-full bg-muted">
                      <div
                        className={cn('h-full rounded-full transition-all duration-700', lagging ? 'bg-amber-300/70' : 'bg-sky-300/60')}
                        style={{ width: `${progress}%` }}
                      />
                    </div>
                  </li>
                )
              })}
            </ul>
          </article>
        )}

        {visible.length === 0 && filter !== 'sync' && (
          <p className="py-8 text-center text-xs text-muted-foreground">لا توجد عناصر في هذا التصنيف.</p>
        )}
      </div>
    </aside>
  )
}
