'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  Activity,
  ArrowDownUp,
  CheckCircle2,
  KeyRound,
  Layers,
  Plus,
  RefreshCw,
  RotateCcw,
  Server,
  Sparkles,
  StopCircle,
  Trash2,
  X,
  Zap,
} from 'lucide-react'
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
  const [, setModels] = useState<string[]>([])
  const [fetchingModels, setFetchingModels] = useState(false)
  const [modelsErr, setModelsErr] = useState<string | null>(null)
  const [fixingId, setFixingId] = useState<string | null>(null)
  const [fixModels, setFixModels] = useState<string[]>([])

  // حالة الاختبار المتسلسل (Sequential Batched Testing)
  const [isTesting, setIsTesting] = useState(false)
  const [testingProgress, setTestingProgress] = useState<{
    current: number
    total: number
    batch: number
    currentNames: string
  } | null>(null)
  const stopTestingRef = useRef(false)

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

  // تجميع المزودين تلقائياً حسب الـ Base URL لتنظيم الشاشة والحذف المجمع
  const groups = useMemo(() => {
    const map = new Map<string, FleetProvider[]>()
    for (const p of providers) {
      const u = (p.base_url || '').replace(/\/+$/, '')
      if (!map.has(u)) map.set(u, [])
      map.get(u)!.push(p)
    }
    return Array.from(map.entries()).map(([url, list]) => {
      const sample = list[0]
      const mainName = sample?.name.split('(')[0]?.trim() || 'مزود ذكاء'
      const upCount = list.filter((x) => x.status === 'up').length
      const downCount = list.filter((x) => x.status === 'down').length
      const unknownCount = list.length - upCount - downCount
      return {
        url,
        mainName,
        providers: list,
        upCount,
        downCount,
        unknownCount,
      }
    })
  }, [providers])

  /** 1️⃣ مسح المزود بالكامل: حذف جميع النماذج التي تشترك في نفس הـ Base URL */
  async function handleDeleteProviderGroup(baseUrl: string, groupName: string, count: number) {
    if (
      typeof window !== 'undefined' &&
      !window.confirm(`هل أنت متأكد من مسح جميع نماذج «${groupName}» (${count} نموذج) نهائياً من ملف ai_providers.json؟`)
    ) {
      return
    }

    setBusy(true)
    setFlash(`⏳ جاري مسح ${count} نموذج تابع لـ ${groupName} من الأسطول…`)
    try {
      const res = await fetch('/api/ai-fleet', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'delete_by_base_url', base_url: baseUrl }),
      })
      const j = (await res.json()) as { ok?: boolean; message?: string }
      if (j.ok) {
        setFlash(j.message ?? `🗑️ تم مسح ${count} نموذج تابع لـ ${groupName} بنجاح`)
        await load()
      } else {
        setFlash(`⚠️ فشل المسح: ${j.message ?? 'رفض السيرفر الطلب'}`)
      }
    } catch {
      setFlash('⚠️ تعذر الاتصال بالسيرفر لإتمام المسح المجمع')
    } finally {
      setBusy(false)
    }
  }

  /** 1️⃣ تنظيف النماذج المعطلة: حذف كل نموذج به أخطاء (404, 410, 429) أو غير متصل */
  async function handleCleanBrokenModels() {
    const brokenCount = providers.filter(
      (p) => p.status === 'down' || (p.last_error && /404|410|429|not found|gone|aborted/i.test(p.last_error)),
    ).length

    if (brokenCount === 0) {
      setFlash('✨ لا توجد نماذج معطلة حالياً لتنظيفها!')
      return
    }

    if (
      typeof window !== 'undefined' &&
      !window.confirm(`هل أنت متأكد من تنظيف وحذف جميع النماذج المعطلة (${brokenCount} نموذج معطل) من الأسطول؟`)
    ) {
      return
    }

    setBusy(true)
    setFlash('⏳ جاري تنظيف النماذج المعطلة من ملف ai_providers.json…')
    try {
      const res = await fetch('/api/ai-fleet', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'clean_broken_models' }),
      })
      const j = (await res.json()) as { ok?: boolean; message?: string }
      if (j.ok) {
        setFlash(j.message ?? '🧹 تم تنظيف وحذف النماذج المعطلة بنجاح')
        await load()
      } else {
        setFlash(`⚠️ فشل التنظيف: ${j.message ?? 'رفض السيرفر الطلب'}`)
      }
    } catch {
      setFlash('⚠️ تعذر الاتصال بالسيرفر لإتمام التنظيف')
    } finally {
      setBusy(false)
    }
  }

  /** 2️⃣ الاختبار المتسلسل (Sequential Batched Ping) — دفعات ثلاثية مع مهلة 500ms لمنع الـ Rate Limit */
  async function runSequentialPing(targets?: FleetProvider[]) {
    const list = targets && targets.length > 0 ? targets : providers
    if (list.length === 0) {
      setFlash('⚠️ لا توجد نماذج لاختبارها')
      return
    }

    setIsTesting(true)
    stopTestingRef.current = false
    setFlash('⚡ بدء الاختبار المتسلسل المنظم في دفعات ثلاثية لمنع الـ Rate Limit…')

    const BATCH_SIZE = 3
    const DELAY_MS = 500
    let processed = 0
    let passed = 0
    let failed = 0

    try {
      for (let i = 0; i < list.length; i += BATCH_SIZE) {
        if (stopTestingRef.current) {
          setFlash(`⏹️ تم إيقاف الاختبار المتسلسل بواسطة المستخدم (${processed} من ${list.length})`)
          break
        }

        const batch = list.slice(i, i + BATCH_SIZE)
        const batchNum = Math.floor(i / BATCH_SIZE) + 1
        const namesSummary = batch.map((b) => b.model.split('/').pop()).join(', ')

        setTestingProgress({
          current: Math.min(i + batch.length, list.length),
          total: list.length,
          batch: batchNum,
          currentNames: namesSummary,
        })

        // اختبار الدفعة الحالية (3 نماذج بالتوازي)
        await Promise.all(
          batch.map(async (p) => {
            try {
              const res = await fetch('/api/ai-fleet', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action: 'test_provider', id: p.id }),
              })
              const j = (await res.json()) as { ok?: boolean; message?: string; detail?: string }
              const isOk = Boolean(j.ok)
              if (isOk) passed++
              else failed++

              // تحديث حالة البطاقة الحية في الواجهة فوراً
              setProviders((prev) =>
                prev.map((item) =>
                  item.id === p.id
                    ? {
                        ...item,
                        status: isOk ? 'up' : 'down',
                        last_error: isOk ? null : (j.detail || j.message || 'فشل الفحص'),
                      }
                    : item,
                ),
              )
              return isOk
            } catch {
              failed++
              setProviders((prev) =>
                prev.map((item) =>
                  item.id === p.id ? { ...item, status: 'down', last_error: 'انقطاع شبكة' } : item,
                ),
              )
              return false
            }
          }),
        )

        processed += batch.length

        // مهلة 500ms فاصلة بين كل دفعة وأخرى لمنع اختناق السيرفر وتفادي خطأ 429
        if (i + BATCH_SIZE < list.length && !stopTestingRef.current) {
          await new Promise((resolve) => setTimeout(resolve, DELAY_MS))
        }
      }

      if (!stopTestingRef.current) {
        setFlash(`✅ اكتمل الاختبار المتسلسل بنجاح: ${passed} جاهز | ${failed} متوقف من أصل ${list.length}`)
      }
    } finally {
      setIsTesting(false)
      setTestingProgress(null)
      stopTestingRef.current = false
    }
  }

  function handleStopTesting() {
    stopTestingRef.current = true
    setIsTesting(false)
    setTestingProgress(null)
    setFlash('⏹️ جاري إنهاء الدفعة الحالية والتوقف…')
  }

  /** الإضافة المجمعة للنماذج دفعة واحدة */
  async function bulkAddModels() {
    const baseUrl = form.base_url.trim().replace(/\/+$/, '')
    const key = (form.api_key || form.env_key).trim()

    if (!baseUrl || !key) {
      const msg = 'يرجى إدخال Base URL ومفتاح الـ API أولاً'
      setModelsErr(msg)
      setFlash(`⚠️ ${msg}`)
      return
    }

    setFetchingModels(true)
    setBusy(true)
    setModelsErr(null)
    setFlash('⏳ جاري سحب النماذج من المزود وإضافتها للأسطول…')

    try {
      const res = await fetch('/api/ai-fleet', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: 'bulk_add_models',
          base_url: baseUrl,
          name: form.name.trim() || 'AI',
          api_key: form.api_key || (form.env_key ? undefined : key),
          env_key: form.env_key || undefined,
          max_tokens: form.max_tokens,
          role: form.role,
        }),
      })

      const j = (await res.json()) as { ok?: boolean; message?: string; total_models?: number }
      if (j.ok) {
        setFlash(j.message ?? '⚡ تم سحب وإضافة جميع النماذج وحفظها في ai_providers.json بنجاح!')
        setAdding(false)
        setForm({ name: '', base_url: '', model: '', max_tokens: 8000, api_key: '', env_key: '', role: 'strong' })
        setModels([])
        await load()
      } else {
        throw new Error(j.message ?? 'فشلت الإضافة المجمعة')
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '⚠️ خطأ في سحب وإضافة النماذج'
      setModelsErr(msg)
      setFlash(`⚠️ ${msg}`)
    } finally {
      setFetchingModels(false)
      setBusy(false)
    }
  }

  /** حذف مزود مفرد */
  async function handleDeleteProvider(id: string, name?: string) {
    if (typeof window !== 'undefined' && !window.confirm(`هل أنت متأكد من حذف المزود «${name || id}» نهائياً من الأسطول؟`)) {
      return
    }

    setBusy(true)
    setFlash('⏳ جاري مسح المزود من ملف ai_providers.json…')

    try {
      const res = await fetch(`/api/ai-fleet?id=${encodeURIComponent(id)}`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id, action: 'remove_provider' }),
      })
      const j = (await res.json()) as { ok?: boolean; message?: string }
      if (j.ok) {
        setProviders((prev) => prev.filter((p) => p.id !== id))
        setFlash(j.message ?? '🗑️ تم حذف المزود بنجاح من الأسطول')
        await load()
      } else {
        setFlash(`⚠️ فشل الحذف من السيرفر: ${j.message ?? 'رفض السيرفر الحذف'}`)
      }
    } catch {
      setFlash('⚠️ تعذر الاتصال بالسيرفر لإتمام الحذف')
    } finally {
      setBusy(false)
    }
  }

  /** اختبار حقيقي: رسالة Ping فعلية للنموذج المختار */
  async function realPing(id: string) {
    setBusy(true)
    setFlash(null)
    const j = (await post({ action: 'ping_chat', id })) as { ms?: number; reply?: string }
    if (j?.ms) setFlash(`⚡ رد حقيقي في ${j.ms}ms — «${(j.reply ?? '').slice(0, 60)}»`)
  }

  /** سحب نماذج مزود محفوظ لإصلاح الموديل بنقرة */
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
    return (
      <div className="p-4 text-sm text-rose-300">
        ⚠️ {error} <Button variant="ghost" size="sm" onClick={() => void load()}>إعادة</Button>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-3 p-4">
      {/* إشعارات النظام Flash */}
      {flash && (
        <div className="flex items-center justify-between gap-2 rounded-xl border border-sky-400/25 bg-sky-400/[0.08] px-3 py-2 text-sm text-sky-200">
          <span>{flash}</span>
          <button type="button" onClick={() => setFlash(null)} aria-label="إغلاق" className="text-sky-300/70">
            <X className="size-3.5" />
          </button>
        </div>
      )}

      {/* شريط تقدم الاختبار المتسلسل لمنع الـ Rate Limit */}
      {isTesting && testingProgress && (
        <div className="flex flex-col gap-2 rounded-xl border border-amber-400/35 bg-amber-500/10 p-3 text-xs text-amber-200 shadow-sm animate-in fade-in">
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-2 font-medium">
              <Zap className="size-4 animate-bounce text-amber-400" />
              اختبار متسلسل (دفعات ثلاثية مع مهلة 500ms): {testingProgress.current} / {testingProgress.total} نموذج
              (دفعة #{testingProgress.batch})
            </span>
            <Button
              size="xs"
              variant="destructive"
              onClick={handleStopTesting}
              className="gap-1 bg-rose-600/80 hover:bg-rose-600 text-white"
            >
              <StopCircle className="size-3.5" /> إيقاف الفحص
            </Button>
          </div>
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-amber-950/40">
            <div
              className="h-full bg-amber-400 transition-all duration-300"
              style={{ width: `${Math.round((testingProgress.current / testingProgress.total) * 100)}%` }}
            />
          </div>
          <p className="font-mono text-[11px] text-amber-300/70 truncate" dir="ltr">
            الدفعة الحالية: {testingProgress.currentNames}
          </p>
        </div>
      )}

      {/* شريط الإجراءات العلوي */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border/50 pb-3">
        <p className="flex items-center gap-2 text-sm font-medium text-foreground">
          <Server className="size-4 text-sky-300" /> أسطول الذكاء الاصطناعي — {providers.length} نموذج في {groups.length} مزود
        </p>

        <div className="flex flex-wrap items-center gap-2">
          {/* زر الاختبار المتسلسل للكل */}
          <Button
            size="sm"
            variant="outline"
            onClick={() => void runSequentialPing()}
            disabled={busy || isTesting || providers.length === 0}
            className="gap-1.5 border-sky-400/30 text-sky-200 hover:bg-sky-400/10 font-medium"
            title="اختبار جميع النماذج في دفعات من 3 نماذج مع مهلة 500ms لتفادي الحظر"
          >
            <Zap className={cn('size-3.5 text-sky-300', isTesting && 'animate-spin')} />
            {isTesting ? 'جاري الفحص…' : 'اختبار متسلسل ⚡'}
          </Button>

          {/* زر تنظيف النماذج المعطلة */}
          <Button
            size="sm"
            variant="outline"
            onClick={() => void handleCleanBrokenModels()}
            disabled={busy || isTesting || providers.length === 0}
            className="gap-1.5 border-rose-500/30 text-rose-300 hover:bg-rose-500/10 hover:text-rose-200"
            title="حذف أي نموذج حالته 404 أو 429 أو 410 أو غير متصل لتنظيف القائمة"
          >
            <Sparkles className="size-3.5 text-amber-300" />
            تنظيف المعطلين 🧹
          </Button>

          <Button
            size="sm"
            variant="ghost"
            onClick={() => void post({ action: 'reset_usage' })}
            disabled={busy || isTesting}
            className="gap-1.5 text-muted-foreground"
          >
            <RotateCcw className="size-3.5" /> تصفير
          </Button>

          <Button
            size="sm"
            onClick={() => setAdding((v) => !v)}
            className="gap-1.5 bg-sky-600 hover:bg-sky-500 text-white font-medium shadow-sm"
          >
            {adding ? <X className="size-3.5" /> : <Plus className="size-3.5" />} مزود جديد
          </Button>
        </div>
      </div>

      {/* لوحة إضافة مزود جديد أو سحب مجمع */}
      {adding && (
        <div className="flex flex-col gap-2 rounded-xl border border-sky-400/25 bg-card p-3 shadow-lg">
          <div className="grid grid-cols-2 gap-2 md:grid-cols-3">
            <label className="flex flex-col gap-1 text-[11px] text-muted-foreground">
              اسم المزود
              <input
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                placeholder="مثال: Nvidia NIM أو Dahl أو Groq"
                aria-label="اسم المزود"
                className="rounded-md border border-border bg-background px-2.5 py-1.5 text-sm text-foreground outline-none focus:border-sky-400/40"
              />
            </label>
            <label className="flex flex-col gap-1 text-[11px] text-muted-foreground">
              Base URL
              <input
                value={form.base_url}
                onChange={(e) => {
                  setForm((f) => ({ ...f, base_url: e.target.value }))
                  setModels([])
                }}
                placeholder="https://integrate.api.nvidia.com/v1"
                dir="ltr"
                aria-label="Base URL"
                className="rounded-md border border-border bg-background px-2.5 py-1.5 font-mono text-xs text-foreground outline-none focus:border-sky-400/40"
              />
            </label>
            <label className="flex flex-col gap-1 text-[11px] text-muted-foreground">
              مفتاح API (أو اسم متغير من .env)
              <input
                value={form.api_key || form.env_key}
                onChange={(e) => {
                  const v = e.target.value.trim()
                  if (/^[A-Z][A-Z0-9_]{2,}$/.test(v)) {
                    setForm((f) => ({ ...f, env_key: v, api_key: '' }))
                  } else {
                    setForm((f) => ({ ...f, api_key: v, env_key: '' }))
                  }
                  setModels([])
                }}
                placeholder="nvapi-... أو DAHL_API_KEY"
                dir="ltr"
                aria-label="API Key"
                type="password"
                className="rounded-md border border-border bg-background px-2.5 py-1.5 font-mono text-xs text-foreground outline-none focus:border-sky-400/40"
              />
            </label>
          </div>

          <div className="flex flex-wrap items-end gap-2 pt-1">
            <Button
              type="button"
              size="sm"
              disabled={fetchingModels || busy || !form.base_url || (!form.env_key && !form.api_key)}
              onClick={() => void bulkAddModels()}
              className="gap-1.5 bg-gradient-to-r from-sky-600 to-indigo-600 hover:from-sky-500 hover:to-indigo-500 text-white font-medium shadow-md transition-all"
            >
              <Zap className={cn('size-4', fetchingModels && 'animate-spin')} />
              {fetchingModels ? 'جاري سحب وحفظ النماذج…' : 'سحب وإضافة كل النماذج دفعة واحدة ⚡'}
            </Button>

            <span className="text-[11px] text-muted-foreground self-center px-1">أو إضافة مفردة:</span>

            <label className="flex min-w-44 flex-1 flex-col gap-1 text-[11px] text-muted-foreground">
              اسم الموديل
              <input
                value={form.model}
                onChange={(e) => setForm((f) => ({ ...f, model: e.target.value }))}
                placeholder="مثال: meta/llama-3.3-70b-instruct"
                dir="ltr"
                aria-label="الموديل"
                className="rounded-md border border-border bg-background px-2.5 py-1.5 font-mono text-xs text-foreground outline-none focus:border-sky-400/40"
              />
            </label>

            <label className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
              Max Tokens
              <input
                value={form.max_tokens}
                onChange={(e) => setForm((f) => ({ ...f, max_tokens: Number(e.target.value) || 8000 }))}
                type="number"
                dir="ltr"
                aria-label="Max Tokens"
                className="w-20 rounded-md border border-border bg-background px-2 py-1.5 font-mono text-xs text-foreground outline-none focus:border-sky-400/40"
              />
            </label>

            <select
              value={form.role}
              onChange={(e) => setForm((f) => ({ ...f, role: e.target.value }))}
              aria-label="دور المزود"
              className="rounded-md border border-border bg-background px-2 py-1.5 text-xs text-foreground"
            >
              <option value="strong">💪 قوي</option>
              <option value="light">⚡ خفيف</option>
            </select>

            <Button
              type="button"
              size="sm"
              variant="outline"
              disabled={busy || !form.name || !form.base_url || !form.model || (!form.api_key && !form.env_key)}
              onClick={() => void post({ action: 'add_provider', ...form })}
              className="gap-1.5 text-xs"
            >
              <Plus className="size-3.5" /> إضافة المفرد
            </Button>
          </div>

          {modelsErr && <p className="text-[11px] text-amber-300">{modelsErr}</p>}
        </div>
      )}

      {/* قائمة المزودين مجمعة حسب الـ Base URL */}
      <div className="flex flex-col gap-4">
        {providers.length === 0 && (
          <p className="rounded-xl border border-dashed border-border py-8 text-center text-xs text-muted-foreground">
            الأسطول فارغ — أضف أول مزود أو اسحب النماذج دفعة واحدة 🚀
          </p>
        )}

        {groups.map((group) => (
          <section key={group.url} className="flex flex-col gap-2 rounded-2xl border border-border/80 bg-card/60 p-3 shadow-sm">
            {/* رأس مجموعة المزود مع زر الحذف المجمع واختبار المجموعة */}
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border/40 pb-2.5">
              <div className="flex flex-wrap items-center gap-2">
                <span className="flex items-center gap-1.5 text-sm font-bold text-foreground">
                  <Layers className="size-4 text-sky-400" />
                  {group.mainName}
                </span>
                <span className="rounded bg-muted/70 px-2 py-0.5 font-mono text-[10px] text-muted-foreground" dir="ltr">
                  {group.url}
                </span>
                <span className="rounded-full bg-sky-500/10 border border-sky-400/25 px-2 py-0.5 text-[10px] font-medium text-sky-300">
                  {group.providers.length} نموذج
                </span>
                {group.upCount > 0 && (
                  <span className="rounded-full bg-emerald-500/10 border border-emerald-400/25 px-2 py-0.5 text-[10px] text-emerald-300 font-medium">
                    ✅ {group.upCount} جاهز
                  </span>
                )}
                {group.downCount > 0 && (
                  <span className="rounded-full bg-rose-500/10 border border-rose-400/25 px-2 py-0.5 text-[10px] text-rose-300 font-medium">
                    ⚠️ {group.downCount} معطل
                  </span>
                )}
              </div>

              {/* أزرار الإجراءات المجمعة للمجموعة */}
              <div className="flex items-center gap-2">
                <Button
                  size="xs"
                  variant="outline"
                  onClick={() => void runSequentialPing(group.providers)}
                  disabled={busy || isTesting}
                  className="gap-1 border-sky-400/25 text-sky-200 hover:bg-sky-400/10 text-[11px]"
                  title="اختبار هذه المجموعة فقط متسلسلاً في دفعات من 3"
                >
                  <Zap className="size-3 text-sky-300" /> اختبار المجموعة
                </Button>

                {/* 1️⃣ زر مسح المزود بالكامل (حذف كل النماذج التي تشترك في نفس הـ baseUrl) */}
                <Button
                  size="xs"
                  variant="ghost"
                  onClick={() => void handleDeleteProviderGroup(group.url, group.mainName, group.providers.length)}
                  disabled={busy || isTesting}
                  className="gap-1 text-rose-400 hover:bg-rose-500/15 hover:text-rose-300 text-[11px] font-medium transition-colors"
                  title="حذف جميع النماذج التابعة لهذا المزود بضغطة واحدة من ai_providers.json"
                >
                  <Trash2 className="size-3.5" />
                  مسح المزود بالكامل ({group.providers.length}) 🗑️
                </Button>
              </div>
            </div>

            {/* بطاقات النماذج التابعة لهذه المجموعة */}
            <div className="grid grid-cols-1 gap-2 pt-1">
              {group.providers.map((p) => {
                const sm = STATUS_META[p.status] ?? STATUS_META.unknown
                const pct = Math.round(p.gauge.ratio * 100)
                return (
                  <article key={p.id} className="rounded-xl border border-border/60 bg-background/50 p-2.5 transition-all hover:border-sky-400/30">
                    <header className="flex flex-wrap items-center gap-2">
                      <span className={cn('flex items-center gap-1.5 text-xs font-medium', p.enabled ? 'text-foreground' : 'text-muted-foreground line-through')}>
                        <Activity className="size-3 text-sky-300" aria-hidden="true" />
                        {p.name}
                      </span>
                      <span
                        className={cn(
                          'rounded border px-1.5 py-0.5 text-[9px] font-semibold',
                          p.role === 'strong' ? 'border-violet-400/30 bg-violet-400/10 text-violet-200' : 'border-emerald-400/30 bg-emerald-400/10 text-emerald-200',
                        )}
                      >
                        {p.role === 'strong' ? '💪 قوي' : '⚡ خفيف'}
                      </span>
                      <span className="rounded bg-muted/60 px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground" dir="ltr">
                        {p.model}
                      </span>
                      <span className={cn('text-[11px] font-medium', sm.cls)}>● {sm.label}</span>

                      <span className="ms-auto flex items-center gap-1">
                        <Button size="xs" variant="ghost" disabled={busy || isTesting} onClick={() => void realPing(p.id)} className="gap-1 text-sky-300 text-[11px]">
                          <Zap className="size-3" /> اختبار حي
                        </Button>
                        <Button
                          size="xs"
                          variant="ghost"
                          disabled={busy || isTesting}
                          onClick={() => void fixModel(p.id)}
                          className="gap-1 text-muted-foreground text-[11px]"
                          title="سحب النماذج المتاحة وإصلاح الموديل"
                        >
                          <ArrowDownUp className="size-3" /> نموذج
                        </Button>
                        <Button
                          size="xs"
                          variant="ghost"
                          disabled={busy || isTesting}
                          onClick={() => void post({ action: 'update_provider', id: p.id, enabled: !p.enabled })}
                          className="gap-1 text-muted-foreground text-[11px]"
                        >
                          <CheckCircle2 className="size-3" /> {p.enabled ? 'تعطيل' : 'تفعيل'}
                        </Button>
                        <Button
                          size="xs"
                          variant="ghost"
                          onClick={() => void handleDeleteProvider(p.id, p.name)}
                          disabled={busy || isTesting}
                          className="gap-1 text-rose-400 hover:bg-rose-500/15 hover:text-rose-300 transition-colors"
                          title="حذف هذا النموذج فقط"
                          aria-label={`حذف المزود ${p.name}`}
                        >
                          <Trash2 className="size-3.5" />
                        </Button>
                      </span>
                    </header>

                    <div className="mt-1.5 flex items-center gap-2 text-[10px] text-muted-foreground">
                      <span className="flex items-center gap-1 font-mono" dir="ltr">
                        <KeyRound className="size-3" aria-hidden="true" /> {p.key_masked}
                      </span>
                      <span>•</span>
                      <span>حد الذاكرة: {p.max_tokens} tokens</span>
                    </div>

                    {/* شريط الاستهلاك */}
                    <div className="mt-1.5">
                      <div className="flex items-center justify-between text-[10px]">
                        <span className="text-muted-foreground">استهلاك الجلسة</span>
                        <span className={cn('font-mono tabular-nums', pct >= 85 ? 'text-rose-300' : pct >= 60 ? 'text-amber-300' : 'text-emerald-300')} dir="ltr">
                          {p.usage.total.toLocaleString('en')} / {p.max_tokens.toLocaleString('en')} ({pct}%)
                        </span>
                      </div>
                      <div className="mt-1 h-1 overflow-hidden rounded-full bg-muted">
                        <div className={cn('h-full rounded-full transition-all duration-700', GAUGE_COLOR[p.gauge.level])} style={{ width: `${Math.min(100, pct)}%` }} />
                      </div>
                      {p.last_error && <p className="mt-1 truncate font-mono text-[10px] text-rose-300/80" dir="ltr">{p.last_error}</p>}
                    </div>

                    {/* نافذة إصلاح الموديل */}
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
                              void post({ action: 'update_provider', id: p.id, model })
                            }
                          }}
                          className="max-w-72 rounded-md border border-border bg-background px-2 py-1 font-mono text-xs text-foreground"
                        >
                          <option value="" disabled>— اختر —</option>
                          {fixModels.map((m) => (
                            <option key={m} value={m}>{m}</option>
                          ))}
                        </select>
                        <button type="button" onClick={() => { setFixingId(null); setFixModels([]) }} className="text-[11px] text-muted-foreground">
                          إلغاء
                        </button>
                      </div>
                    ) : null}
                  </article>
                )
              })}
            </div>
          </section>
        ))}
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