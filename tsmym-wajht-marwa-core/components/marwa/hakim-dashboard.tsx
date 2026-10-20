'use client'

import { useCallback, useEffect, useState } from 'react'
import { AlertTriangle, FileSignature, FlaskConical, Image, RefreshCw, Rocket, ScanLine } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

type Bottleneck = { code: string; level: 'red' | 'amber' | 'ok'; message: string }
type Quotation = { id: string; client: string; margin_pct: number; price: number; created_at: string }
type Resp = {
  error?: string
  bottlenecks?: Bottleneck[]
  quotations?: Quotation[]
  templates?: { key: string; title: string }[]
  business_e164?: string
  doc_dir?: string
}

export function HakimDashboard() {
  const [bottlenecks, setBottlenecks] = useState<Bottleneck[]>([])
  const [quotations, setQuotations] = useState<Quotation[]>([])
  const [templates, setTemplates] = useState<{ key: string; title: string }[]>([])
  const [docDir, setDocDir] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [flash, setFlash] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  // 1️⃣ التسعير
  const [client, setClient] = useState('')
  const [items, setItems] = useState('')
  const [machine, setMachine] = useState('ليزر CO2')
  const [materials, setMaterials] = useState(100)
  const [hours, setHours] = useState(1)
  const [margin, setMargin] = useState(30)
  // 3️⃣ العقود
  const [docClient, setDocClient] = useState('')
  const [tpl, setTpl] = useState('receipt')
  // 4️⃣ المحاكي
  const [discount, setDiscount] = useState(15)
  const [sim, setSim] = useState<Record<string, unknown> | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const r = await fetch('/api/hakim', { cache: 'no-store' })
      const j = (await r.json()) as Resp
      if (j.error) throw new Error(j.error)
      setBottlenecks(j.bottlenecks ?? [])
      setQuotations(j.quotations ?? [])
      setTemplates(j.templates ?? [])
      setDocDir(j.doc_dir ?? '')
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
      const r = await fetch('/api/hakim', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
      const j = (await r.json()) as { ok?: boolean; notify?: string; message?: string; quotation?: Quotation; projected_revenue?: number; delta_revenue?: number; verdict?: string; projected_orders?: number; projected_ticket?: number; revenue_now?: number; file?: string; title?: string; bottlenecks?: Bottleneck[] }
      if (payload.action === 'make_quotation' && j.quotation) {
        setFlash(`${okMsg} — ${j.quotation.id} (سعر ${j.quotation.price} ج.م • هامش ${j.quotation.margin_pct}%) • ${j.notify ?? ''}`)
        void load()
      } else if (payload.action === 'make_document') {
        setFlash(`📄 ${j.title ?? 'وثيقة'} použila: ${j.file?.split('\\').pop()}`)
        void load()
      } else if (payload.action === 'scan_bottlenecks') {
        setBottlenecks(j.bottlenecks ?? [])
        setFlash(`👀 مسح الاختناقات — ${j.bottlenecks?.length ?? 0} إشعار`)
      } else {
        setSim({ projected_revenue: j.projected_revenue, delta_revenue: j.delta_revenue, projected_orders: j.projected_orders, projected_ticket: j.projected_ticket, revenue_now: j.revenue_now, verdict: j.verdict })
        setFlash(j.verdict ?? '🎯 محاكاة جاهزة')
      }
    } catch {
      setFlash('⚠️ فشل الاتصال')
    } finally {
      setBusy(false)
    }
  }

  if (loading) return <div className="flex items-center gap-2 p-4 text-sm text-muted-foreground"><RefreshCw className="size-4 animate-spin" /> حكيم بجمع ملفات الحالة وبيانات سلمى…</div>
  if (error) return <div className="p-4 text-sm text-rose-300">⚠️ {error}</div>

  return (
    <div className="flex flex-col gap-3 p-3">

      {flash && <p className="rounded-lg bg-emerald-400/10 px-3 py-2 text-xs text-emerald-300" role="status">{flash}</p>}

      {/* 2️⃣ رادار الاختناقات */}
      <div className="rounded-xl border border-border p-3">
        <div className="mb-2 flex items-center justify-between">
          <p className="flex items-center gap-2 text-sm font-medium"><ScanLine className="size-4 text-rose-300" /> رادار اختناقات الورشة (قراءة صامتة من بيبو+صاصا+سلمى)</p>
          <Button variant="outline" size="sm" disabled={busy} className="h-7 px-2 text-[11px] text-rose-200" onClick={() => void post_({ action: 'scan_bottlenecks' }, '👀')}>
            <RefreshCw className="size-3" /> مسح الآن
          </Button>
        </div>
        <ul className="flex flex-col gap-1">
          {bottlenecks.map((b, i) => (
            <li key={i} className={cn('flex items-start gap-2 rounded-lg border px-2 py-1.5 text-[11px]',
              b.level === 'red' ? 'border-rose-400/40 bg-rose-400/10 text-rose-200' :
              b.level === 'amber' ? 'border-amber-400/30 bg-amber-400/10 text-amber-200' :
              'border-emerald-400/25 bg-emerald-400/10 text-emerald-200')}>
              {b.level === 'ok' ? <Image className="mt-0.5 size-3"> </Image> : <AlertTriangle className="mt-0.5 size-3 shrink-0" />}
              <span>{b.message}</span>
            </li>
          ))}
        </ul>
      </div>

      {/* 1️⃣ حاسبة التسعير */}
      <div className="rounded-xl border border-border p-3">
        <p className="mb-2 flex items-center gap-2 text-sm font-medium"><FileSignature className="size-4 text-amber-300" /> حاسبة التسعير الذكية</p>
        <div className="grid grid-cols-1 gap-1.5 md:grid-cols-2">
          <input value={client} onChange={(e) => setClient(e.target.value)} placeholder="اسم العميل" className="h-7 rounded-lg border border-border bg-card px-2 text-xs outline-none md:col-span-2" />
          <input value={items} onChange={(e) => setItems(e.target.value)} placeholder="البنود (مثال: تابلو خشب 60×80)" className="h-7 rounded-lg border border-border bg-card px-2 text-xs outline-none md:col-span-2" />
          <select value={machine} onChange={(e) => setMachine(e.target.value)} className="h-7 rounded-lg border border-border bg-card px-2 text-xs">
            <option>ليزر CO2</option><option>Epson L1800</option><option>كاتر بلوتر</option><option>يدوي/تجميع</option>
          </select>
          <label className="flex items-center gap-1 text-[11px] text-muted-foreground">خامات <input type="number" value={materials} onChange={(e) => setMaterials(+e.target.value)} className="h-7 w-20 rounded border border-border bg-card px-1 font-mono text-[11px]" /> ج.م</label>
          <label className="flex items-center gap-1 text-[11px] text-muted-foreground">ساعات <input type="number" value={hours} onChange={(e) => setHours(+e.target.value)} step="0.5" className="h-7 w-16 rounded border border-border bg-card px-1 font-mono text-[11px]" /></label>
          <label className="flex items-center gap-1 text-[11px] text-muted-foreground">هامش <input type="number" value={margin} onChange={(e) => setMargin(+e.target.value)} className="h-7 w-16 rounded border border-border bg-card px-1 font-mono text-[11px]" /> %</label>
        </div>
        <Button variant="outline" size="sm" disabled={busy || !client.trim() || !items.trim()} className="mt-2 h-7 px-2 text-[11px] text-amber-200" onClick={() => void post_({ action: 'make_quotation', client, items, machine, materials, hours, margin }, '🚀 عرض السعر أُرسل لصندوق وارد سلمى')}>
          <Rocket className="size-3" /> اعتماد وتحويل لسلمى 🚀
        </Button>
        {quotations.length > 0 && (
          <ul className="mt-2 flex max-h-24 flex-col gap-0.5 overflow-y-auto">
            {quotations.slice(-5).reverse().map((q) => (
              <li key={q.id} className="flex justify-between text-[10px] text-muted-foreground"><span className="truncate">{q.id} — {q.client}</span><span className="font-mono">{q.price} ج.م</span></li>
            ))}
          </ul>
        )}
      </div>

      {/* 3️⃣ صانع العقود B2B */}
      <div className="rounded-xl border border-border p-3">
        <p className="mb-2 flex items-center gap-2 text-sm font-medium"><FileSignature className="size-4 text-sky-300" /> صانع العقود (B2B)</p>
        <div className="flex items-center gap-1.5">
          <select value={tpl} onChange={(e) => setTpl(e.target.value)} className="h-7 rounded-lg border border-border bg-card px-2 text-xs">
            {templates.map((t) => <option key={t.key} value={t.key}>{t.title}</option>)}
          </select>
          <input value={docClient} onChange={(e) => setDocClient(e.target.value)} placeholder="اسم العميل/الشركة" className="h-7 flex-1 rounded-lg border border-border bg-card px-2 text-xs" />
          <Button variant="outline" size="sm" disabled={busy || !docClient.trim()} className="h-7 px-2 text-[11px] text-sky-200" onClick={() => void post_({ action: 'make_document', template: tpl, client: docClient }, '📄 وثيقة')}>
            توليد
          </Button>
        </div>
        <p className="mt-1.5 text-[10px] text-muted-foreground">تُحفظ في <span dir="ltr">{docDir.split('\\').slice(-1)[0]}</span> — Markdown جاهز للطباعة PDF</p>
      </div>

      {/* 4️⃣ المحاكي الاستراتيجي */}
      <div className="rounded-xl border border-border p-3">
        <p className="mb-2 flex items-center gap-2 text-sm font-medium"><FlaskConical className="size-4 text-violet-300" /> المحاكي الاستراتيجي (What-If)</p>
        <div className="flex items-center gap-1.5">
          <label className="flex items-center gap-1 text-[11px] text-muted-foreground">خفض <input type="number" value={discount} onChange={(e) => setDiscount(+e.target.value)} className="h-7 w-16 rounded border border-border bg-card px-1 font-mono text-[11px]" /> %</label>
          <Button variant="outline" size="sm" disabled={busy} className="h-7 px-2 text-[11px] text-violet-200" onClick={() => void post_({ action: 'what_if', discount }, '🎯')}>
            احسب العائد
          </Button>
        </div>
        {sim && (
          <div className="mt-2 grid grid-cols-2 gap-1 text-[11px] md:grid-cols-4">
            <div className="rounded-lg border border-border bg-card px-2 py-1"><p className="text-[9px] text-muted-foreground">إيراد حالي</p><p className="font-mono">{String(sim.revenue_now)} ج.م</p></div>
            <div className="rounded-lg border border-border bg-card px-2 py-1"><p className="text-[9px] text-muted-foreground">إيراد متوقع</p><p className="font-mono text-emerald-300">{String(sim.projected_revenue)} ج.م</p></div>
            <div className="rounded-lg border border-border bg-card px-2 py-1"><p className="text-[9px] text-muted-foreground">دلتا</p><p className={cn('font-mono', Number(sim.delta_revenue) >= 0 ? 'text-emerald-300' : 'text-rose-300')}>{String(sim.delta_revenue)} ج.م</p></div>
            <div className="rounded-lg border border-border bg-card px-2 py-1"><p className="text-[9px] text-muted-foreground">طلبيات متوقعة</p><p className="font-mono">{String(sim.projected_orders)}</p></div>
          </div>
        )}
      </div>
    </div>
  )
}
