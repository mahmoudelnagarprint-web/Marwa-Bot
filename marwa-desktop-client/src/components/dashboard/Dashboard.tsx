'use client'

// components/dashboard/Dashboard.tsx — لوحة القيادة الذكية
// الكروت تتغذى عبر جسر DSH (Tauri/WebSocket) — وبدون جسر: حالة «بانتظار الجسر»
// صادقة مع زر وضع العرض (MOCK) المعنون بوضوح — بلا أرقام وهمية متخفية.
import { useCallback, useEffect, useState } from 'react'
import { cn } from '@/lib/utils'
import { dsh, type TransportKind } from '@/services/dsh-ipc'
import { MOCK_STATS } from '@/services/mock-engine'
import { SmartStatsCard } from './SmartStatsCard'

type Stats = {
  cash_on_hand?: number
  income_window?: number
  receivables?: number
  under_preparation?: { count: number; value: number }
  source?: 'bridge' | 'mock'
  updated_at?: string
}

/** طلب رؤية تحليلية من مروة — عبر الجسر (يُربط بمحرك مروة الحقيقي عند التشغيل داخل Tauri) */
async function askMarwaInsight(title: string, value: number | string): Promise<string | null> {
  try {
    const res = await dsh.call<{ text?: string }>('agent_insight', { title, value: String(value) })
    return res?.text ?? null
  } catch {
    return null // في وضع mock — الزر يعطي رسالة صادقة من داخل الكرت
  }
}

export function Dashboard({ transport }: { transport: TransportKind }) {
  const [stats, setStats] = useState<Stats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await dsh.call<Stats>('dashboard_stats')
      setStats({ ...data, source: transport === 'mock' ? 'mock' : 'bridge', updated_at: new Date().toISOString() })
    } catch (e) {
      // بلا جسر: نعرض وضع العرض الموثوم (MOCK) — بلا ادعاء حياة
      setStats({ ...MOCK_STATS[0], source: 'mock', updated_at: new Date().toISOString() })
      setError(transport === 'mock' ? null : e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }, [transport])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const mock = stats?.source === 'mock'

  return (
    <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-6 scrollbar-thin">
      {/* الترويسة */}
      <div className="space-y-1 border-b border-matte-700/60 pb-4">
        <h1 className="font-display text-2xl md:text-3xl font-bold text-foreground">
          صباح الخير يا محمود
        </h1>
        <p className="text-sm text-muted-foreground">
          غرفة قيادة مروة كور — الأرقام تصل من المحرك المحلي عبر الجسر، وكل كرت يحمل رؤية مروة.
        </p>
      </div>

      {/* شريط الحالة الصادق */}
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span
          className={cn(
            'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 font-medium',
            mock ? 'border-amber-500/30 bg-amber-500/10 text-amber-300' : 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300',
          )}
        >
          {mock ? 'وضع العرض (MOCK) — أضف جسر DSH أو فعّل Tauri للأرقام الحية' : 'متصل بالمحرك الحي'}
        </span>
        <button
          type="button"
          onClick={() => void refresh()}
          className="inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-2.5 py-1 font-medium text-foreground hover:bg-sidebar-accent/60"
        >
          <RefreshCwMini /> تحديث يدوي
        </button>
        {error && <span className="text-rose-300">⚠️ {error}</span>}
      </div>

      {/* شبكة الكروت الذكية */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {loading && !stats ? (
          [0, 1, 2].map((i) => (
            <div key={i} className="h-40 animate-pulse rounded-xl border border-matte-700 bg-matte-850" aria-busy="true" />
          ))
        ) : (
          <>
            <SmartStatsCard
              title="الخزنة النقدية الحالية"
              value={stats?.cash_on_hand}
              unit="ج"
              source={stats?.source}
              updatedAt={stats?.updated_at}
              accent="gold"
              icon={<CoinsIcon />}
              insight={undefined}
              onRequestInsight={() => askMarwaInsight('الخزنة النقدية الحالية', stats?.cash_on_hand ?? '—')}
            />
            <SmartStatsCard
              title="دخل أكتوبر (النافذة الرسمية)"
              value={stats?.income_window}
              unit="ج"
              source={stats?.source}
              updatedAt={stats?.updated_at}
              accent="emerald"
              icon={<TrendIcon />}
              onRequestInsight={() => askMarwaInsight('دخل أكتوبر', stats?.income_window ?? '—')}
            />
            <SmartStatsCard
              title="الآجل المعلق"
              value={stats?.receivables}
              unit="ج"
              source={stats?.source}
              updatedAt={stats?.updated_at}
              accent="rose"
              icon={<CreditIcon />}
              onRequestInsight={() => askMarwaInsight('الآجل المعلق', stats?.receivables ?? '—')}
            />
          </>
        )}
      </div>

      {/* ملاحظة معمارية */}
      <p className="rounded-lg border border-matte-700 bg-matte-850 px-3 py-2 text-[11px] leading-relaxed text-muted-foreground">
        📐 الكروت مصممة لتقبل البيانات عبر <span className="font-mono text-gold-300">Tauri invoke</span> أو{' '}
        <span className="font-mono text-gold-300">WebSocket</span> من المحرك المحلي — وخانة «رؤية تحليلية» في كل كرت
        تُولدها مروة من الرقم نفسه عبر الجسر (لا أرقام متخيلة إطلاقاً).
      </p>
    </div>
  )
}

function RefreshCwMini() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
      <path d="M21 12a9 9 0 1 1-2.64-6.36" />
      <path d="M21 3v6h-6" />
    </svg>
  )
}
function CoinsIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
      <circle cx="8" cy="8" r="6" />
      <path d="M18.09 10.37A6 6 0 1 1 10.34 18" />
      <path d="M7 6h1v4" />
      <path d="m16.71 13.88.7.71-2.82 2.82" />
    </svg>
  )
}
function TrendIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
      <path d="M22 7 13.5 15.5 8.5 10.5 2 17" />
      <path d="M16 7h6v6" />
    </svg>
  )
}
function CreditIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
      <rect width="20" height="14" x="2" y="5" rx="2" />
      <path d="M2 10h20" />
    </svg>
  )
}
