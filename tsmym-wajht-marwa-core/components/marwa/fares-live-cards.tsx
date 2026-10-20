'use client'

// components/marwa/fares-live-cards.tsx — كروت فارس الحية (MARWA CORE task-2)
// الأرقام من /api/fares-summary → القاعدة الحية pos_data.db بوضع قراءة فقط.
// كل رقم موسوم «محسوب من البرنامج» + طابع آخر تحديث (قاعدة المكتب الملزمة §6-6).
// تحديث تلقائي كل 60 ثانية + تحديث يدوي.

import { useCallback, useEffect, useState } from 'react'
import { AlertTriangle, Banknote, Clock3, HandCoins, PiggyBank, RefreshCw, Wallet } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { LIVE_TAG, fetchFaresSummary, formatCairoTime, formatEGP, type FaresSummary } from '@/lib/live'

function LiveCard({
  icon: Icon,
  label,
  value,
  suffix,
  sub,
}: {
  icon: typeof Banknote
  label: string
  value: string
  suffix?: string
  sub?: string
}) {
  return (
    <div className="rounded-lg bg-background/60 p-2.5">
      <p className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
        <Icon className="size-3.5" aria-hidden="true" />
        {label}
      </p>
      <p className="mt-1 flex items-baseline gap-1.5">
        <span className="font-mono text-lg font-medium tabular-nums" dir="ltr">
          {value}
        </span>
        {suffix && <span className="text-[11px] text-muted-foreground">{suffix}</span>}
      </p>
      {sub && <p className="mt-0.5 truncate text-[10px] text-muted-foreground">{sub}</p>}
    </div>
  )
}

function BaselineDiff({ value, base, label }: { value: number; base: number; label: string }) {
  const d = Math.round((value - base) * 100) / 100
  if (d === 0) {
    return (
      <span className="rounded border border-emerald-400/20 bg-emerald-400/[0.08] px-1.5 py-0.5 text-[10px] text-emerald-300">
        مطابق لخط الأساس §9
      </span>
    )
  }
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[10px]',
        d > 0 ? 'border-sky-400/20 bg-sky-400/[0.08] text-sky-300' : 'border-amber-400/20 bg-amber-400/[0.08] text-amber-300',
      )}
    >
      <AlertTriangle className="size-3" aria-hidden="true" />
      {label}: {d > 0 ? '+' : ''}
      {formatEGP(d)} عن خط الأساس §9
    </span>
  )
}

export function FaresLiveCards() {
  const [summary, setSummary] = useState<FaresSummary | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState(false)

  const load = useCallback(async () => {
    setRefreshing(true)
    try {
      setError(null)
      setSummary(await fetchFaresSummary())
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    let alive = true
    void load()
    const id = setInterval(() => {
      if (alive) void load()
    }, 60_000)
    return () => {
      alive = false
    }
  }, [])

  if (error) {
    return (
      <div className="rounded-xl border border-rose-400/20 bg-rose-400/[0.06] p-4 text-sm text-rose-200">
        <p className="font-medium">تعذر قراءة الأرقام الحية من البرنامج</p>
        <p className="mt-1 text-xs text-rose-200/70">{error}</p>
        <Button variant="outline" size="xs" className="mt-3" onClick={() => void load()}>
          إعادة المحاولة
        </Button>
      </div>
    )
  }

  if (!summary) {
    return (
      <div className="grid grid-cols-2 gap-2 md:grid-cols-4" aria-busy="true">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="h-[92px] animate-pulse rounded-lg bg-background/60" />
        ))}
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-2.5">
      <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
        <LiveCard
          icon={PiggyBank}
          label="دخل أكتوبر (نافذة البرنامج)"
          value={formatEGP(summary.income_window)}
          suffix="ج"
          sub={`من ${summary.window_start} — ${LIVE_TAG}`}
        />
        <LiveCard
          icon={Wallet}
          label="الخزنة الفعلية"
          value={formatEGP(summary.cash_on_hand)}
          suffix="ج"
          sub={`افتتاحي ${formatEGP(summary.opening_balance)} + دخل − مصروف ${formatEGP(summary.expenses_window)}`}
        />
        <LiveCard
          icon={HandCoins}
          label="الآجل الحقيقي (أرصدة موجبة)"
          value={formatEGP(summary.receivables)}
          suffix="ج"
          sub={summary.receivables_detail.length
            ? summary.receivables_detail.map((r) => `${r.name} ${formatEGP(r.balance)}`).join(' • ')
            : 'لا أرصدة موجبة'}
        />
        <LiveCard
          icon={HandCoins}
          label="قيد التجهيز"
          value={formatEGP(summary.under_preparation.value)}
          suffix={`ج (${summary.under_preparation.count} طلبات)`}
          sub={`المعلق = آجل ${formatEGP(summary.receivables)} + قيد التجهيز = ${formatEGP(summary.pending_total)} ج`}
        />
      </div>

      {/* شريط التحديث والوسم — إلزامي على كل رقم مالي */}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 text-[11px] text-muted-foreground">
        <span className={cn('inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5', 'border-sky-400/20 bg-sky-400/[0.08] text-sky-300')}>
          <Wallet className="size-3" aria-hidden="true" />
          {LIVE_TAG}
        </span>
        <span className="flex items-center gap-1.5">
          <Clock3 className="size-3.5" aria-hidden="true" />
          آخر تحديث: {formatCairoTime(summary.generated_at)}
        </span>
        <span>
          آخر حركة بالقاعدة: {summary.last_movement ? `#${summary.last_movement.id} — ${formatCairoTime(summary.last_movement.date)}` : '—'}
        </span>
        <span className="rounded bg-background/60 px-1.5 py-0.5 font-mono text-[10px]" dir="ltr">
          {summary.source}
        </span>
        <Button variant="ghost" size="xs" className="h-6 gap-1 px-2" onClick={() => void load()} disabled={refreshing}>
          <RefreshCw className={cn('size-3', refreshing && 'animate-spin')} aria-hidden="true" />
          تحديث
        </Button>
      </div>

      <div className="flex flex-wrap items-center gap-2 text-[11px]">
        <BaselineDiff value={summary.income_window} base={summary.baseline.income} label="دخل أكتوبر" />
        <BaselineDiff value={summary.receivables} base={summary.baseline.receivables} label="الآجل" />
        <BaselineDiff value={summary.cash_on_hand} base={summary.baseline.cash} label="الخزنة" />
        <span className="text-muted-foreground/70">
          خط الأساس المعتمد (§9): دخل {formatEGP(summary.baseline.income)} • آجل {formatEGP(summary.receivables)} • خزنة {formatEGP(summary.baseline.cash)}
        </span>
      </div>
    </div>
  )
}
