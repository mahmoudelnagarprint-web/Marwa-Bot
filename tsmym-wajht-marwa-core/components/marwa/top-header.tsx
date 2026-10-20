'use client'

import { useEffect, useState } from 'react'
import { BarChart3, ChevronDown, Cpu, Laptop, RefreshCw, Trophy } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { models } from '@/lib/marwa-data'

function PulseIndicator() {
  const [seconds, setSeconds] = useState(3)

  useEffect(() => {
    const id = setInterval(() => setSeconds((s) => (s >= 3 ? 1 : s + 1)), 1000)
    return () => clearInterval(id)
  }, [])

  return (
    <div className="flex items-center gap-2 rounded-full border border-emerald-400/15 bg-emerald-400/[0.06] px-2.5 py-1">
      <span className="relative flex size-2" aria-hidden="true">
        <span className="animate-marwa-pulse absolute inset-0 rounded-full bg-emerald-400" />
        <span className="relative size-2 rounded-full bg-emerald-400/90" />
      </span>
      <span className="text-xs text-emerald-200/80">
        <span className="font-mono" dir="ltr">
          Marwa Pulse
        </span>
        {' • '}
        <span className="font-mono tabular-nums">{seconds}s</span> — واجهة تجريبية (التفعيل الحي بالمرحلة 3 بأمر المالك)
      </span>
    </div>
  )
}

export function TopHeader({
  model,
  onModelChange,
  onHandover,
  onReports,
  onAchievements,
}: {
  model: string
  onModelChange: (id: string) => void
  onHandover: () => void
  onReports: () => void
  onAchievements: () => void
}) {
  const current = models.find((m) => m.id === model) ?? models[0]

  return (
    <header className="flex h-14 shrink-0 items-center justify-between gap-4 border-b border-border bg-sidebar px-4">
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2.5">
          <span className="flex size-8 items-center justify-center rounded-lg bg-foreground text-background">
            <span className="font-mono text-sm font-semibold" dir="ltr">
              M
            </span>
          </span>
          <div className="leading-tight">
            <p className="font-mono text-sm font-semibold tracking-wide" dir="ltr">
              MARWA CORE
            </p>
            <p className="text-[11px] text-muted-foreground">مروة المايسترو</p>
          </div>
        </div>
        <span className="h-6 w-px bg-border" aria-hidden="true" />
        <PulseIndicator />
        <span className="hidden items-center gap-1.5 rounded-md border border-border px-2 py-1 text-xs text-muted-foreground md:inline-flex">
          <Laptop className="size-3.5" aria-hidden="true" />
          <span className="font-mono" dir="ltr">
            LAPTOP
          </span>
        </span>
      </div>

      <div className="flex items-center gap-2">
        <Button variant="outline" size="sm" onClick={onHandover} className="gap-2">
          <RefreshCw className="size-3.5" aria-hidden="true" />
          تسليم السياق
          <span className="font-mono text-[11px] text-muted-foreground" dir="ltr">
            Handover
          </span>
        </Button>
        <DropdownMenu>
          <DropdownMenuTrigger
            render={
              <Button variant="ghost" size="sm" className="gap-2 text-muted-foreground hover:text-foreground" />
            }
          >
            <Cpu className="size-3.5" aria-hidden="true" />
            <span dir="ltr">{current.label}</span>
            <ChevronDown className="size-3.5" aria-hidden="true" />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="center" className="w-56">
            <DropdownMenuGroup>
              <DropdownMenuLabel>اختيار النموذج</DropdownMenuLabel>
              <DropdownMenuRadioGroup value={model} onValueChange={(v) => onModelChange(String(v))}>
                {models.map((m) => (
                  <DropdownMenuRadioItem key={m.id} value={m.id}>
                    <span className="flex w-full items-center justify-between gap-3">
                      <span dir="ltr">{m.label}</span>
                      <span className="text-[11px] text-muted-foreground">{m.provider}</span>
                    </span>
                  </DropdownMenuRadioItem>
                ))}
              </DropdownMenuRadioGroup>
            </DropdownMenuGroup>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      <div className="flex items-center gap-2">
        <Button variant="secondary" size="sm" onClick={onReports} className="gap-2">
          <BarChart3 className="size-3.5 text-sky-300" aria-hidden="true" />
          التقارير
        </Button>
        <Button variant="secondary" size="sm" onClick={onAchievements} className="gap-2">
          <Trophy className="size-3.5 text-amber-300" aria-hidden="true" />
          الإنجازات
        </Button>
      </div>
    </header>
  )
}
