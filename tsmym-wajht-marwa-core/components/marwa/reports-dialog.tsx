'use client'

// components/marwa/reports-dialog.tsx — التقارير الموحدة (MARWA CORE)
// مُطهَّر (task-2 فيجن): لا أرقام وهمية (كانت 15.2K/37/94%/مساهمات متخيلة).
// مؤشرات الشريط العلوي = أرقام فارس الحية من /api/fares-summary (محسوب من
// البرنامج). أحدث التقارير تُقرأ من مصفوفة التقارير الفعلية للوكلاء (فارغة
// حتى تفعيل طبقة التقارير الرسمية).

import { useState } from 'react'
import { BarChart3 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { LIVE_TAG, fetchFaresSummary, formatEGP, type FaresSummary } from '@/lib/live'
import { agents } from '@/lib/marwa-data'
import { AgentAvatar } from './agent-avatar'

const barColor: Record<string, string> = {
  salma: 'bg-rose-300/70',
  fares: 'bg-sky-300/70',
  bebo: 'bg-amber-300/70',
  koko: 'bg-emerald-300/70',
  rased: 'bg-violet-300/70',
  vision: 'bg-indigo-300/70',
}

export function ReportsDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
  const [summary, setSummary] = useState<FaresSummary | null>(null)
  const [err, setErr] = useState<string | null>(null)

  function loadOnce() {
    setErr(null)
    fetchFaresSummary()
      .then(setSummary)
      .catch((e) => setErr(e instanceof Error ? e.message : String(e)))
  }

  const recent = agents
    .flatMap((a) => a.reports.map((r) => ({ ...r, agent: a })))
    .slice(0, 6)

  return (
    <Dialog
      open={open}
      onOpenChange={(v) => {
        if (v) loadOnce()
        onOpenChange(v)
      }}
    >
      <DialogContent className="max-h-[85dvh] overflow-y-auto sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <BarChart3 className="size-4 text-sky-300" aria-hidden="true" />
            التقارير الموحدة
          </DialogTitle>
          <DialogDescription>
            المؤشرات الرسمية من البرنامج — {LIVE_TAG}. بقية التقارير تُبنى عند تفعيل طبقات كل وكيل (task-3).
          </DialogDescription>
        </DialogHeader>

        {err && (
          <p className="rounded-lg border border-rose-400/20 bg-rose-400/[0.06] p-2 text-xs text-rose-200">
            تعذر قراءة الأرقام الحية: {err}
          </p>
        )}

        {summary ? (
          <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
            {[
              { label: 'دخل أكتوبر', value: summary.income_window },
              { label: 'الخزنة', value: summary.cash_on_hand },
              { label: 'الآجل الحقيقي', value: summary.receivables },
              { label: 'قيد التجهيز', value: summary.under_preparation.value },
            ].map((k) => (
              <div key={k.label} className="rounded-xl border border-border bg-card p-3">
                <p className="text-xs text-muted-foreground">{k.label}</p>
                <p className="mt-1 font-mono text-2xl font-medium tabular-nums" dir="ltr">
                  {formatEGP(k.value)}
                </p>
                <p className="text-[10px] text-muted-foreground">ج — {LIVE_TAG}</p>
              </div>
            ))}
            <p className="col-span-2 text-[10px] text-muted-foreground md:col-span-4">
              نافذة المحاسبة: من {summary.window_start} (settings) • آخر تحديث: {summary.generated_at} • المصدر: {summary.source}
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-2 md:grid-cols-4" aria-busy="true">
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="h-[84px] animate-pulse rounded-xl bg-card" />
            ))}
          </div>
        )}

        <div className="grid gap-3 md:grid-cols-2">
          <section className="rounded-xl border border-border bg-card p-4">
            <h3 className="text-sm font-medium">أحدث التقارير</h3>
            <ul className="mt-2 flex flex-col divide-y divide-border">
              {recent.length === 0 && (
                <li className="py-6 text-center text-xs text-muted-foreground">
                  لا تقارير رسمية محفوظة بعد — تُبنى من الطبقة الحية عند اكتمال دفاتر الوكلاء.
                </li>
              )}
              {recent.map((r) => (
                <li key={r.title} className="flex items-center gap-2.5 py-2">
                  <AgentAvatar agent={r.agent} size={22} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs font-medium">{r.title}</p>
                    <p className="truncate text-[11px] text-muted-foreground">{r.summary}</p>
                  </div>
                  <span className="shrink-0 text-[11px] text-muted-foreground">{r.date}</span>
                </li>
              ))}
            </ul>
          </section>

          <section className="rounded-xl border border-border bg-card p-4">
            <h3 className="text-sm font-medium">قياس مساهمة الوكلاء</h3>
            <p className="mt-2 text-xs text-muted-foreground">
              غير مفعّل بعد — يُبنى على بيانات إنجاز حقيقية عند تشغيل قياس الأداء (لا نسب متخيلة).
            </p>
          </section>
        </div>
      </DialogContent>
    </Dialog>
  )
}
