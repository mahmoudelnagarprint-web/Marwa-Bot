'use client'

// components/marwa/social-reports-panel.tsx — تقارير السوشيال ميديا (كوكو)
// يعرض التقارير المحفوظة (بطاقات + أعمدة CSS بسيطة للتفاعل) + زر توليد تقرير جديد
// عبر POST /api/facebook/report (كوكو يحلل المنشورات ويكتب التحليل والمقترحات).

import { useCallback, useEffect, useState } from 'react'
import { BarChart3, Loader2, RefreshCw, Sparkles } from 'lucide-react'
import { cn } from '@/lib/utils'

type SocialReport = {
  id: string
  period_label: string
  metrics: { total_posts?: number; total_likes?: number; total_comments?: number; total_shares?: number }
  best_posts: { page?: string; message?: string; likes?: number; comments?: number; engagement?: number }[]
  analysis: string | null
  suggestions: string | null
  created_at: string
}

export function SocialReportsPanel() {
  const [reports, setReports] = useState<SocialReport[]>([])
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch('/api/facebook/report', { cache: 'no-store' })
      const data = await res.json()
      if (!data?.success) {
        setError(data?.error ?? 'خطأ غير معروف')
        return
      }
      setReports(data.reports ?? [])
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const generate = async () => {
    setGenerating(true)
    setError(null)
    try {
      const res = await fetch('/api/facebook/report', { method: 'POST' })
      const data = await res.json()
      if (!data?.success) {
        setError(data?.error ?? 'فشل توليد التقرير')
        return
      }
      void load()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setGenerating(false)
    }
  }

  const maxEng = Math.max(1, ...reports.flatMap((r) => (r.best_posts ?? []).map((b) => b.engagement ?? 0)))

  return (
    <div className="space-y-4" aria-label="تقارير السوشيال ميديا">
      <div className="flex items-center justify-between">
        <p className="flex items-center gap-1.5 text-sm font-medium">
          <BarChart3 className="size-4 text-emerald-300" aria-hidden="true" />
          تقارير السوشيال ميديا — تحليل كوكو الدوري
        </p>
        <button
          type="button"
          onClick={() => void generate()}
          disabled={generating}
          className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
        >
          {generating ? <Loader2 className="size-3.5 animate-spin" /> : <Sparkles className="size-3.5" />}
          {generating ? 'كوكو يحلل الآن…' : 'توليد تقرير جديد'}
        </button>
      </div>

      {error && (
        <p className="rounded-lg border border-rose-400/20 bg-rose-400/10 px-2 py-1 text-xs text-rose-300">⚠️ {error}</p>
      )}
      {loading && (
        <p className="flex items-center gap-2 py-3 text-xs text-muted-foreground" aria-busy="true">
          <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
          جارٍ قراءة التقارير المحفوظة…
        </p>
      )}

      {!loading && reports.length === 0 && (
        <div className="rounded-xl border border-dashed border-border bg-card/40 p-6 text-center">
          <BarChart3 className="mx-auto mb-2 size-7 text-muted-foreground/60" aria-hidden="true" />
          <p className="text-sm font-semibold">لا تقارير محفوظة بعد</p>
          <p className="mt-1 text-xs text-muted-foreground">اضغط «توليد تقرير جديد» — كوكو يحلل آخر المنشورات ويكتب التحليل والمقترحات.</p>
        </div>
      )}

      {reports.map((r) => (
        <div key={r.id} className="rounded-xl border border-border bg-card p-4 space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h4 className="font-display text-sm font-bold text-foreground">📊 {r.period_label}</h4>
            <span className="text-[10px] text-muted-foreground font-mono">
              {new Date(r.created_at).toLocaleString('ar-EG', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}
            </span>
          </div>

          {/* بطاقات المقاييس */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            {[
              { label: 'منشورات', value: r.metrics?.total_posts ?? 0 },
              { label: 'لايكات', value: r.metrics?.total_likes ?? 0 },
              { label: 'تعليقات', value: r.metrics?.total_comments ?? 0 },
              { label: 'مشاركات', value: r.metrics?.total_shares ?? 0 },
            ].map((m) => (
              <div key={m.label} className="rounded-lg border border-border bg-background/60 p-2 text-center">
                <p className="text-lg font-bold text-primary tabular-nums">{m.value}</p>
                <p className="text-[10px] text-muted-foreground">{m.label}</p>
              </div>
            ))}
          </div>

          {/* أفضل البوستات — أعمدة تفاعل بسيطة */}
          {(r.best_posts ?? []).length > 0 && (
            <div className="space-y-1.5">
              <p className="text-[11px] font-medium text-muted-foreground">أعلى المنشورات تفاعلاً:</p>
              {(r.best_posts ?? []).map((b, i) => (
                <div key={i} className="space-y-1">
                  <div className="flex items-center justify-between gap-2 text-[11px]">
                    <span className="truncate text-foreground/90">«{b.message}» — {b.page}</span>
                    <span className="shrink-0 text-muted-foreground tabular-nums">تفاعل {b.engagement}</span>
                  </div>
                  <div className="h-1.5 rounded-full bg-secondary overflow-hidden">
                    <div
                      className="h-full rounded-full bg-gradient-to-l from-primary/80 to-primary/40"
                      style={{ width: `${Math.max(6, Math.round(((b.engagement ?? 0) / maxEng) * 100))}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}

          {r.analysis && (
            <div className="rounded-lg border border-border bg-background/60 p-2.5">
              <p className="mb-1 text-[11px] font-semibold text-sky-300">التحليل المبدئي:</p>
              <p className="whitespace-pre-wrap text-xs leading-relaxed text-foreground/90">{r.analysis}</p>
            </div>
          )}
          {r.suggestions && (
            <div className="rounded-lg border border-emerald-400/20 bg-emerald-400/[0.06] p-2.5">
              <p className="mb-1 text-[11px] font-semibold text-emerald-300">مقترحات الحملة القادمة:</p>
              <p className="whitespace-pre-wrap text-xs leading-relaxed text-foreground/90">{r.suggestions}</p>
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
