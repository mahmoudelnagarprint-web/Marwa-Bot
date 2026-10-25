'use client'

// components/dashboard/SmartStatsCard.tsx — كرت إحصاء ذكي (بلا أرقام وهمية)
// MARWA CORE task-8:
//   • القيمة تصل عبر جسر DSH (Tauri invoke / WebSocket) — ولا رقم ثابت في الكود
//   • خانة «رؤية تحليلية سريعة (AI Insight)» — تُولدها مروة من الرقم عبر الجسر
//     بزر طلب صريح (Sparkles) — والنتيجة تظهر تحت الرقم بأنياقة
//   • شارة المصدر صادقة: حي (J via bridge) أو MOCK (وضع عرض — مُعلَّم بوضوح)
import { useState } from 'react'
import { Sparkles, Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'

export type StatCardProps = {
  title: string
  value?: number | string
  unit?: string
  /** توقيت آخر تحديث من المحرك */
  updatedAt?: string
  /** المصدر: bridge = من المحرك الحي • mock = وضع العرض • undefined = لم يصل بعد */
  source?: 'bridge' | 'mock'
  /** الرؤية التحليلية الجاهزة (إن ولّدها المحرك مع الرقم) */
  insight?: string
  /** طلب رؤية جديدة من مروة عبر الجسر */
  onRequestInsight?: () => Promise<string | null>
  icon?: React.ReactNode
  accent?: 'gold' | 'sky' | 'emerald' | 'rose'
}

const ACCENT: Record<NonNullable<StatCardProps['accent']>, { border: string; bg: string; text: string }> = {
  gold: { border: 'border-gold-800/60', bg: 'bg-gold-400/[0.06]', text: 'text-gold-400' },
  sky: { border: 'border-sky-500/30', bg: 'bg-sky-500/[0.06]', text: 'text-sky-300' },
  emerald: { border: 'border-emerald-500/30', bg: 'bg-emerald-500/[0.06]', text: 'text-emerald-300' },
  rose: { border: 'border-rose-500/30', bg: 'bg-rose-500/[0.06]', text: 'text-rose-300' },
}

export function SmartStatsCard({
  title,
  value,
  unit = 'ج',
  updatedAt,
  source,
  insight,
  onRequestInsight,
  icon,
  accent = 'gold',
}: StatCardProps) {
  const [localInsight, setLocalInsight] = useState<string | null>(null)
  const [insightBusy, setInsightBusy] = useState(false)
  const [insightError, setInsightError] = useState<string | null>(null)
  const shown = localInsight ?? insight ?? null
  const accentCls = ACCENT[accent]

  const askInsight = async () => {
    if (!onRequestInsight) return
    setInsightBusy(true)
    setInsightError(null)
    try {
      const res = await onRequestInsight()
      setLocalInsight(res ?? 'لم تتوفر رؤية الآن — أعد المحاولة')
    } catch (e) {
      setInsightError(e instanceof Error ? e.message : String(e))
    } finally {
      setInsightBusy(false)
    }
  }

  const isMock = source === 'mock'
  const valueDisplay =
    value === undefined
      ? '—'
      : typeof value === 'number'
        ? value.toLocaleString('ar-EG', { maximumFractionDigits: 2 })
        : value

  return (
    <div className={cn('relative overflow-hidden rounded-xl border bg-matte-850 p-4 transition-all', accentCls.border, isMock && 'opacity-95')}>
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-muted-foreground">{title}</span>
        {icon && <div className={cn('flex size-8 items-center justify-center rounded-lg', accentCls.bg, accentCls.text)}>{icon}</div>}
      </div>

      <div className="mt-3 flex items-baseline gap-2">
        <span dir="ltr" className="font-display text-2xl md:text-3xl font-bold tracking-tight text-foreground tabular-nums">
          {valueDisplay}
        </span>
        {unit && value !== undefined && <span className="font-display text-sm font-semibold text-muted-foreground">{unit}</span>}
      </div>

      {/* شارة المصدر الصادقة */}
      <p className="mt-2 text-[11px] text-muted-foreground flex items-center gap-1.5">
        {source === 'bridge' ? (
          <span className="rounded border border-emerald-500/30 bg-emerald-500/10 px-1.5 py-0.5 text-[10px] text-emerald-300 font-mono">حي — من المحرك</span>
        ) : source === 'mock' ? (
          <span className="rounded border border-amber-500/30 bg-amber-500/10 px-1.5 py-0.5 text-[10px] text-amber-300 font-mono">MOCK — وضع العرض</span>
        ) : (
          <span className="rounded border border-border bg-matte-800 px-1.5 py-0.5 text-[10px] font-mono">بانتظار الجسر…</span>
        )}
        {updatedAt && <span className="font-mono">{new Date(updatedAt).toLocaleTimeString('ar-EG', { hour: '2-digit', minute: '2-digit' })}</span>}
      </p>

      {/* خانة الرؤية التحليلية السريعة (AI Insight) — توليدها مروة عبر الجسر */}
      <div className="mt-3 border-t border-matte-700 pt-2.5">
        {shown ? (
          <p className="text-[11px] leading-relaxed text-gold-200 flex items-start gap-1.5">
            <Sparkles className="mt-0.5 size-3 shrink-0 text-gold-400" aria-hidden="true" />
            <span className="min-w-0">{shown}</span>
          </p>
        ) : (
          <button
            type="button"
            onClick={() => void askInsight()}
            disabled={insightBusy || value === undefined}
            className="inline-flex items-center gap-1.5 rounded-md border border-gold-800/60 px-2 py-1 text-[10px] font-medium text-gold-300 transition-colors hover:bg-gold-400/10 disabled:opacity-40"
            title="اطلب من مروة رؤية تحليلية سريعة على هذا الرقم"
          >
            {insightBusy ? <Loader2 className="size-3 animate-spin" /> : <Sparkles className="size-3" />}
            رؤية تحليلية من مروة
          </button>
        )}
        {insightError && <p className="mt-1 text-[10px] text-rose-300">⚠️ {insightError}</p>}
      </div>
    </div>
  )
}
