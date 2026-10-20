'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle, Boxes, Building2, CheckCheck, Clock, Copy, Crown,
  HandCoins, MessageCircle, PackageSearch, Phone, RefreshCw, Users, Zap,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import type { SalmaOrder, SalmaSummary } from '@/app/api/salma-summary/route'

type Filter = 'all' | 'debtors_only' | 'under_prep' | 'ready'

const money = (n: number) => n.toLocaleString('en-EG')

/** رسالة واتساب حسب الحالة (عتاب مدين / استعجال / إبلاغ بالاستلام) */
function waText(o: SalmaOrder, mode: 'debt' | 'rush' | 'ready'): string | null {
  if (!o.phoneE164) return null
  if (mode === 'debt') {
    return `مساء الخير ${o.client} 🌹\nمعاك سلمى من ورشة النجار برنت.\nعلى رأسي ملاحظة صغيرة: في مبلغ ${money(o.balance)} ج متأخر على حسابكم، ولو اتسوى النهاردة الأوردرات الجاية تدور أسرع 🙏`
  }
  if (mode === 'rush') {
    return `أهلاً ${o.client} 👋\nطلبكم رقم #${o.id} تحت التنفيذ حاليًا في الورشة وهي داخلة على خط الإنتاج.\nهبلّغكم فور جهوزيته — ومحتاج منكم موعد التسليم المناسب 🕒`
  }
  return `حيّاك الله ${o.client} 🎉\nطلبكم رقم #${o.id} جهز وحاجز للاستلام من الورشة.\nسعدنا بخدمتكم ونستنى رأيكم بعد التسليم ✨`
}

function waLink(phone: string, text: string): string {
  return `https://wa.me/${phone}?text=${encodeURIComponent(text)}`
}

const statusChip: Record<string, string> = {
  'Under Preparation': 'border-amber-400/30 bg-amber-400/10 text-amber-300',
  Ready: 'border-emerald-400/30 bg-emerald-400/10 text-emerald-300',
}

