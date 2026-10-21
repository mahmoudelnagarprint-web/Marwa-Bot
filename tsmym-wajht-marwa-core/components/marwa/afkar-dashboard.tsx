'use client'

import { useCallback, useEffect, useState } from 'react'
import {
  Archive, Check, CirclePlus, Lightbulb, NotebookPen, PenLine, Plus, RefreshCw,
  Rocket, Search, Sparkles, StickyNote, Trash2, Undo2, Wand2, X,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

type Note = {
  id: number
  title: string
  body?: string
  category: string
  tags?: string[]
  project?: string | null
  status: 'open' | 'done' | 'trashed'
  created_at: string
  updated_at: string
  spawned?: { at: string; commands: string[] }[]
}

type Payload = {
  stats: Record<string, number>
  by_category: Record<string, Note[]>
  trashed: Note[]
  radar: { name: string; starts_in_months: number; ideas: { id: number; title: string; tags: string[] }[] }[]
  categories: string[]
}

const CATEGORY_META: Record<string, { label: string; icon: typeof Lightbulb; chip: string }> = {
  'فكرة منتج': { label: 'فكرة منتج', icon: Lightbulb, chip: 'border-fuchsia-400/25 bg-fuchsia-400/[0.08] text-fuchsia-200' },
  'برومبت تصميم': { label: 'برومبت تصميم', icon: Wand2, chip: 'border-violet-400/25 bg-violet-400/[0.08] text-violet-200' },
  'تجهيزات مواسم': { label: 'تجهيزات مواسم', icon: Sparkles, chip: 'border-amber-400/25 bg-amber-400/[0.08] text-amber-200' },
  'ملاحظة': { label: 'ملاحظة', icon: StickyNote, chip: 'border-border bg-card text-muted-foreground' },
  'مسودة': { label: 'مسودة', icon: PenLine, chip: 'border-border bg-card text-muted-foreground' },
}

const FILTERS = ['الكل', 'فكرة منتج', 'برومبت تصميم', 'تجهيزات مواسم', 'ملاحظة', 'مسودة'] as const
type Filter = (typeof FILTERS)[number]

export function AfkarDashboard() {
  const [data, setData] = useState<Payload | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<Filter>('الكل')
  const [query, setQuery] = useState('')
  const [adding, setAdding] = useState(false)
  const [title, setTitle] = useState('')
  const [body, setBody] = useState('')
  const [category, setCategory] = useState('فكرة منتج')
  const [tags, setTags] = useState('')
  const [busy, setBusy] = useState(false)
  const [flash, setFlash] = useState<string | null>(null)
  const [converting, setConverting] = useState<number | null>(null)
  const [showTrash, setShowTrash] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch('/api/afkar', { cache: 'no-store' })
      const j = (await res.json()) as Payload & { ok?: boolean; error?: string; note?: Note }
      // المحرك يرجع {ok, note} للتعديلات و{ok, stats, by_category,...} للوحة
      if (j.ok === false) throw new Error(j.error ?? 'رفض المحرك')
      if (j.stats) setData(j as Payload)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'فشل التحميل')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void load() }, [load])

  async function post(payload: Record<string, unknown>, okMsg: string) {
    setBusy(true)
    setFlash(null)
    try {
      const res = await fetch('/api/afkar', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const j = (await res.json()) as { ok?: boolean; error?: string }
      if (!j.ok) throw new Error(j.error ?? 'رفض المحرك')
      setFlash(okMsg)
      await load()
    } catch (e) {
      setFlash(e instanceof Error ? e.message : 'فشل الاتصال بمحرك أفكار')
    } finally {
      setBusy(false)
    }
  }

  function addIdea() {
    const t = title.trim()
    if (!t) return
    void post(
      { action: 'add', title: t, body: body.trim(), category, tags: tags.split(',').map((s) => s.trim()).filter(Boolean) },
      '💡 الفكرة اتسجلت في معمل أفكار',
    )
    setTitle('')
    setBody('')
    setTags('')
    setAdding(false)
  }

  async function convertIdea(n: Note) {
    setConverting(n.id)
    try {
      const res = await fetch('/api/afkar', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'convert_idea', id: n.id, title: n.title }),
      })
      const j = (await res.json()) as { dispatched?: number; total?: number; results?: { ok: boolean }[]; ok?: boolean }
      if (!j.ok) throw new Error('رفض محرك التوجيه')
      setFlash(
        `🚀 تحولت «${n.title}» لمشروع — ${j.dispatched ?? 0}/${j.total ?? 3} أمر وصل للوكلاء`,
      )
      await load()
    } catch {
      setFlash('⚠️ فشل الاتصال بمحرك التوجيه')
    } finally {
      setConverting(null)
    }
  }

  const all = data ? Object.values(data.by_category).flat() : []
  const visible = all.filter((n) => {
    if (filter !== 'الكل' && n.category !== filter) return false
    if (!query.trim()) return true
    const q = query.trim()
    return n.title.includes(q) || (n.body ?? '').includes(q) || (n.tags ?? []).some((t) => t.includes(q))
  })

  if (loading) {
    return (
      <div className="flex items-center gap-2 p-4 text-sm text-muted-foreground">
        <RefreshCw className="size-4 animate-spin" /> أفكار بتجمع الملاحظات من المعمل…
      </div>
    )
  }
  if (error || !data) {
    return (
      <div className="p-4 text-sm text-rose-300">
        ⚠️ {error ?? 'لا بيانات'}{' '}
        <Button variant="ghost" size="sm" onClick={() => void load()}>إعادة المحاولة</Button>
      </div>
    )
  }

  const kpis = [
    { label: 'أفكار مفتوحة', value: data.stats.open, icon: Lightbulb, tone: 'text-fuchsia-300 border-fuchsia-400/20 bg-fuchsia-400/10' },
    { label: 'أفكار منتجات', value: data.stats.products, icon: CirclePlus, tone: 'text-violet-300 border-violet-400/20 bg-violet-400/10' },
    { label: 'برومبتات تصميم', value: data.stats.prompts, icon: Wand2, tone: 'text-sky-300 border-sky-400/20 bg-sky-400/10' },
    { label: 'تجهيزات مواسم', value: data.stats.seasons, icon: Sparkles, tone: 'text-amber-300 border-amber-400/20 bg-amber-400/10' },
    { label: 'منفذة', value: data.stats.done, icon: Check, tone: 'text-emerald-300 border-emerald-400/20 bg-emerald-400/10' },
  ]

  return (
    <div className="flex flex-col gap-4 p-4">
      {flash && (
        <div className="flex items-center justify-between gap-2 rounded-xl border border-emerald-400/25 bg-emerald-400/[0.08] px-3 py-2 text-sm text-emerald-200">
          <span>{flash}</span>
          <button type="button" onClick={() => setFlash(null)} aria-label="إغلاق" className="text-emerald-300/70 hover:text-emerald-200">
            <X className="size-3.5" />
          </button>
        </div>
      )}

      {/* كروت علوية — نفس نظام باقي الغرف */}
      <div className="grid grid-cols-2 gap-2 md:grid-cols-5">
        {kpis.map((k) => (
          <div key={k.label} className={cn('rounded-xl border p-3', k.tone)}>
            <k.icon className="size-4" aria-hidden="true" />
            <p className="mt-2 text-lg font-semibold tabular-nums text-foreground">{k.value}</p>
            <p className="text-[11px] text-muted-foreground">{k.label}</p>
          </div>
        ))}
      </div>

      {/* رادار المواسم */}
      <div className="rounded-xl border border-amber-400/20 bg-amber-400/[0.05] p-3">
        <p className="flex items-center gap-2 text-sm font-medium text-amber-200">
          <Sparkles className="size-4" /> رادار المواسم — أقرب ثلاثة مواسم
        </p>
        <ul className="mt-2 grid grid-cols-1 gap-2 md:grid-cols-3">
          {data.radar.map((r) => (
            <li key={r.name} className="rounded-lg border border-border bg-card p-2.5">
              <p className="flex items-center justify-between text-sm">
                <span>{r.name}</span>
                <span className="text-[11px] text-muted-foreground tabular-nums">
                  {r.starts_in_months === 0 ? 'الجاري الآن' : `بعد ${r.starts_in_months} شهر`}
                </span>
              </p>
              {r.ideas.length > 0 ? (
                <ul className="mt-1.5 flex flex-col gap-1">
                  {r.ideas.map((i) => (
                    <li key={i.id} className="truncate text-xs text-foreground/80">• {i.title}</li>
                  ))}
                </ul>
              ) : (
                <p className="mt-1.5 text-[11px] text-muted-foreground">لا تجهيزات مسجلة بعد</p>
              )}
            </li>
          ))}
        </ul>
      </div>

      {/* شريط الأدوات: فلاتر + بحث + إضافة */}
      <div className="flex flex-wrap items-center gap-2">
        {FILTERS.map((f) => (
          <Button key={f} variant={filter === f ? 'default' : 'outline'} size="sm" onClick={() => setFilter(f)}>
            {f}
          </Button>
        ))}
        <div className="relative ms-auto min-w-40 flex-1 md:max-w-xs">
          <Search className="pointer-events-none absolute end-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="ابحث في المعمل…"
            aria-label="بحث في المعمل"
            className="w-full rounded-md border border-border bg-card py-1.5 pe-8 ps-3 text-sm outline-none placeholder:text-muted-foreground focus:border-fuchsia-400/40"
          />
        </div>
        <Button size="sm" onClick={() => setAdding((v) => !v)} className="gap-1.5">
          {adding ? <X className="size-3.5" /> : <Plus className="size-3.5" />}
          فكرة جديدة
        </Button>
      </div>

      {/* فورم الإضافة — يُملأ من هنا فقط (لا بيانات متخيلة) */}
      {adding && (
        <div className="flex flex-col gap-2 rounded-xl border border-fuchsia-400/25 bg-card p-3">
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="عنوان الفكرة — مثال: بوكس خشب هدايا رمضان"
            aria-label="عنوان الفكرة"
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm outline-none placeholder:text-muted-foreground focus:border-fuchsia-400/40"
          />
          <textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            rows={2}
            placeholder="تفاصيل: مقاسات، خامة، عدد مقترح… (اختياري)"
            aria-label="تفاصيل الفكرة"
            className="w-full resize-none rounded-md border border-border bg-background px-3 py-2 text-sm outline-none placeholder:text-muted-foreground focus:border-fuchsia-400/40"
          />
          <div className="flex flex-wrap items-center gap-2">
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              aria-label="تصنيف الفكرة"
              className="rounded-md border border-border bg-background px-2 py-1.5 text-sm"
            >
              {data.categories.map((c) => (
                <option key={c} value={c}>{CATEGORY_META[c]?.label ?? c}</option>
              ))}
            </select>
            <input
              value={tags}
              onChange={(e) => setTags(e.target.value)}
              placeholder="وسوم مفصولة بفاصلة: رمضان, هدايا"
              aria-label="وسوم"
              className="min-w-40 flex-1 rounded-md border border-border bg-background px-3 py-1.5 text-sm outline-none placeholder:text-muted-foreground focus:border-fuchsia-400/40"
            />
            <Button size="sm" onClick={addIdea} disabled={!title.trim() || busy}>
              <NotebookPen className="size-3.5" /> حفظ في المعمل
            </Button>
          </div>
        </div>
      )}

      {/* قائمة الأفكار */}
      <div className="flex flex-col gap-2.5">
        {visible.map((n) => {
          const meta = CATEGORY_META[n.category] ?? CATEGORY_META['ملاحظة']
          return (
            <article key={n.id} className="rounded-xl border border-border bg-card p-3">
              <header className="flex items-start justify-between gap-3">
                <div className="flex min-w-0 items-start gap-2">
                  <meta.icon className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                  <div className="min-w-0">
                    <h3 className="text-sm font-medium text-foreground">{n.title}</h3>
                    <p className="mt-1 flex flex-wrap items-center gap-1.5">
                      <span className={cn('rounded border px-1.5 py-0.5 text-[10px]', meta.chip)}>{meta.label}</span>
                      {(n.tags ?? []).map((t) => (
                        <span key={t} className="rounded bg-muted/60 px-1.5 py-0.5 text-[10px] text-muted-foreground">{t}</span>
                      ))}
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => void post({ action: 'done', id: n.id }, `✅ «${n.title}» اتنفذت`)}
                  aria-label={`تم تنفيذ ${n.title}`}
                  className="flex size-5 shrink-0 items-center justify-center rounded border border-border text-muted-foreground transition-colors hover:border-emerald-400/40 hover:bg-emerald-400/15 hover:text-emerald-300"
                >
                  <Check className="size-3" />
                </button>
              </header>

              {n.body && <p className="mt-2 text-xs leading-relaxed text-muted-foreground">{n.body}</p>}

              {n.spawned && n.spawned.length > 0 && (
                <div className="mt-2 rounded-lg border border-emerald-400/20 bg-emerald-400/[0.06] p-2">
                  <p className="text-[11px] font-medium text-emerald-200">
                    🚀 تحولت لمشروع — {n.spawned.length} أمر في الدائرة
                  </p>
                  <ul className="mt-1 flex flex-col gap-0.5">
                    {n.spawned.flatMap((s) => s.commands).map((c, i) => (
                      <li key={i} className="font-mono text-[10px] text-muted-foreground" dir="ltr">{c}</li>
                    ))}
                  </ul>
                </div>
              )}

              <footer className="mt-2.5 flex flex-wrap items-center gap-2">
                <Button
                  size="xs"
                  variant="outline"
                  className="gap-1.5"
                  disabled={converting === n.id || busy}
                  onClick={() => void convertIdea(n)}
                >
                  <Rocket className={cn('size-3', converting === n.id && 'animate-pulse')} />
                  {converting === n.id ? 'بيحول لمشروع…' : 'تحويل الفكرة لمشروع 🚀'}
                </Button>
                <Button
                  size="xs"
                  variant="ghost"
                  className="gap-1.5 text-muted-foreground"
                  disabled={busy}
                  onClick={() => void post({ action: 'trash', id: n.id }, `🗑️ «${n.title}» انتقلت للأرشيف`)}
                >
                  <Trash2 className="size-3" /> أرشفة
                </Button>
                <span className="ms-auto text-[10px] text-muted-foreground">
                  {new Date(n.created_at).toLocaleDateString('ar-EG')}
                </span>
              </footer>
            </article>
          )
        })}

        {visible.length === 0 && (
          <p className="rounded-xl border border-dashed border-border py-8 text-center text-xs text-muted-foreground">
            {query ? 'لا نتائج مطابقة للبحث' : 'المعمل فاضي — أضف أول فكرة بالزر ☝️'}
          </p>
        )}
      </div>

      {/* الأرشيف — الحذف ناعم قابل للاسترجاع */}
      <div className="rounded-xl border border-border bg-card/40 p-3">
        <button
          type="button"
          onClick={() => setShowTrash((v) => !v)}
          className="flex w-full items-center gap-2 text-sm text-muted-foreground"
        >
          <Archive className="size-4" />
          الأرشيف ({data.trashed.length})
          <span className="ms-auto text-[11px]">{showTrash ? '▲' : '▼'}</span>
        </button>
        {showTrash && (
          <ul className="mt-2 flex flex-col gap-1.5">
            {data.trashed.length === 0 && (
              <li className="text-xs text-muted-foreground">لا عناصر مؤرشفة</li>
            )}
            {data.trashed.map((n) => (
              <li key={n.id} className="flex items-center gap-2 rounded-lg border border-border bg-card px-2.5 py-1.5 text-sm">
                <span className="min-w-0 flex-1 truncate text-muted-foreground line-through">{n.title}</span>
                <Button size="xs" variant="ghost" className="gap-1" disabled={busy}
                  onClick={() => void post({ action: 'restore', id: n.id }, `↩️ «${n.title}» رجعت للمعمل`)}>
                  <Undo2 className="size-3" /> استرجاع
                </Button>
                <Button size="xs" variant="ghost" className="gap-1 text-rose-300" disabled={busy}
                  onClick={() => void post({ action: 'purge', id: n.id }, '🗑️ حُذفت نهائياً من الأرشيف')}>
                  <Trash2 className="size-3" /> نهائي
                </Button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
