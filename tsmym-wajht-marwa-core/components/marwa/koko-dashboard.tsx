'use client'

import { useCallback, useEffect, useState } from 'react'
import {
  Check, ImageIcon, Megaphone, RefreshCw, Search, Sparkles, Zap,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

type VipClient = { id: number; name: string; phone: string; type: string; balance: number }
type AssetHit = { name: string; rel: string; ext: string; size: number }
type TelemetryLite = { id: string; name: string; state: 'Idle' | 'Busy' }

type Resp = {
  error?: string
  vips?: VipClient[]
  assets?: AssetHit[]
  assets_dir?: string
  business_e164?: string
  clip_ready?: boolean
}

/** قراءة رادار صاصا (غرفة التحكم) — نفس مصدر telemetry */
async function fetchSasaRadars(): Promise<TelemetryLite[]> {
  try {
    const r = await fetch('/api/devices', { cache: 'no-store' })
    const j = (await r.json()) as { telemetry?: TelemetryLite[] }
    return j.telemetry ?? []
  } catch {
    return []
  }
}

export function KokoDashboard() {
  const [vips, setVips] = useState<VipClient[]>([])
  const [assets, setAssets] = useState<AssetHit[]>([])
  const [assetsDir, setAssetsDir] = useState('')
  const [bizE164, setBizE164] = useState('')
  const [clipReady, setClipReady] = useState(false)
  const [radars, setRadars] = useState<TelemetryLite[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  // الناشر
  const [post, setPost] = useState('')
  const [imageUrl, setImageUrl] = useState('')
  // البحث البصري
  const [q, setQ] = useState('')
  const [hits, setHits] = useState<AssetHit[] | null>(null)
  // العروض
  const [promo, setPromo] = useState('')
  const [flash, setFlash] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch('/api/koko', { cache: 'no-store' })
      const j = (await res.json()) as Resp
      if (j.error) throw new Error(j.error)
      setVips(j.vips ?? [])
      setAssets(j.assets ?? [])
      setAssetsDir(j.assets_dir ?? '')
      setBizE164(j.business_e164 ?? '')
      setClipReady(Boolean(j.clip_ready))
      setRadars(await fetchSasaRadars())
    } catch (e) {
      setError(e instanceof Error ? e.message : 'فشل التحميل')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void load() }, [load])

  async function post_(payload: Record<string, unknown>, okMsg: string) {
    setBusy(true)
    setFlash(null)
    try {
      const res = await fetch('/api/koko', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const j = (await res.json()) as { ok?: boolean; notify?: string; message?: string; preview?: string; hits?: AssetHit[]; hint?: string }
      if (payload.action === 'asset_search') {
        setHits(j.hits ?? [])
        setFlash(j.hint ?? j.message ?? null)
      } else {
        setFlash([j.ok ? okMsg : `⚠️ ${j.message ?? 'فشل'}`, j.notify].filter(Boolean).join(' • '))
        if (j.preview) setPromo(j.preview)
      }
    } catch {
      setFlash('⚠️ فشل الاتصال')
    } finally {
      setBusy(false)
    }
  }

  const laser = radars.find((r) => r.id === 'laser')
  const laserIdle = laser?.state === 'Idle'

  if (loading) return <div className="flex items-center gap-2 p-4 text-sm text-muted-foreground"><RefreshCw className="size-4 animate-spin" /> كوكو بتجمع الوسائط والعملاء…</div>
  if (error) return <div className="p-4 text-sm text-rose-300">⚠️ {error}</div>

  return (
    <div className="flex flex-col gap-3 p-3">
      {/* 4️⃣ العروض اللحظية — من رادار صاصا */}
      {laserIdle && (
        <div className="flex items-center justify-between gap-2 rounded-xl border border-amber-400/30 bg-amber-400/10 p-2.5">
          <p className="text-xs text-amber-200">⚡ الماكينة (ليزر CO2) فارغة — هل نُطلق عرض خصم سريع؟</p>
          <Button
            variant="outline"
            size="sm"
            disabled={busy}
            className="h-7 shrink-0 px-2 text-[11px] text-amber-200"
            onClick={() => {
              setPromo('🔥 عرض لحظي: خصم 15% على أعمال الليزر لأول 5 طلبيات اليوم — النجار برنت 📞 01000433420')
              setFlash('✨ تولّد بوست جاهز — راجعيه وانشره')
            }}
          >
            <Sparkles className="size-3" /> توليد بوست
          </Button>
        </div>
      )}

      {/* 1️⃣ الناشر الآلي */}
      <div className="rounded-xl border border-border p-3">
        <p className="mb-2 flex items-center gap-2 text-sm font-medium"><Megaphone className="size-4 text-fuchsia-300" /> الناشر الآلي (فيسبوك)</p>
        <textarea
          value={post}
          onChange={(e) => setPost(e.target.value)}
          rows={3}
          placeholder="اكتبي نص العرض الترويجي هنا… (رقم البزنس 01000433420 يضاف تلقائياً في رموز الـCTA)"
          className="w-full resize-none rounded-lg border border-border bg-card p-2 text-xs outline-none focus:ring-1 focus:ring-fuchsia-400/40"
        />
        <div className="mt-1.5 flex items-center gap-1.5">
          <input
            value={imageUrl}
            onChange={(e) => setImageUrl(e.target.value)}
            placeholder="مسار صورة (اختياري) — مثال: designs/banner.png"
            dir="ltr"
            className="h-7 flex-1 rounded-lg border border-border bg-card px-2 font-mono text-[11px] outline-none focus:ring-1 focus:ring-fuchsia-400/40"
          />
          <Button variant="outline" size="sm" disabled={busy || !post.trim()} className="h-7 px-2 text-[11px] text-fuchsia-200" onClick={() => void post_({ action: 'fb_publish', content: post, image: imageUrl }, '🚀 نُشر على فيسبوك')}>
            زر النشر 🚀
          </Button>
        </div>
      </div>

      {flash && <p className="text-xs text-emerald-300" role="status">{flash}</p>}

      {/* 2️⃣ البحث البصري */}
      <div className="rounded-xl border border-border p-3">
        <p className="mb-2 flex items-center gap-2 text-sm font-medium">
          <ImageIcon className="size-4 text-sky-300" /> البحث البصري في أصول الورشة
          <span className={cn('rounded px-1.5 py-0.5 text-[9px]', clipReady ? 'bg-emerald-400/15 text-emerald-300' : 'bg-zinc-400/10 text-zinc-400')}>
            {clipReady ? 'CLIP جاهز' : 'بحث نصي (ربط CLIP/ChromaDB قيد الانتظار)'}
          </span>
        </p>
        <div className="flex items-center gap-1.5">
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && q.trim()) void post_({ action: 'asset_search', query: q }, '') }}
            placeholder="ابحثي: تابلوه خشب…"
            className="h-7 flex-1 rounded-lg border border-border bg-card px-2 text-xs outline-none focus:ring-1 focus:ring-sky-400/40"
          />
          <Button variant="outline" size="sm" disabled={busy || !q.trim()} className="h-7 px-2 text-[11px] text-sky-200" onClick={() => void post_({ action: 'asset_search', query: q }, '')}>
            <Search className="size-3" /> ابحثي
          </Button>
        </div>
        {hits !== null && (
          hits.length === 0 ? (
            <p className="py-2 text-center text-[11px] text-muted-foreground">لا نتائج — جربي كلمة أخف (تُفهرس أسماء الملفات فقط).</p>
          ) : (
            <ul className="mt-2 grid max-h-40 grid-cols-1 gap-1 overflow-y-auto md:grid-cols-2">
              {hits.map((h) => (
                <li key={h.rel} className="flex items-center justify-between rounded-lg border border-border bg-card px-2 py-1.5">
                  <span className="truncate font-mono text-[10px]" dir="ltr">{h.rel}</span>
                  <Check className="size-3 shrink-0 text-emerald-300" />
                </li>
              ))}
            </ul>
          )
        )}
        {hits === null && assets.length > 0 && (
          <p className="mt-2 text-[10px] text-muted-foreground">{assets.length} أصل وسائط مفهرس من <span dir="ltr">{assetsDir}</span></p>
        )}
      </div>

      {/* 3️⃣ مدفع الواتساب الترويجي */}
      <div className="rounded-xl border border-border p-3">
        <p className="mb-2 flex items-center gap-2 text-sm font-medium">
          <Zap className="size-4 text-emerald-300" /> مدفع الواتساب (عملاء VIP من غرفة سلمى)
          <span className="rounded bg-zinc-400/10 px-1.5 py-0.5 font-mono text-[9px] text-zinc-300" dir="ltr">{bizE164}</span>
        </p>
        <textarea
          value={promo}
          onChange={(e) => setPromo(e.target.value)}
          rows={2}
          placeholder="نص العرض المجمع… (اتصال CTA يضاف تلقائياً)"
          className="w-full resize-none rounded-lg border border-border bg-card p-2 text-xs outline-none focus:ring-1 focus:ring-emerald-400/40"
        />
        <div className="mt-1.5 flex items-center justify-between gap-2">
          <span className="text-[11px] text-muted-foreground">🎯 {vips.length} عميل VIP (جملة / مدين / عرائس)</span>
          <Button variant="outline" size="sm" disabled={busy || !promo.trim()} className="h-7 px-2 text-[11px] text-emerald-200" onClick={() => void post_({ action: 'wa_broadcast', promo }, '📢 العرض جاهز — مرّره لسلمى')}>
            <Megaphone className="size-3" /> إرسال عرض مجمع 📢
          </Button>
        </div>
        {vips.length > 0 && (
          <ul className="mt-1.5 flex max-h-24 flex-col gap-0.5 overflow-y-auto">
            {vips.slice(0, 8).map((v) => (
              <li key={v.id} className="flex items-center justify-between rounded px-1.5 py-0.5 text-[10px] text-muted-foreground">
                <span className="truncate">{v.name}{v.type === 'Wholesale' ? ' • جملة' : v.balance > 0 ? ` • دين ${v.balance}` : ''}</span>
                <span className="font-mono" dir="ltr">{v.phone || 'بلا رقم'}</span>
              </li>
            ))}
            {vips.length > 8 && <li className="text-[10px] text-muted-foreground">+{vips.length - 8} آخرين…</li>}
          </ul>
        )}
      </div>
    </div>
  )
}
