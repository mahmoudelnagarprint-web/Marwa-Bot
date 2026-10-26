'use client'

import { useEffect, useState } from 'react'
import { BarChart3, Cpu, Laptop, Settings, Trophy } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

type LiveState = {
  ok?: boolean
  db_ok?: boolean
  db_error?: string | null
  hardware_daemon?: { fresh?: boolean; updated_at?: string | null }
  ts?: string
}

/** مؤشر الاتصال الحقيقي (تطهير 2026-10-25): يفحص /api/live فعلياً كل 30 ثانية —
 *  يفتح القاعدة الحية readOnly على السيرفر. لا عدادات متحركة ولا ادعاءات ثابتة. */
function PulseIndicator() {
  const [live, setLive] = useState<LiveState | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let alive = true
    async function check() {
      try {
        const res = await fetch('/api/live', { cache: 'no-store' })
        const j = (await res.json()) as LiveState
        if (!alive) return
        setLive(j)
        setFailed(false)
      } catch {
        if (alive) setFailed(true)
      }
    }
    void check()
    const id = setInterval(check, 30_000)
    return () => { alive = false; clearInterval(id) }
  }, [])

  const connected = !failed && live?.db_ok === true
  const hwFresh = live?.hardware_daemon?.fresh === true
  const time = live?.ts
    ? new Intl.DateTimeFormat('ar-EG', { timeZone: 'Africa/Cairo', hour: '2-digit', minute: '2-digit', second: '2-digit' }).format(new Date(live.ts))
    : null

  return (
    <div
      className={cn(
        'flex items-center gap-2 rounded-full border px-2.5 py-1',
        connected ? 'border-emerald-400/15 bg-emerald-400/[0.06]' : 'border-amber-400/20 bg-amber-400/[0.08]',
      )}
      title={connected ? 'فحص حي: القاعدة تُقرأ readOnly على السيرفر' : 'فحص /api/live فشل — السيرفر أو القاعدة غير متاحين'}
    >
      <span className={cn('relative flex size-2', connected && hwFresh ? '' : 'opacity-70')} aria-hidden="true">
        {connected && (
          <>
            <span className="animate-marwa-pulse absolute inset-0 rounded-full bg-emerald-400" />
            <span className="relative size-2 rounded-full bg-emerald-400/90" />
          </>
        )}
        {!connected && <span className="size-2 rounded-full bg-amber-400" />}
      </span>
      <span className={cn('text-xs', connected ? 'text-emerald-200/80' : 'text-amber-200/90')}>
        <span className="font-mono" dir="ltr">Marwa Pulse</span>
        {' • '}
        {failed || !live
          ? 'يفحص الاتصال…'
          : connected
            ? `الطبقة الحية متصلة (POS ✓${time ? ` ${time}` : ''}${hwFresh ? ' • عتاد حي' : ' • دايمون العتاد غير شغال'})`
            : `غير متصل${live?.db_error ? ` — ${live.db_error.slice(0, 60)}` : ' — السيرفر أو القاعدة بعيد'}`}
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
