'use client'

// components/marwa/integrations-panel.tsx — لوحة ربط الحسابات الخارجية (OAuth)
// MARWA CORE task-6 (أمر المالك 2026-10-24):
//   أزرار "Connect to Google" و "Connect to Canva" + حالة الاتصال + فصل.
// 🔐 الأمان: الأزرار توجه المالك لمسار /api/integrations/auth/<provider> — الرموز
//   تُتبادل وتُحفظ في خزنة السيرفر المشفرة (لا تمر بالواجهة إطلاقاً) — هنا حالتنا فقط.

import { useCallback, useEffect, useState } from 'react'
import { CalendarCheck, FileSpreadsheet, Image, Mail, Paperclip, RefreshCw, Search } from 'lucide-react'
import { cn } from '@/lib/utils'

type Status = {
  provider: string
  connected: boolean
  expires_at: string | null
  expired: boolean
  scope: string | null
  updated_at: string | null
}

type EnvReady = { google: boolean; canva: boolean; secret: boolean }

const PROVIDER_META = {
  google: {
    name: 'Google',
    color: 'text-sky-300',
    border: 'border-sky-400/20',
    bg: 'bg-sky-400/[0.06]',
    tools: [
      { icon: FileSpreadsheet, label: 'Sheets — جداول وتقفيلات' },
      { icon: CalendarCheck, label: 'Calendar — مواعيد التسليم' },
      { icon: Mail, label: 'Gmail — قراءة الإيميلات' },
      { icon: Paperclip, label: 'Drive/Docs — مستندات' },
    ],
  },
  canva: {
    name: 'Canva',
    color: 'text-fuchsia-300',
    border: 'border-fuchsia-400/20',
    bg: 'bg-fuchsia-400/[0.06]',
    tools: [
      { icon: Image, label: 'تصميمات من القوالب' },
      { icon: RefreshCw, label: 'تصدير PNG/PDF' },
    ],
  },
} as const

export function IntegrationsPanel() {
  const [statuses, setStatuses] = useState<Status[]>([])
  const [envReady, setEnvReady] = useState<EnvReady | null>(null)
  const [loading, setLoading] = useState(true)
  const [msg, setMsg] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await fetch('/api/integrations/status', { cache: 'no-store' })
      const data = await res.json()
      setStatuses(data?.integrations ?? [])
      setEnvReady(data?.envReady ?? null)
    } catch {
      setMsg('تعذر قراءة حالة التكاملات — تأكد أن السيرفر يعمل')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
    // التقاط نتيجة العودة من الكولباك (?integrations=connected&msg=...)
    const q = new URLSearchParams(window.location.search)
    if (q.get('integrations')) {
      setMsg(q.get('msg') ?? null)
      window.history.replaceState({}, '', window.location.pathname)
    }
  }, [load])

  const connect = (provider: string) => {
    window.location.href = `/api/integrations/auth/${provider}`
  }

  const disconnect = async (provider: string) => {
    await fetch('/api/integrations/disconnect', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ provider }),
    })
    void load()
  }

  const statusOf = (p: string): Status | undefined => statuses.find((s) => s.provider === p)

  return (
    <div className="space-y-3" aria-label="التكاملات الخارجية">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium">🌐 التكاملات الخارجية — ربط الحسابات للوكلاء</p>
        <button
          type="button"
          onClick={() => void load()}
          className="rounded border border-border px-2 py-0.5 text-[10px] text-muted-foreground hover:bg-sidebar-accent/60"
        >
          تحديث
        </button>
      </div>

      {msg && (
        <p className={cn('rounded-lg border px-2 py-1 text-xs', msg.includes('فشل') || msg.includes('فشل') ? 'border-rose-400/20 bg-rose-400/10 text-rose-300' : 'border-emerald-400/20 bg-emerald-400/10 text-emerald-300')}>
          {msg}
        </p>
      )}

      {envReady && !envReady.secret && (
        <p className="rounded-lg border border-amber-400/20 bg-amber-400/10 px-2 py-1.5 text-xs text-amber-300">
          🔑 أضف <span className="font-mono">INTEGRATIONS_SECRET</span> إلى <span className="font-mono">.env.local</span> أولاً (راجع INTEGRATIONS_SETUP.md القسم 4) — بدونها لا تُحفظ الرموز.
        </p>
      )}

      {loading ? (
        <p className="py-3 text-xs text-muted-foreground">جارٍ قراءة حالة التكاملات…</p>
      ) : (
        (Object.keys(PROVIDER_META) as (keyof typeof PROVIDER_META)[]).map((p) => {
          const meta = PROVIDER_META[p]
          const st = statusOf(p)
          const ready = envReady ? (p === 'google' ? envReady.google : envReady.canva) : false
          return (
            <div key={p} className={cn('rounded-xl border p-3', meta.border, meta.bg)}>
              <div className="flex items-center justify-between gap-2">
                <div className="min-w-0">
                  <p className={cn('text-sm font-semibold', meta.color)}>
                    {meta.name}{' '}
                    {st?.connected ? (
                      <span className="rounded border border-emerald-400/20 bg-emerald-400/10 px-1.5 py-0.5 text-[10px] text-emerald-300">متصل ✓</span>
                    ) : (
                      <span className="rounded border border-zinc-400/20 bg-zinc-400/10 px-1.5 py-0.5 text-[10px] text-zinc-300">غير متصل</span>
                    )}
                  </p>
                  <p className="mt-1 text-[11px] text-muted-foreground">
                    {st?.connected
                      ? st.expired
                        ? 'الرمز منتهٍ — سيتجدد تلقائياً عند أول استخدام'
                        : `صالح حتى ${st.expires_at ? new Date(st.expires_at).toLocaleString('ar-EG') : '—'}`
                      : 'اربط الحساب ليتمكن الوكلاء من العمل نيابة عنك'}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-1.5">
                  <button
                    type="button"
                    onClick={() => connect(p)}
                    disabled={!ready}
                    className="rounded-lg bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground transition-all hover:bg-primary/90 disabled:opacity-40"
                    title={ready ? 'بدء ربط الحساب' : 'أضف مفاتيح المزود في .env.local أولاً'}
                  >
                    Connect to {meta.name}
                  </button>
                  {st?.connected && (
                    <button
                      type="button"
                      onClick={() => void disconnect(p)}
                      className="rounded-lg border border-rose-400/20 px-2 py-1.5 text-xs text-rose-300 transition-colors hover:bg-rose-400/10"
                    >
                      فصل
                    </button>
                  )}
                </div>
              </div>

              <div className="mt-2 flex flex-wrap gap-1.5">
                {meta.tools.map((t) => (
                  <span key={t.label} className="inline-flex items-center gap-1 rounded border border-border px-1.5 py-0.5 text-[10px] text-muted-foreground">
                    <t.icon className="size-3" aria-hidden="true" />
                    {t.label}
                  </span>
                ))}
              </div>

              {!ready && (
                <p className="mt-2 text-[10px] text-amber-300/90">
                  مفاتيح {meta.name} غير مضبوطة في <span className="font-mono">.env.local</span> — راجع INTEGRATIONS_SETUP.md
                </p>
              )}
            </div>
          )
        })
      )}

      <p className="rounded-lg border border-border bg-card/40 px-2 py-1.5 text-[10px] leading-relaxed text-muted-foreground">
        🔐 الرموز تُحفظ مشفرة (AES-256-GCM) في خزنة السيرفر فقط — لا تمر بالواجهة ولا تُعرض أبداً. أدوات Google Search تستخدم مفتاح API مباشر (قسم 3 من الدليل).
      </p>
    </div>
  )
}
