'use client'

import { useCallback, useEffect, useState } from 'react'
import { Activity, ArrowDownUp, CheckCircle2, KeyRound, Plug, Plus, RefreshCw, RotateCcw, Server, Trash2, X, Zap } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

type FleetProvider = {
  id: string
  name: string
  base_url: string
  model: string
  max_tokens: number
  enabled: boolean
  role: 'strong' | 'light'
  env_key: string | null
  key_masked: string
  has_key: boolean
  status: 'up' | 'down' | 'unknown'
  last_error: string | null
  usage: { prompt: number; completion: number; total: number; calls: number }
  gauge: { ratio: number; level: 'green' | 'yellow' | 'red' }
}

type Routing = { complex: string[]; executors: string[]; default_role: 'strong' | 'light' }

const GAUGE_COLOR: Record<string, string> = {
  green: 'bg-emerald-400/70',
  yellow: 'bg-amber-400/80',
  red: 'bg-rose-400/80',
}
const STATUS_META: Record<string, { label: string; cls: string }> = {
  up: { label: 'جاهز', cls: 'text-emerald-300' },
  down: { label: 'متوقف', cls: 'text-rose-300' },
  unknown: { label: 'غير مجرب', cls: 'text-muted-foreground' },
}

export function AiFleet() {
  const [providers, setProviders] = useState<FleetProvider[]>([])
  const [routing, setRouting] = useState<Routing | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [flash, setFlash] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [adding, setAdding] = useState(false)
  const [form, setForm] = useState({ name: '', base_url: '', model: '', max_tokens: 8000, api_key: '', env_key: '', role: 'strong' })
  const [models, setModels] = useState<string[]>([])
  const [fetchingModels, setFetchingModels] = useState(false)
  const [modelsErr, setModelsErr] = useState<string | null>(null)
  // إصلاح الموديل داخل الكرت — للمزود المحفوظ الذي دخل بموديل خاطئ
  const [fixingId, setFixingId] = useState<string | null>(null)
  const [fixModels, setFixModels] = useState<string[]>([])

  const load = useCallback(async () => {
    setError(null)
    try {
      const res = await fetch('/api/ai-fleet', { cache: 'no-store' })
      const j = (await res.json()) as { ok?: boolean; providers?: FleetProvider[]; routing?: Routing; error?: string }
      if (j.ok && j.providers) {
        setProviders(j.providers)
        setRouting(j.routing ?? null)
      } else {
        throw new Error(j.error ?? 'فشل التحميل')
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'فشل التحميل')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void load() }, [load])

  async function post(payload: Record<string, unknown>) {
    setBusy(true)
    setFlash(null)
    try {
      const res = await fetch('/api/ai-fleet', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const j = (await res.json()) as { ok?: boolean; message?: string }
      setFlash(j.message ?? (j.ok ? 'تم' : 'رفض الإجراء'))
      if (j.ok) {
        setAdding(false)
        setForm({ name: '', base_url: '', model: '', max_tokens: 8000, api_key: '', env_key: '', role: 'strong' })
        setModels([])
        await load()
      }
      return j
    } catch {
      setFlash('⚠️ فشل الاتصال')
      return { ok: false }
    } finally {
      setBusy(false)
    }
  }

  /** السحب التلقائي للنماذج — GET /v1/models القياسية من المزود المُدخل */
  async function fetchModels() {
    if (!form.base_url || (!form.env_key && !form.api_key)) {
      setModelsErr('أدخل Base URL والمفتاح أولاً')
      return
    }
    setFetchingModels(true)
    setModelsErr(null)
    try {
      const res = await fetch('/api/ai-fleet', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'list_models', base_url: form.base_url, env_key: form.env_key || undefined, api_key: form.api_key || undefined }),
      })
      const j = (await res.json()) as { ok?: boolean; models?: string[]; message?: string }
      if (j.ok && j.models?.length) {
        setModels(j.models)
        if (!form.model || !j.models.includes(form.model)) setForm((f) => ({ ...f, model: j.models![0] }))
      } else {
        setModelsErr(j.message ?? 'لا نماذج')
      }
    } catch {
      setModelsErr('⚠️ فشل سحب النماذج')
    } finally {
      setFetchingModels(false)
    }
  }

  /** اختبار حقيقي: رسالة Ping فعلية للنموذج المختار */
  async function realPing(id: string) {
    setBusy(true)
    setFlash(null)
    const j = (await post({ action: 'ping_chat', id })) as { ms?: number; reply?: string }
    if (j?.ms) setFlash(`⚡ رد حقيقي في ${j.ms}ms — «${(j.reply ?? '').slice(0, 60)}»`)
  }

  /** سحب نماذج مزود محفوظ (بمفتاحه المخزن) لإصلاح الموديل بنقرة */
  async function fixModel(id: string) {
    setBusy(true)
    setFlash(null)
    try {
      const res = await fetch('/api/ai-fleet', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'list_models', id }),
      })
      const j = (await res.json()) as { ok?: boolean; models?: string[]; message?: string }
      if (j.ok && j.models?.length) {
        setFixModels(j.models)
        setFixingId(id)
      } else {
        setFlash(j.message ?? 'لا نماذج')
      }
    } catch {
      setFlash('⚠️ فشل سحب النماذج')
    } finally {
      setBusy(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 p-4 text-sm text-muted-foreground">
        <RefreshCw className="size-4 animate-spin" /> فيجن بيجمع موقف الأسطول…
      </div>
    )
  }
  if (error) {
    return <div className="p-4 text-sm text-rose-300">⚠️ {error} <Button variant="ghost" size="sm" onClick={() => void load()}>إعادة</Button></div>
  }

  return (
    <div className="flex flex-col gap-3 p-4">
      {flash && (
        <div className="flex items-center justify-between gap-2 rounded-xl border border-sky-400/25 bg-sky-400/[0.08] px-3 py-2 text-sm text-sky-200">
          <span>{flash}</span>
          <button type="button" onClick={() => setFlash(null)} aria-label="إغلاق" className="text-sky-300/70"><X className="size-3.5" /></button>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <p className="flex items-center gap-2 text-sm font-medium text-foreground">
          <Server className="size-4 text-sky-300" /> أسطول الذكاء الاصطناعي — {providers.length} مزود
        </p>
        <div className="ms-auto flex items-center gap-2">
          <Button size="sm" variant="ghost" onClick={() => void post({ action: 'reset_usage' })} disabled={busy} className="gap-1.5 text-muted-foreground">
            <RotateCcw className="size-3.5" /> تصفير الجلسة
          </Button>
          <Button size="sm" onClick={() => setAdding((v) => !v)} className="gap-1.5">
            {adding ? <X className="size-3.5" /> : <Plus className="size-3.5" />} مزود جديد
          </Button>
        </div>
      </div>

      {adding && (
        <div className="flex flex-col gap-2 rounded-xl border border-sky-400/25 bg-card p-3">
          <div className="grid grid-cols-2 gap-2 md:grid-cols-3">
            <label className="flex flex-col gap-1 text-[11px] text-muted-foreground">
              اسم المزود
              <input value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} placeholder="مثال: Dahl / OpenRouter" aria-label="اسم المزود"
                className="rounded-md border border-border bg-background px-2.5 py-1.5 text-sm text-foreground outline-none focus:border-sky-400/40" />
            </label>
            <label className="flex flex-col gap-1 text-[11px] text-muted-foreground">
              Base URL
              <input value={form.base_url} onChange={(e) => { setForm((f) => ({ ...f, base_url: e.target.value })); setModels([]) }} placeholder="https://api…/v1" dir="ltr" aria-label="Base URL"
                className="rounded-md border border-border bg-background px-2.5 py-1.5 font-mono text-xs text-foreground outline-none focus:border-sky-400/40" />
            </label>
            <label className="flex flex-col gap-1 text-[11px] text-muted-foreground">
              مفتاح API (أو اسم متغير من .env)
              <input value={form.env_key || form.api_key} onChange={(e) => {
                const v = e.target.value
                setForm((f) => (v.startsWith('nvapi-') || v.startsWith('sk-') ? { ...f, api_key: v, env_key: '' } : { ...f, env_key: v, api_key: '' }))
                setModels([])
              }} placeholder="DAHL_API_KEY أو sk-…" dir="ltr" aria-label="API Key" type="password"
                className="rounded-md border border-border bg-background px-2.5 py-1.5 font-mono text-xs text-foreground outline-none focus:border-sky-400/40" />
            </label>
          </div>

          {/* الموديل: سحب تلقائي من /v1models — أو إدخال يدوي احتياط */}
          <div className="flex flex-wrap items-end gap-2">
            <label className="flex min-w-56 flex-1 flex-col gap-1 text-[11px] text-muted-foreground">
              الموديل {models.length > 0 && <span className="text-emerald-300">({models.length} نموذج متاح)</span>}
              {models.length > 0 ? (
                <select value={form.model} onChange={(e) => setForm((f) => ({ ...f, model: e.target.value }))} aria-label="اختيار الموديل"
                  className="rounded-md border border-emerald-400/30 bg-background px-2.5 py-1.5 font-mono text-xs text-foreground outline-none">
                  {models.map((m) => (
                    <option key={m} value={m}>{m}</option>
                  ))}
                </select>
              ) : (
                <input value={form.model} onChange={(e) => setForm((f) => ({ ...f, model: e.target.value }))} placeholder="اكتب يدوياً أو اسحب النماذج" dir="ltr" aria-label="الموديل"
                  className="rounded-md border border-border bg-background px-2.5 py-1.5 font-mono text-xs text-foreground outline-none focus:border-sky-400/40" />
              )}
            </label>
            <Button size="sm" variant="outline" disabled={fetchingModels || !form.base_url || (!form.env_key && !form.api_key)} onClick={() => void fetchModels()} className="gap-1.5">
              <ArrowDownUp className={cn('size-3.5', fetchingModels && 'animate-bounce')} />
              {fetchingModels ? 'بيسحب…' : 'سحب النماذج ⬇'}
            </Button>
            <label className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
              Max Tokens
              <input value={form.max_tokens} onChange={(e) => setForm((f) => ({ ...f, max_tokens: Number(e.target.value) || 8000 }))} type="number" dir="ltr" aria-label="Max Tokens"
                className="w-24 rounded-md border border-border bg-background px-2 py-1.5 font-mono text-xs text-foreground outline-none focus:border-sky-400/40" />
            </label>
            <select value={form.role} onChange={(e) => setForm((f) => ({ ...f, role: e.target.value }))} aria-label="دور المزود"
              className="rounded-md border border-border bg-background px-2 py-1.5 text-sm text-foreground">
              <option value="strong">💪 قوي (المعقدون)</option>
              <option value="light">⚡ خفيف (التنفيذيون)</option>
            </select>
            <Button size="sm" disabled={busy || !form.name || !form.base_url || !form.model || (!form.api_key && !form.env_key)} onClick={() => void post({ action: 'add_provider', ...form })}>
              <Plug className="size-3.5" /> إضافة للأسطول
            </Button>
          </div>
          {modelsErr && <p className="text-[11px] text-amber-300">{modelsErr} — يمكن الإدخال يدوياً.</p>}
          <p className="text-[10px] text-muted-foreground">
            🔐 المفتاح لا يظهر أبداً في الواجهة ولا يخرج من السيرفر — والملف محمي في .gitignore.
          </p>
        </div>
      )}

      <div className="flex flex-col gap-2">
        {providers.length === 0 && (
          <p className="rounded-xl border border-dashed border-border py-6 text-center text-xs text-muted-foreground">
            الأسطول فاضي — أضف أول مزود (أو أعِد التحميل لو فيه DAHL_API_KEY في .env)
          </p>
        )}
        {providers.map((p) => {
          const sm = STATUS_META[p.status] ?? STATUS_META.unknown
          const pct = Math.round(p.gauge.ratio * 100)
          return (
            <article key={p.id} className="rounded-xl border border-border bg-card p-3">
              <header className="flex flex-wrap items-center gap-2">
                <span className={cn('flex items-center gap-1.5 text-sm font-medium', p.enabled ? 'text-foreground' : 'text-muted-foreground line-through')}>
                  <Activity className="size-3.5 text-sky-300" aria-hidden="true" />
                  {p.name}
                </span>
                <span className={cn('rounded border px-1.5 py-0.5 text-[10px]', p.role === 'strong' ? 'border-violet-400/30 bg-violet-400/10 text-violet-200' : 'border-emerald-400/30 bg-emerald-400/10 text-emerald-200')}>
                  {p.role === 'strong' ? '💪 قوي' : '⚡ خفيف'}
                </span>
                <span className="rounded bg-muted/60 px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground" dir="ltr">{p.model}</span>
                <span className={cn('text-[11px]', sm.cls)}>● {sm.label}</span>
                <span className="ms-auto flex items-center gap-1">
                  <Button size="xs" variant="ghost" disabled={busy} onClick={() => void realPing(p.id)} className="gap-1 text-sky-300">
                    <Zap className="size-3" /> اختبار حي
                  </Button>
                  <Button size="xs" variant="ghost" disabled={busy} onClick={() => void fixModel(p.id)} className="gap-1 text-muted-foreground" title="سحب النماذج المتاحة وإصلاح الموديل">
                    <ArrowDownUp className="size-3" /> نموذج
                  </Button>
                  <Button size="xs" variant="ghost" disabled={busy} onClick={() => void post({ action: 'update_provider', id: p.id, enabled: !p.enabled })} className="gap-1 text-muted-foreground">
                    <CheckCircle2 className="size-3" /> {p.enabled ? 'تعطيل' : 'تفعيل'}
                  </Button>
                  <Button size="xs" variant="ghost" disabled={busy} onClick={() => void post({ action: 'remove_provider', id: p.id })} className="gap-1 text-rose-300">
                    <Trash2 className="size-3" />
                  </Button>
                </span>
              </header>

              <div className="mt-2 flex items-center gap-2 text-[11px] text-muted-foreground">
                <span className="font-mono" dir="ltr">{p.base_url}</span>
                <span className="flex items-center gap-1 font-mono" dir="ltr">
                  <KeyRound className="size-3" aria-hidden="true" /> {p.key_masked}
                </span>
              </div>

              {/* مؤشر الاستهلاك الحي (Token Gauge) — أخضر → أصفر → أحمر */}
              <div className="mt-2">
                <div className="flex items-center justify-between text-[11px]">
                  <span className="text-muted-foreground">استهلاك الجلسة (تقديري)</span>
                  <span className={cn('font-mono tabular-nums', pct >= 85 ? 'text-rose-300' : pct >= 60 ? 'text-amber-300' : 'text-emerald-300')} dir="ltr">
                    {p.usage.total.toLocaleString('en')} / {p.max_tokens.toLocaleString('en')} ({pct}%)
                  </span>
                </div>
                <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-muted">
                  <div className={cn('h-full rounded-full transition-all duration-700', GAUGE_COLOR[p.gauge.level])} style={{ width: `${Math.min(100, pct)}%` }} />
                </div>
                {p.last_error && <p className="mt-1 truncate font-mono text-[10px] text-rose-300/80" dir="ltr">{p.last_error}</p>}
              </div>

              {/* إصلاح الموديل بنقرة — سحب النماذج بمفتاح المزود المخزن */}
              {fixingId === p.id && fixModels.length > 0 ? (
                <div className="mt-2 flex flex-wrap items-center gap-2 rounded-lg border border-emerald-400/25 bg-emerald-400/[0.06] p-2">
                  <span className="text-[11px] text-emerald-200">اختر الموديل الصحيح:</span>
                  <select
                    aria-label="إصلاح الموديل"
                    defaultValue=""
                    onChange={(e) => {
                      const model = e.target.value
                      if (model) {
                        setFixingId(null)
                        setFixModels([])
                        void post({ action: 'update_provider', id: p.id, model }, )
                      }
                    }}
                    className="max-w-72 rounded-md border border-border bg-background px-2 py-1 font-mono text-xs text-foreground"
                  >
                    <option value="" disabled>— اختر —</option>
                    {fixModels.map((m) => (
                      <option key={m} value={m}>{m}</option>
                    ))}
                  </select>
                  <button type="button" onClick={() => { setFixingId(null); setFixModels([]) }} className="text-[11px] text-muted-foreground">إلغاء</button>
                </div>
              ) : null}
            </article>
          )
        })}
      </div>

      {routing && (
        <div className="rounded-xl border border-border bg-card/50 p-3 text-xs text-muted-foreground">
          <p className="mb-1 font-medium text-foreground">🎯 التوجيه حسب الوكيل</p>
          <p>المعقدون ← الأقوى: <span className="font-mono" dir="ltr">{routing.complex.join(', ')}</span></p>
          <p>التنفيذيون ← الأخف: <span className="font-mono" dir="ltr">{routing.executors.join(', ')}</span></p>
        </div>
      )}
    </div>
  )
}