export function SalmaDashboard({ agentId }: { agentId?: string }) {
  const [data, setData] = useState<SalmaSummary | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<Filter>('all')
  const [showShortages, setShowShortages] = useState(false)
  const [rushBusy, setRushBusy] = useState(false)
  const [rushMsg, setRushMsg] = useState<string | null>(null)
  const [morningSeen, setMorningSeen] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch('/api/salma-summary', { cache: 'no-store' })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const j = (await res.json()) as SalmaSummary & { error?: string }
      if (j.error) throw new Error(j.error)
      setData(j)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'فشل التحميل')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void load() }, [load])

  // ملخص الصباح: يظهر تلقائياً عند فتح الواجهة (we د) ويختفي بزر
  const showMorning = data && !morningSeen

  const filtered = useMemo(() => {
    if (!data) return []
    if (filter === 'debtors_only') return data.orders.filter((o) => o.balance > 0)
    if (filter === 'under_prep') return data.orders.filter((o) => o.status === 'Under Preparation')
    if (filter === 'ready') return data.orders.filter((o) => o.status === 'Ready')
    return data.orders
  }, [data, filter])

  /** استعجال بيبو: أمر /task @bebo حقيقي عبر المحرك (لا تدخل من المالك) */
  async function rushBebo(orderId: number, client: string, product?: string) {
    setRushBusy(true)
    setRushMsg(null)
    try {
      const res = await fetch('/api/slash', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text: `/task @bebo استعجال طلب #${orderId} (${client})${product ? ` — ${product}` : ''} — من لوحة سلمى`,
        }),
      })
      const j = (await res.json()) as { ok?: boolean; push?: string; file?: string; message?: string }
      setRushMsg(
        j.ok
          ? `⚡ استعجال وصل بيبو ${j.push === 'OK' ? 'ودُفع للسحابة' : ''} — الملف: ${j.file?.split('\\').pop()}`
          : `⚠️ ${j.message ?? 'المحرك رفض الأمر'}`,
      )
    } catch {
      setRushMsg('⚠️ فشل الاتصال بمحرك التوجيه')
    } finally {
      setRushBusy(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 p-4 text-sm text-muted-foreground">
        <RefreshCw className="size-4 animate-spin" /> سلمى بتجمع الموقف من قاعدة الورشة…
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

  const k = data.kpis
  const kpiCards = [
    { label: 'عملاء نشطون', value: money(k.active_clients), icon: Users, tone: 'text-sky-300 border-sky-400/20 bg-sky-400/10' },
    { label: 'طلبات مفتوحة', value: `${money(k.open_orders)} • ${money(k.open_orders_value)} ج`, icon: Boxes, tone: 'text-teal-300 border-teal-400/20 bg-teal-400/10' },
    { label: 'آجل مستحق', value: `${money(k.receivables_total)} ج`, icon: HandCoins, tone: 'text-rose-300 border-rose-400/20 bg-rose-400/10' },
    { label: 'تسليمات جاهزة', value: `${money(k.ready_orders)} • ${money(k.ready_value)} ج`, icon: CheckCheck, tone: 'text-emerald-300 border-emerald-400/20 bg-emerald-400/10' },
  ]

  return (
    <div className="flex flex-col gap-4 p-4">
      {/* ملخص الصباح الذكي */}
      {showMorning ? (
        <div className="relative rounded-xl border border-rose-400/25 bg-gradient-to-l from-rose-400/[0.10] to-transparent p-4">
          <div className="flex items-start gap-3">
            <MessageCircle className="mt-0.5 size-5 shrink-0 text-rose-300" aria-hidden="true" />
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-foreground">{data.summary_message}</p>
              <p className="mt-1 text-[10px] text-muted-foreground">
                {data.tag} • {data.source} • {new Date(data.computed_at).toLocaleTimeString('ar-EG')}
              </p>
            </div>
            <Button variant="ghost" size="xs" onClick={() => setMorningSeen(true)} aria-label="إخفاء الملخص">✕</Button>
          </div>
        </div>
      ) : null}

      {/* KPIs */}
      <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
        {kpiCards.map((c) => (
          <div key={c.label} className={cn('rounded-xl border p-3', c.tone)}>
            <c.icon className="size-4" aria-hidden="true" />
            <p className="mt-2 truncate text-sm font-semibold text-foreground">{c.value}</p>
            <p className="text-[11px] text-muted-foreground">{c.label}</p>
          </div>
        ))}
      </div>

      {/* شريط الأدوات: فلاتر + جدول النواقص */}
      <div className="flex flex-wrap items-center gap-2">
        {([
          ['all', `الكل (${k.open_orders})`],
          ['debtors_only', `المدينون فقط (${k.debtors_count})`],
          ['under_prep', `تحت التجهيز (${k.under_preparation})`],
          ['ready', `جاهز للاستلام (${k.ready_orders})`],
        ] as [Filter, string][]).map(([f, label]) => (
          <Button
            key={f}
            variant={filter === f ? 'default' : 'outline'}
            size="sm"
            onClick={() => setFilter(f)}
          >
            {label}
          </Button>
        ))}
        <Button
          variant={showShortages ? 'default' : 'outline'}
          size="sm"
          onClick={() => setShowShortages((s) => !s)}
        >
          <PackageSearch className="size-4" /> جدول نواقص الإنتاج
        </Button>
      </div>

      {/* جدول تجميع نواقص الإنتاج (الميزة الجوهرية) — لسحب الخامات دفعة واحدة */}
      {showShortages && data.aggregation.length > 0 && (
        <div className="rounded-xl border border-amber-400/25 bg-amber-400/[0.06] p-3">
          <p className="mb-2 flex items-center gap-2 text-sm font-medium text-amber-200">
            <PackageSearch className="size-4" /> تجميع نواقص الطلبات المفتوحة — اسحب الخامات دفعة واحدة
            <span className="text-[10px] font-normal text-muted-foreground">({data.tag})</span>
          </p>
          <ul className="grid grid-cols-1 gap-1.5 sm:grid-cols-2 lg:grid-cols-3">
            {data.aggregation.map((a) => (
              <li
                key={a.product}
                className="flex items-center justify-between gap-2 rounded-lg border border-border bg-card px-3 py-2 text-sm"
              >
                <span className="truncate">{a.product}</span>
                <span className="shrink-0 rounded bg-amber-400/15 px-2 py-0.5 font-mono text-xs text-amber-200">
                  ×{a.total_qty}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {showShortages && data.aggregation.length === 0 && (
        <p className="text-xs text-muted-foreground">لا نواقص تجميعية — الطلبات المفتوحة فاضية.</p>
      )}

      {/* جدول الطلبات */}
      <div className="overflow-hidden rounded-xl border border-border">
        <table className="w-full text-right text-sm">
          <thead className="bg-muted/40 text-[11px] text-muted-foreground">
            <tr>
              <th className="px-3 py-2 font-medium">#</th>
              <th className="px-3 py-2 font-medium">العميل</th>
              <th className="px-3 py-2 font-medium">الحالة</th>
              <th className="px-3 py-2 font-medium">القيمة</th>
              <th className="px-3 py-2 font-medium">الإجراءات</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {filtered.map((o) => (
              <tr key={o.id} className="hover:bg-muted/20">
                <td className="px-3 py-2 font-mono text-xs text-muted-foreground">#{o.id}</td>
                <td className="px-3 py-2">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <span className="font-medium">{o.client}</span>
                    {o.vip && (
                      <span className="inline-flex items-center gap-0.5 rounded bg-fuchsia-400/15 px-1.5 py-0.5 text-[10px] text-fuchsia-300">
                        <Crown className="size-3" /> {o.client_type === 'Wholesale' ? 'جملة' : 'VIP'}
                      </span>
                    )}
                    {o.balance > 0 && (
                      <span className="rounded bg-rose-400/15 px-1.5 py-0.5 text-[10px] text-rose-300 font-mono">
                        دين {money(o.balance)}
                      </span>
                    )}
                  </div>
                  <p className="text-[10px] text-muted-foreground">
                    <Clock className="mr-1 inline size-3" />
                    {o.date?.slice(0, 16).replace('T', ' ')}
                    {o.client_type === 'Wholesale' ? ' • جملة' : ''}
                  </p>
                </td>
                <td className="px-3 py-2">
                  <span className={cn('inline-flex items-center gap-1 rounded border px-2 py-0.5 text-[11px]', statusChip[o.status] ?? 'border-border text-muted-foreground')}>
                    {o.status === 'Under Preparation' ? 'تحت التجهيز' : o.status === 'Ready' ? 'جاهز' : o.status}
                  </span>
                  {k.late_orders > 0 && o.status === 'Under Preparation' && (
                    <AlertTriangle className="mr-1 inline size-3 text-amber-300" aria-label="متأخر" />
                  )}
                </td>
                <td className="px-3 py-2 font-mono text-xs">{money(o.total)} ج</td>
                <td className="px-3 py-2">
                  <div className="flex flex-wrap items-center gap-1.5">
                    {o.status === 'Ready' && o.phoneE164 ? (
                      <a
                        href={waLink(o.phoneE164, waText(o, 'ready') ?? '')}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 rounded-md border border-emerald-400/30 bg-emerald-400/10 px-2 py-1 text-[11px] text-emerald-300 hover:bg-emerald-400/20"
                      >
                        <MessageCircle className="size-3" /> واتساب: بلّغ بالاستلام
                      </a>
                    ) : o.status !== 'Ready' && o.phoneE164 ? (
                      <a
                        href={waLink(o.phoneE164, waText(o, 'rush') ?? '')}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 rounded-md border border-sky-400/30 bg-sky-400/10 px-2 py-1 text-[11px] text-sky-300 hover:bg-sky-400/20"
                      >
                        <MessageCircle className="size-3" /> واتساب: استعجال
                      </a>
                    ) : (
                      <span className="text-[11px] text-muted-foreground">لا رقم واتساب</span>
                    )}
                    {o.balance > 0 && o.phoneE164 && (
                      <a
                        href={waLink(o.phoneE164, waText(o, 'debt') ?? '')}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 rounded-md border border-rose-400/30 bg-rose-400/10 px-2 py-1 text-[11px] text-rose-300 hover:bg-rose-400/20"
                      >
                        <HandCoins className="size-3" /> واتساب: عاتب في الديون
                      </a>
                    )}
                    {o.status === 'Under Preparation' ? (
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={rushBusy}
                        onClick={() => void rushBebo(o.id, o.client)}
                        className="h-7 px-2 text-[11px]"
                      >
                        <Zap className="size-3" /> استعجال بيبو
                      </Button>
                    ) : null}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {filtered.length === 0 && (
          <p className="p-4 text-center text-xs text-muted-foreground">لا طلبات في هذا الفلتر.</p>
        )}
      </div>

      {rushMsg && <p className="text-xs text-emerald-300" role="status">{rushMsg}</p>}

      {/* دفتر المدينين السريع */}
      <div className="rounded-xl border border-border p-3">
        <p className="mb-2 flex items-center gap-2 text-sm font-medium">
          <Building2 className="size-4 text-rose-300" /> دفتر التحصيل (المديونية الموجبة)
          <span className="text-[10px] font-normal text-muted-foreground">({data.tag})</span>
        </p>
        <ul className="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
          {data.debtors.map((d) => (
            <li key={d.id} className="flex items-center justify-between gap-2 rounded-lg border border-border bg-card px-3 py-2 text-sm">
              <span className="truncate">{d.name}<span className="text-rose-300"> {money(d.balance)} ج</span></span>
              <div className="flex shrink-0 items-center gap-1">
                {d.phoneE164 ? (
                  <>
                    <a
                      href={waLink(d.phoneE164, `مساء الخير ${d.name} 🌹\nمعاك سلمى من ورشة النجار برنت.\nفي مبلغ ${money(d.balance)} ج مفتوح على الحساب — لو مصرّفه النهاردة نسجل الطلب الجديد فوراً 🙏`)}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1 rounded-md border border-emerald-400/30 bg-emerald-400/10 px-2 py-1 text-[11px] text-emerald-300 hover:bg-emerald-400/20"
                    >
                      <MessageCircle className="size-3" /> عاتب
                    </a>
                    <a
                      href={`tel:+${d.phoneE164}`}
                      className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-[11px] text-muted-foreground hover:bg-muted/30"
                    >
                      <Phone className="size-3" /> اتصال
                    </a>
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      aria-label="نسخ رقم الهاتف"
                      title={d.phone ?? d.phoneE164 ?? ''}
                      onClick={() => void navigator.clipboard?.writeText(d.phoneE164 ?? '')}
                    >
                      <Copy className="size-3" />
                    </Button>
                  </>
                ) : (
                  <span className="text-[11px] text-muted-foreground">بدون رقم</span>
                )}
              </div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
