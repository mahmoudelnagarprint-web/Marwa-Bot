'use client'

import { useEffect, useState } from 'react'
import { BarChart3, Cpu, Laptop, Settings, Trophy } from 'lucide-react'
import { Button } from '@/components/ui/button'

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
        <span className="font-mono tabular-nums">{seconds}s</span> — متصلة بالطبقة الحية (POS + Workspaces)
      </span>
    </div>
  )
}

/** المزود النشط الحي — يقرأ حالة الأسطول الفعلية (Active/Standby) من /api/chat */
function ActiveProviderBadge({ onOpenSettings }: { onOpenSettings: () => void }) {
  const [provider, setProvider] = useState<{ name: string; model: string; standby?: string | null } | null>(null)
  const [checked, setChecked] = useState(false)

  useEffect(() => {
    let alive = true
    async function load() {
      try {
        const res = await fetch('/api/chat?agent=marwa', { cache: 'no-store' })
        const j = (await res.json()) as {
          ok?: boolean
          active?: { name?: string; model?: string } | null
          standby?: { model?: string } | null
        }
        if (!alive) return
        const active = j.active
        setProvider(
          active?.model
            ? {
                name: active.name || 'مزود',
                model: active.model,
                standby: j.standby?.model ?? null,
              }
            : null,
        )
      } catch { /* السيرفر غير متاح */ } finally {
        if (alive) setChecked(true)
      }
    }
    void load()
    const id = setInterval(load, 120_000)
    return () => { alive = false; clearInterval(id) }
  }, [])

  return (
    <button
      type="button"
      onClick={onOpenSettings}
      title={
        provider
          ? `النموذج النشط: ${provider.model}${provider.standby ? ` — الاحتياطي: ${provider.standby}` : ''}`
          : 'فتح إعدادات أسطول الذكاء الاصطناعي'
      }
      aria-label="المزود النشط للذكاء الاصطناعي"
      className="inline-flex items-center gap-1.5 rounded-md border border-border px-2 py-1 text-xs text-muted-foreground transition-colors hover:border-foreground/20 hover:text-foreground"
    >
      {provider ? (
        <>
          <span className="relative flex size-2 shrink-0" aria-hidden="true">
            <span className="animate-marwa-pulse absolute inset-0 rounded-full bg-emerald-400" />
            <span className="relative size-2 rounded-full bg-emerald-400/90" />
          </span>
          <span className="max-w-32 truncate">{provider.name}</span>
          <span className="hidden max-w-48 truncate font-mono text-[11px] md:inline" dir="ltr">{provider.model}</span>
        </>
      ) : (
        <>
          <Cpu className="size-3.5" aria-hidden="true" />
          {checked ? 'لا مزود — أضف من ⚙️' : 'يفحص الأسطول…'}
        </>
      )}
    </button>
  )
}

export function TopHeader({
  onReports,
  onAchievements,
  onOpenSettings,
}: {
  onReports: () => void
  onAchievements: () => void
  onOpenSettings: () => void
}) {
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
        <ActiveProviderBadge onOpenSettings={onOpenSettings} />
        <Button variant="ghost" size="icon-sm" onClick={onOpenSettings} aria-label="الإعدادات العامة — أسطول الذكاء" title="الإعدادات العامة (أسطول الذكاء)" className="text-muted-foreground hover:text-foreground">
          <Settings className="size-4" aria-hidden="true" />
        </Button>
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
