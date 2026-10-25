'use client'

import { useCallback, useEffect, useState } from 'react'
import {
  ListTodo, PackageMinus, RefreshCw, Ruler, Scissors, Zap, CheckCheck, Printer,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import type { BoardColumn, InboxItem, ProductionCard } from '@/app/api/production/route'

const money = (n: number) => n.toLocaleString('en-EG')

const COLS: { key: BoardColumn; label: string; icon: typeof Ruler; tone: string; dot: string }[] = [
  { key: 'design', label: 'تجهيز التصميم والمقاسات', icon: Ruler, tone: 'border-teal-400/25 bg-teal-400/[0.05]', dot: 'bg-teal-400' },
  { key: 'printing', label: 'قيد الطباعة/الليزر', icon: Printer, tone: 'border-amber-400/25 bg-amber-400/[0.05]', dot: 'bg-amber-400' },
  { key: 'ready', label: 'جاهز للتسليم', icon: CheckCheck, tone: 'border-emerald-400/25 bg-emerald-400/[0.05]', dot: 'bg-emerald-400' },
]

/** كشف نوع الماكينة من أصناف الطلب — تمهيد لربط صاصا */
function machineFor(items: { name: string; qty: number }[]): { name: string; icon: typeof Printer; tone: string } | null {
  const all = items.map((i) => i.name).join(' ')
  if (/ليزر|خشب|درع|طارة|لوحة|تابلوه/i.test(all)) return { name: 'ليزر CO2', icon: Zap, tone: 'text-rose-300 border-rose-400/25 bg-rose-400/10' }
  if (/فلتر|فلت|فنيل|بنر|طباعة|ورق/i.test(all)) return { name: 'Epson L1800', icon: Printer, tone: 'text-sky-300 border-sky-400/25 bg-sky-400/10' }
  if (/قلم|ستيكر|كاتر|لوجو|logo/i.test(all)) return { name: 'كاتر بلوتر', icon: Scissors, tone: 'text-violet-300 border-violet-400/25 bg-violet-400/10' }
  return null
}

const MACHINES = [
  { name: 'Epson L1800', icon: Printer, tone: 'text-sky-300 border-sky-400/25 bg-sky-400/10' },
  { name: 'ليزر CO2', icon: Zap, tone: 'text-rose-300 border-rose-400/25 bg-rose-400/10' },
  { name: 'كاتر بلوتر', icon: Scissors, tone: 'text-violet-300 border-violet-400/25 bg-violet-400/10' },
] as const

// الربط الحي (تطهير 2026-10-25): حالة الماكينات من دايمون العتاد عبر /api/devices — لا «جاهزة» ثابتة
type HwTelemetry = { id: string; name: string; state: 'Idle' | 'Busy'; metric_label: string; metric_value: number | string; metric_unit: string; simulated: boolean; stale?: boolean; hardware_source?: string }

type Resp = {
  error?: string
  board?: ProductionCard[]
  inbox?: InboxItem[]
}

export function BeboDashboard() {
  const [board, setBoard] = useState<ProductionCard[]>([])
  const [inbox, setInbox] = useState<InboxItem[]>([])
  const [telemetry, setTelemetry] = useState<HwTelemetry[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [flash, setFlash] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [res, hwRes] = await Promise.all([
        fetch('/api/production', { cache: 'no-store' }),
        fetch('/api/devices', { cache: 'no-store' }).catch(() => null),
      ])
      const j = (await res.json()) as Resp
      if (j.error) throw new Error(j.error)
      setBoard(j.board ?? [])
      setInbox(j.inbox ?? [])
      if (hwRes?.ok) {
        const hw = (await hwRes.json()) as { telemetry?: HwTelemetry[] }
        setTelemetry(hw.telemetry ?? [])
      } else {
        setTelemetry([])
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'فشل التحميل')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void load() }, [load])

  async function act(payload: Record<string, unknown>, okMsg: string) {
    setBusy(true)
    setFlash(null)
    try {
      const res = await fetch('/api/production', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const j = (await res.json()) as { ok?: boolean; message?: string; notify?: string }
      if (j.ok) {
        setFlash([okMsg, j.notify].filter(Boolean).join(' • '))
        await load()
      } else {
        setFlash(`⚠️ ${j.message ?? 'فشل'}`)
      }
    } catch {
      setFlash('⚠️ فشل الاتصال')
    } finally {
      setBusy(false)
    }
  }

  async function checkout(orderId: number, items: { name: string; qty: number }[]) {
    const list = items.map((i) => `${i.name} ×${i.qty}`).join('، ')
    // أمر الخامات الحقيقي: /task @fares عبر المحرك من /api/slash
    setBusy(true)
    setFlash(null)
    try {
      const res = await fetch('/api/slash', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: `/task @fares سحب خامات طلب #${orderId}: ${list} — بيحدّدها بيبو من العهدة` }),
      })
      const j = (await res.json()) as { ok?: boolean; file?: string; push?: string; message?: string }
      setFlash(
        j.ok
          ? `🧱 أمر الخامات وصل فارس ${j.push === 'OK' ? 'ودُفع للسحابة' : ''} — ${j.file?.split('\\').pop()}`
          : `⚠️ ${j.message ?? 'المحرك رفض'}`,
      )
    } catch {
      setFlash('⚠️ فشل الاتصال بالمحرك')
    } finally {
      setBusy(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 p-4 text-sm text-muted-foreground">
        <RefreshCw className="size-4 animate-spin" /> بيبو بيجمع الطلبات من قاعدة الورشة…
      </div>
    )
  }
  if (error) {
    return (
      <div className="p-4 text-sm text-rose-300">⚠️ {error}</div>
    )
  }

  return (
    <div className="flex flex-col gap-3 p-3">
      {/* حالة الماكينات — حية من دايمون العتاد (تطهير 2026-10-25) */}
      <div className="grid grid-cols-3 gap-2">
        {MACHINES.map((m) => {
          const t = telemetry.find((x) => x.name === m.name)
          const stateLabel = t
            ? t.stale
              ? 'قديمة — الدايمون غير شغال'
              : t.state === 'Busy'
                ? 'تعمل الآن'
                : t.metric_value === 'غير مربوطة' || t.metric_value === 'offline'
                  ? 'غير مربوطة'
                  : 'خاملة — متصلة'
            : 'دايمون العتاد غير شغال'
          return (
            <div key={m.name} className={cn('flex items-center gap-2 rounded-xl border p-2.5', m.tone)}>
              <m.icon className="size-4" aria-hidden="true" />
              <div className="min-w-0">
                <p className="truncate text-xs font-medium text-foreground" dir="ltr">{m.name}</p>
                <p className="text-[10px] text-muted-foreground">
                  {stateLabel}
                  {t && !t.stale && t.metric_value !== null ? ` • ${t.metric_label}: ${t.metric_value}${t.metric_unit}` : ''}
                </p>
              </div>
            </div>
          )
        })}
      </div>

      {/* كانبان ثلاثي الأعمدة */}
      <div className="grid grid-cols-1 gap-2 md:grid-cols-3">
        {COLS.map((c) => {
          const cards = board.filter((b) => b.col === c.key)
          return (
            <div key={c.key} className={cn('flex min-h-52 flex-col gap-1.5 rounded-xl border p-2.5', c.tone)}>
              <p className="flex items-center gap-1.5 text-xs font-medium">
                <span className={cn('size-1.5 rounded-full', c.dot)} aria-hidden="true" />
                {c.label}
                <span className="ml-auto rounded bg-card px-1.5 font-mono text-[10px] text-muted-foreground">{cards.length}</span>
              </p>
              {cards.length === 0 && <p className="py-6 text-center text-[11px] text-muted-foreground">فاضية</p>}
              {cards.map((card) => {
                const mach = machineFor(card.items)
                return (
                  <div key={card.id} className="rounded-lg border border-border bg-card p-2.5">
                    <div className="flex items-center justify-between gap-1.5">
                      <span className="font-mono text-[10px] text-muted-foreground">#{card.id}</span>
                      <span className="font-mono text-[10px] text-muted-foreground">{money(card.total)} ج</span>
                    </div>
                    <p className="mt-0.5 text-sm font-medium">{card.client}</p>
                    <ul className="mt-1 space-y-0.5 text-[11px] text-muted-foreground">
                      {card.items.map((it) => (
                        <li key={it.name} className="truncate">{it.name} <span className="font-mono">×{it.qty}</span></li>
                      ))}
                    </ul>
                    {mach && (
                      <span className={cn('mt-1.5 inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px]', mach.tone)}>
                        <mach.icon className="size-3" /> {mach.name}
                      </span>
                    )}
                    <div className="mt-2 flex items-center gap-1.5">
                      {COLS.filter((x) => x.key !== c.key).map((x) => (
                        <Button
                          key={x.key}
                          variant="outline"
                          size="sm"
                          disabled={busy}
                          className="h-6 px-1.5 text-[10px]"
                          onClick={() => void act({ action: 'set_column', order_id: card.id, column: x.key }, `↔️ #${card.id} → ${x.label}`)}
                        >
                          → {x.label.split(' ')[0]}
                        </Button>
                      ))}
                      <Button
                        variant="ghost"
                        size="sm"
                        disabled={busy || card.items.length === 0}
                        className="h-6 px-1.5 text-[10px] text-amber-300"
                        onClick={() => void checkout(card.id, card.items)}
                      >
                        <PackageMinus className="size-3" /> لفات
                      </Button>
                    </div>
                  </div>
                )
              })}
            </div>
          )
        })}
      </div>

      {flash && <p className="text-xs text-emerald-300" role="status">{flash}</p>}

      {/* صندوق الوارد النشط */}
      <div className="rounded-xl border border-border p-3">
        <p className="mb-2 flex items-center gap-2 text-sm font-medium">
          <ListTodo className="size-4 text-amber-300" /> صندوق وارد بيبو
          <span className="text-[10px] font-normal text-muted-foreground">(inbox_tasks — حي)</span>
        </p>
        {inbox.length === 0 ? (
          <p className="py-3 text-center text-xs text-muted-foreground">لا مهام حالياً — صندوق فاضي.</p>
        ) : (
          <ul className="flex flex-col gap-1.5">
            {inbox.map((t) => (
              <li key={t.file} className="flex items-center justify-between gap-2 rounded-lg border border-border bg-card px-3 py-2">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">{t.title}</p>
                  <p className="truncate text-[10px] text-muted-foreground" title={t.detail}>
                    {new Date(t.created_at).toLocaleString('ar-EG')}
                    {t.op_id ? ` • ${t.op_id.slice(0, 14)}` : ''}
                  </p>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={busy}
                  className="h-7 shrink-0 px-2 text-[11px] text-emerald-300"
                  onClick={() => void act({ action: 'mark_done', file: t.file }, '✅ تم التنفيذ وأرشفة المهمة')}
                >
                  <CheckCheck className="size-3" /> تم التنفيذ
                </Button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
