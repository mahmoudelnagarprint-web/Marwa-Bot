'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import { MessageCircle, Phone, RefreshCw, Send, Sparkles, User } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import type { SalmaOrder } from '@/app/api/salma-summary/route'

/** رقم واتساب الورشة (أمر المالك 2026-10-21) — صيغة دولية لمصر */
const WORKSHOP_WA = '201000433420'

export function CustomerChat() {
  const [orders, setOrders] = useState<SalmaOrder[]>([])
  const [selected, setSelected] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [drafting, setDrafting] = useState(false)
  const [draft, setDraft] = useState('')
  const [flash, setFlash] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await fetch('/api/salma-summary', { cache: 'no-store' })
      const j = (await res.json()) as { orders?: SalmaOrder[] }
      setOrders(j.orders ?? [])
    } catch {
      setFlash('⚠️ فشل تحميل العملاء')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { void load() }, [load])

  const clients = useMemo(() => {
    const map = new Map<string, { name: string; phone: string | null; orders: SalmaOrder[]; balance: number }>()
    for (const o of orders) {
      const c = map.get(o.client) ?? { name: o.client, phone: o.phoneE164 ?? o.phone, orders: [], balance: 0 }
      c.orders.push(o)
      c.balance += o.balance
      map.set(o.client, c)
    }
    return [...map.values()].sort((a, b) => b.balance - a.balance)
  }, [orders])

  const current = clients.find((c) => c.name === selected) ?? null

  async function smartReply() {
    if (!current) return
    setDrafting(true)
    setFlash(null)
    try {
      const res = await fetch('/api/customer-reply', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ client: current.name }),
      })
      const j = (await res.json()) as { ok?: boolean; text?: string; reason?: string }
      if (j.ok && j.text) {
        setDraft(j.text)
        setFlash('✨ الرد اتصاغ من حالة الطلبات الحقيقية — راجعه وعدّل قبل الإرسال')
      } else {
        setFlash(`⚠️ ${j.reason ?? 'المحرك غير متاح حالياً'}`)
      }
    } catch {
      setFlash('⚠️ فشل الاتصال بمحرك الصياغة')
    } finally {
      setDrafting(false)
    }
  }

  function sendWhatsApp() {
    const text = draft.trim()
    if (!text) return
    window.open(`https://wa.me/${WORKSHOP_WA}?text=${encodeURIComponent(text)}`, '_blank')
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 p-4 text-sm text-muted-foreground">
        <RefreshCw className="size-4 animate-spin" /> سلمى بتجمع عملاء POS…
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-3 p-4">
      {flash && (
        <div className="rounded-xl border border-sky-400/25 bg-sky-400/[0.08] px-3 py-2 text-sm text-sky-200">{flash}</div>
      )}

      <div className="grid gap-3 md:grid-cols-2">
        {/* قائمة العملاء */}
        <div className="flex flex-col gap-1.5">
          <p className="flex items-center gap-1.5 text-sm font-medium text-foreground">
            <MessageCircle className="size-4 text-teal-300" /> العملاء ({clients.length})
          </p>
          <div className="flex max-h-72 flex-col gap-1 overflow-y-auto scrollbar-thin">
            {clients.length === 0 && (
              <p className="rounded-xl border border-dashed border-border py-6 text-center text-xs text-muted-foreground">لا عملاء في POS</p>
            )}
            {clients.map((c) => (
              <button
                key={c.name}
                type="button"
                onClick={() => { setSelected(c.name); setDraft('') }}
                className={cn(
                  'flex items-center justify-between gap-2 rounded-lg border px-3 py-2 text-start text-sm transition-colors',
                  selected === c.name ? 'border-teal-400/40 bg-teal-400/10' : 'border-border bg-card hover:bg-accent',
                )}
              >
                <span className="flex min-w-0 items-center gap-2">
                  <User className="size-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
                  <span className="min-w-0 truncate">{c.name}</span>
                  {c.phone && <Phone className="size-3 shrink-0 text-muted-foreground" aria-hidden="true" />}
                </span>
                <span className="flex shrink-0 items-center gap-2 text-[11px]">
                  <span className="text-muted-foreground">{c.orders.length} طلب</span>
                  {c.balance > 0 && <span className="rounded bg-rose-400/15 px-1.5 py-0.5 font-mono text-rose-300">{Math.round(c.balance)}ج</span>}
                </span>
              </button>
            ))}
          </div>
        </div>

        {/* الرد الذكي */}
        <div className="flex flex-col gap-2">
          <p className="text-sm font-medium text-foreground">الرد على العميل</p>
          {current ? (
            <>
              <div className="rounded-lg border border-border bg-card p-2.5 text-xs">
                <p className="font-medium">{current.name}</p>
                <ul className="mt-1 flex flex-col gap-0.5 text-muted-foreground">
                  {current.orders.slice(0, 3).map((o) => (
                    <li key={o.id} className="flex items-center justify-between gap-2">
                      <span>#{o.id} — {o.status}</span>
                      <span className="font-mono tabular-nums">{Math.round(o.total)}ج</span>
                    </li>
                  ))}
                </ul>
              </div>
              <textarea
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                rows={5}
                placeholder="اضغط ✨ صياغة رد ذكي — أو اكتب يدوياً…"
                aria-label="مسودة الرد"
                className="w-full resize-none rounded-lg border border-border bg-background p-2.5 text-sm outline-none placeholder:text-muted-foreground focus:border-teal-400/40"
              />
              <div className="flex flex-wrap items-center gap-2">
                <Button size="sm" variant="outline" disabled={drafting} onClick={() => void smartReply()} className="gap-1.5">
                  <Sparkles className={cn('size-3.5', drafting && 'animate-pulse')} />
                  {drafting ? 'بيصيغ من لوحة بيبو…' : 'صياغة رد ذكي'}
                </Button>
                <Button size="sm" disabled={!draft.trim()} onClick={sendWhatsApp} className="gap-1.5">
                  <Send className="size-3.5" /> إرسال عبر واتساب
                </Button>
                {current.phone && (
                  <a
                    href={`https://wa.me/${current.phone.replace(/\D/g, '')}?text=${encodeURIComponent(draft || '')}`}
                    target="_blank"
                    rel="noreferrer"
                    className="text-[11px] text-muted-foreground underline underline-offset-2"
                  >
                    أو واتساب العميل مباشرة
                  </a>
                )}
              </div>
            </>
          ) : (
            <p className="rounded-xl border border-dashed border-border py-8 text-center text-xs text-muted-foreground">
              اختر عميلاً من القائمة ☝️
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
