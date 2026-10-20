'use client'

import { useState } from 'react'
import { ArrowLeft, Check, Loader2, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { cn } from '@/lib/utils'
import { models } from '@/lib/marwa-data'

export function HandoverDialog({
  open,
  onOpenChange,
  currentModel,
  messageCount,
  activeCount,
  onComplete,
}: {
  open: boolean
  onOpenChange: (v: boolean) => void
  currentModel: string
  messageCount: number
  activeCount: number
  onComplete: (targetModel: string) => void
}) {
  const others = models.filter((m) => m.id !== currentModel)
  const [target, setTarget] = useState(others[0].id)
  const [step, setStep] = useState(-1)
  const [snapshot, setSnapshot] = useState<{ from: string; to: string } | null>(null)

  const items = [
    `ملخص المحادثة (${messageCount} رسالة)`,
    `حالة الوكلاء المفعّلين (${activeCount})`,
    'بنود النوت بوك المفتوحة',
    'القرارات المعتمدة والإجراءات',
    'تفضيلات المستخدم وأسلوب الرد',
  ]
  const finished = step >= items.length
  const running = step >= 0 && !finished
  const effectiveTarget = others.some((m) => m.id === target) ? target : others[0].id
  const current = models.find((m) => m.id === currentModel)!
  const next = models.find((m) => m.id === effectiveTarget)!

  function start() {
    setSnapshot({ from: current.label, to: next.label })
    setStep(0)
    items.forEach((_, i) => {
      setTimeout(() => setStep(i + 1), 450 * (i + 1))
    })
    setTimeout(() => onComplete(effectiveTarget), 450 * items.length + 100)
  }

  function handleOpenChange(v: boolean) {
    if (running) return
    onOpenChange(v)
    if (!v) {
      setStep(-1)
      setSnapshot(null)
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <RefreshCw className={cn('size-4', running && 'animate-spin')} aria-hidden="true" />
            تسليم السياق
          </DialogTitle>
          <DialogDescription>انقل ذاكرة مروة الكاملة إلى نموذج آخر دون فقدان أي تفاصيل.</DialogDescription>
        </DialogHeader>

        <div className="flex items-center gap-2">
          <div className="flex-1 rounded-lg border border-border bg-card p-2.5">
            <p className="text-[11px] text-muted-foreground">من</p>
            <p className="text-sm font-medium" dir="ltr">
              {snapshot?.from ?? current.label}
            </p>
          </div>
          <ArrowLeft className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
          <div className="flex-1">
            {snapshot ? (
              <div className="rounded-lg border border-border bg-card p-2.5">
                <p className="text-[11px] text-muted-foreground">إلى</p>
                <p className="text-sm font-medium" dir="ltr">
                  {snapshot.to}
                </p>
              </div>
            ) : (
              <>
                <label htmlFor="handover-target" className="text-[11px] text-muted-foreground">
                  إلى
                </label>
                <select
                  id="handover-target"
                  value={effectiveTarget}
                  onChange={(e) => setTarget(e.target.value)}
                  className="mt-0.5 w-full rounded-lg border border-border bg-card p-2 text-sm outline-none focus-visible:border-ring"
                  dir="ltr"
                >
                  {others.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.label}
                    </option>
                  ))}
                </select>
              </>
            )}
          </div>
        </div>

        <ul className="flex flex-col gap-1.5" aria-live="polite">
          {items.map((label, i) => {
            const done = step > i
            const active = step === i
            return (
              <li
                key={label}
                className={cn(
                  'flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-sm transition-colors',
                  done ? 'text-foreground' : 'text-muted-foreground',
                  active && 'bg-accent',
                )}
              >
                <span
                  className={cn(
                    'flex size-4 items-center justify-center rounded-full border',
                    done ? 'border-emerald-400/40 bg-emerald-400/15 text-emerald-300' : 'border-border',
                  )}
                >
                  {done && <Check className="size-2.5" />}
                  {active && <Loader2 className="size-2.5 animate-spin" />}
                </span>
                {label}
              </li>
            )
          })}
        </ul>

        <DialogFooter>
          {finished ? (
            <Button onClick={() => handleOpenChange(false)} className="w-full">
              تم التسليم إلى {snapshot?.to}
            </Button>
          ) : (
            <Button onClick={start} disabled={running} className="w-full gap-2">
              {running && <Loader2 className="size-3.5 animate-spin" />}
              {running ? 'جارٍ التسليم...' : 'بدء التسليم'}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
