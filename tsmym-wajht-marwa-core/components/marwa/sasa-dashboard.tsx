'use client'

import { useCallback, useEffect, useState } from 'react'
import {
  FileDigit, Fan, FolderOpen, Gauge, Rocket, RefreshCw, Send, Wrench, Zap,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

type SpoolTask = { id: number; client: string; total: number; items: { name: string; qty: number }[]; machine: string }
type DesignFile = { name: string; rel: string; size: number; mtime: string; ext: string }
type MachineTelemetry = { id: string; name: string; state: 'Idle' | 'Busy'; metric_label: string; metric_value: number | string; metric_unit: string; simulated: true | false; hardware_source?: string }

type Resp = {
  error?: string
  spool?: SpoolTask[]
  telemetry?: MachineTelemetry[]
  designs_dir?: string
  designs?: DesignFile[]
}

const machineTone: Record<string, string> = {
  'ليزر CO2': 'text-rose-300 border-rose-400/25 bg-rose-400/10',
  'Epson L1800': 'text-sky-300 border-sky-400/25 bg-sky-400/10',
  'كاتر بلوتر': 'text-violet-300 border-violet-400/25 bg-violet-400/10',
}

const MAINTENANCE: Record<string, string[]> = {
  'Epson L1800': ['Head Cleaning', 'Nozzle Check'],
  'ليزر CO2': ['Cooling Check', 'Mirror/Lens Clean'],
  'كاتر بلوتر': ['Blade Check', 'Calibrate'],
}

export function SasaDashboard() {
  const [spool, setSpool] = useState<SpoolTask[]>([])
  const [telemetry, setTelemetry] = useState<MachineTelemetry[]>([])
  const [designs, setDesigns] = useState<DesignFile[]>([])
  const [designsDir, setDesignsDir] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [flash, setFlash] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch('/api/devices', { cache: 'no-store' })
      const j = (await res.json()) as Resp
      if (j.error) throw new Error(j.error)
      setSpool(j.spool ?? [])
      setTelemetry(j.telemetry ?? [])
      setDesigns(j.designs ?? [])
      setDesignsDir(j.designs_dir ?? '')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'فشل التحميل')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void load() }, [load])

  async function post(payload: Record<string, unknown>) {
    setBusy(true)
    setFlash(null)
    try {
      const res = await fetch('/api/devices', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const j = (await res.json()) as { ok?: boolean; notify?: string; message?: string }
      setFlash(j.ok ? (j.notify ?? 'تم') : `⚠️ ${j.message ?? 'فشل'}`)
    } catch {
      setFlash('⚠️ فشل الاتصال')
    } finally {
      setBusy(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 p-4 text-sm text-muted-foreground">
        <RefreshCw className="size-4 animate-spin" /> صاصا بيرصد الماكينات…
      </div>
    )
  }
  if (error) return <div className="p-4 text-sm text-rose-300">⚠️ {error}</div>

  return (
    <div className="flex flex-col gap-3 p-3">
      {/* رادار الماكينات */}
      <div className="grid grid-cols-1 gap-2 md:grid-cols-3">
        {telemetry.map((m) => (
          <div key={m.id} className={cn('rounded-xl border p-3', machineTone[m.name] ?? 'border-border bg-card')}>
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium" dir="rtl">{m.name}</p>
              <span
                className={cn(
                  'rounded px-1.5 py-0.5 font-mono text-[10px]',
                  m.state === 'Busy' ? 'bg-amber-400/15 text-amber-300' : 'bg-emerald-400/15 text-emerald-300',
                )}
              >
                {m.state}
              </span>
            </div>
            <div className="mt-2 flex items-end justify-between">
              <div>
                <p className="text-[10px] text-muted-foreground">{m.metric_label}{m.simulated ? ' (محاكاة مؤقتة)' : ` (عتاد حقيقي • ${m.hardware_source?.split(' @ ')[0] ?? 'دايمون'})`}</p>
                <p className="font-mono text-lg font-semibold">
                  {m.metric_value}
                  <span className="text-[10px] font-normal text-muted-foreground"> {m.metric_unit}</span>
                </p>
              </div>
              <Gauge className="size-5 opacity-40" aria-hidden="true" />
            </div>
            <div className="mt-1.5 flex flex-wrap gap-1">
              {(MAINTENANCE[m.name] ?? []).map((mtn) => (
                <Button
                  key={mtn}
                  variant="outline"
                  size="sm"
                  disabled={busy}
                  className="h-6 px-1.5 text-[10px]"
                  onClick={() => void post({ action: 'maintenance', machine: m.name, maintenance: mtn })}
                >
                  <Wrench className="size-3" /> {mtn}
                </Button>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* طابور التشغيل الذكي (من عمود printing بلوحة بيبو) */}
      <div className="rounded-xl border border-border p-3">
        <p className="mb-2 flex items-center gap-2 text-sm font-medium">
          <Fan className="size-4 text-amber-300" /> طابور التشغيل
          <span className="text-[10px] font-normal text-muted-foreground">(يسحب من عمود «قيد الطباعة/الليزر» بلوحة بيبو)</span>
        </p>
        {spool.length === 0 ? (
          <p className="py-3 text-center text-xs text-muted-foreground">الطابور فاضي — انقل كارت من لوحة بيبو لعمود «قيد الطباعة/الليزر».</p>
        ) : (
          <ul className="flex flex-col gap-1.5">
            {spool.map((t) => (
              <li key={t.id} className="flex items-center justify-between gap-2 rounded-lg border border-border bg-card px-3 py-2">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">
                    #{t.id} — {t.client}
                  </p>
                  <p className="truncate text-[10px] text-muted-foreground">
                    {t.items.map((i) => `${i.name} ×${i.qty}`).join(' • ')}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-1.5">
                  <span className={cn('rounded px-1.5 py-0.5 text-[10px]', machineTone[t.machine])}>{t.machine}</span>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={busy}
                    className="h-7 px-2 text-[11px] text-emerald-300"
                    onClick={() => void post({ action: 'launch_machine', order_id: t.id, machine: t.machine })}
                  >
                    <Rocket className="size-3" /> إرسال للماكينة
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      {flash && <p className="text-xs text-emerald-300" role="status">{flash}</p>}

      {/* متصفح التصميمات المحلي */}
      <div className="rounded-xl border border-border p-3">
        <p className="mb-2 flex items-center gap-2 text-sm font-medium">
          <FolderOpen className="size-4 text-sky-300" /> متصفح التصميمات
          <span className="truncate text-[10px] font-normal text-muted-foreground" dir="ltr">{designsDir}</span>
        </p>
        {designs.length === 0 ? (
          <p className="py-3 text-center text-xs text-muted-foreground">
            لا ملفات (dxf/cdr/psd/ai/pdf/svg/plt) في مجلد التصميمات — عدّل DESIGNS_DIR في .env.local.
          </p>
        ) : (
          <ul className="grid max-h-64 grid-cols-1 gap-1 overflow-y-auto md:grid-cols-2">
            {designs.map((d) => (
              <li key={d.rel} className="flex items-center justify-between gap-2 rounded-lg border border-border bg-card px-2.5 py-1.5">
                <div className="min-w-0">
                  <p className="truncate text-xs font-medium" dir="ltr">{d.name}</p>
                  <p className="text-[9px] text-muted-foreground" dir="ltr">{d.rel}</p>
                </div>
                <div className="flex shrink-0 items-center gap-1.5">
                  <span className="rounded bg-sky-400/10 px-1 py-0.5 font-mono text-[9px] text-sky-300">{d.ext}</span>
                  <span className="font-mono text-[9px] text-muted-foreground">{(d.size / 1024).toFixed(0)} KB</span>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
