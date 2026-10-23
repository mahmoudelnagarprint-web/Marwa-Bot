'use client'
// components/marwa/chat-live.tsx — واجهة الشات الحية: مؤقت الانتظار + شريط Active/Standby + مؤشر التبديل الآلي + اختيار النموذج يدوياً
import { useCallback, useEffect, useRef, useState } from 'react'
import { Sparkles } from 'lucide-react'
import { cn } from '@/lib/utils'
import {
  fetchFleet,
  streamChat,
  type ChatDone,
  type FleetPlan,
  type GatewayEvent,
  type ProviderBrief,
  type StreamChatBody,
} from '@/lib/chat-client'

type LiveState = {
  loading: boolean
  startedAt: number | null // لحظة إرسال الرسالة (يقرؤها ReplyTimer فقط)
  finalSeconds: number | null // زمن آخر رد مكتمل
  active: ProviderBrief | null
  standby: ProviderBrief | null
  failures: number // عدد المحاولات الفاشلة في الطلب الحالي
  max: number
  manual: boolean
}

const INITIAL: LiveState = {
  loading: false,
  startedAt: null,
  finalSeconds: null,
  active: null,
  standby: null,
  failures: 0,
  max: 5,
  manual: false,
}

export type LiveChat = ReturnType<typeof useLiveChat>

export function useLiveChat(agent: string) {
  const [state, setState] = useState<LiveState>(INITIAL)
  const [fleet, setFleet] = useState<FleetPlan | null>(null)
  const [providerId, setProviderId] = useState<string>('') // '' = آلي
  const [strictProvider, setStrictProvider] = useState(false)
  const abortRef = useRef<AbortController | null>(null)
  const loadingRef = useRef(false)

  // جلب الأسطول + (Active/Standby) عند فتح الشات وعند تغيير الوكيل أو الاختيار اليدوي
  useEffect(() => {
    const ctl = new AbortController()
    void fetchFleet(agent, providerId || undefined, ctl.signal).then((f) => {
      if (!f?.ok || ctl.signal.aborted) return
      setFleet(f)
      if (!loadingRef.current) {
        setState((s) => ({ ...s, active: f.active, standby: f.standby, manual: f.manual }))
      }
    })
    return () => ctl.abort()
  }, [agent, providerId])

  useEffect(() => () => abortRef.current?.abort(), [])

  const onEvent = useCallback((ev: GatewayEvent) => {
    setState((s) => {
      switch (ev.type) {
        case 'plan':
          return { ...s, active: ev.active, standby: ev.standby, manual: ev.manual }
        case 'attempt':
          return { ...s, active: ev.active, standby: ev.standby, max: ev.max }
        case 'failover':
          return { ...s, failures: ev.n, max: ev.max, active: ev.to ?? s.active, standby: ev.standby }
        default:
          return s
      }
    })
  }, [])

  const send = useCallback(
    async (messages: StreamChatBody['messages'], maxTokens?: number): Promise<ChatDone> => {
      abortRef.current?.abort()
      const ctl = new AbortController()
      abortRef.current = ctl
      const startedAt = Date.now()
      loadingRef.current = true
      setState((s) => ({ ...s, loading: true, startedAt, finalSeconds: null, failures: 0 }))
      try {
        const done = await streamChat(
          { agent, messages, maxTokens, providerId: providerId || undefined, strictProvider },
          onEvent,
          ctl.signal,
        )
        setState((s) => ({
          ...s,
          active: done.provider ?? s.active,
          standby: done.standby !== undefined ? done.standby : s.standby,
        }))
        return done
      } catch (e) {
        if ((e as { name?: string })?.name === 'AbortError') return { ok: false, reason: 'أُلغي الطلب' }
        return { ok: false, reason: 'تعذر الاتصال بالسيرفر' }
      } finally {
        loadingRef.current = false
        setState((s) => ({ ...s, loading: false, finalSeconds: (Date.now() - startedAt) / 1000 }))
      }
    },
    [agent, providerId, strictProvider, onEvent],
  )

  const cancel = useCallback(() => abortRef.current?.abort(), [])

  return { state, fleet, providerId, setProviderId, strictProvider, setStrictProvider, send, cancel }
}

/** مؤقت مستقل: يعيد رسم نفسه فقط (لا يُرندر باقي الشات كل 100ms) */
export function ReplyTimer({ startedAt, running, finalSeconds }: { startedAt: number | null; running: boolean; finalSeconds: number | null }) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    if (!running) return
    setNow(Date.now())
    const id = window.setInterval(() => setNow(Date.now()), 100)
    return () => window.clearInterval(id)
  }, [running, startedAt])

  let secs: number | null = null
  if (running && startedAt) secs = Math.max(0, (now - startedAt) / 1000)
  else if (finalSeconds !== null) secs = finalSeconds
  if (secs === null) return null

  const slow = running && secs >= 10
  return (
    <span
      className={`tabular-nums rounded-full px-2 py-0.5 text-xs font-medium ${
        running ? (slow ? 'bg-amber-100 text-amber-800' : 'bg-blue-100 text-blue-800') : 'bg-emerald-100 text-emerald-800'
      }`}
      title={running ? 'عمر انتظار الرد' : 'زمن آخر رد'}
    >
      ⏱ {secs.toFixed(1)}ث
    </span>
  )
}

function Badge({ label, p, tone }: { label: string; p: ProviderBrief | null; tone: 'active' | 'standby' }) {
  const active = tone === 'active'
  return (
    <span
      className={cn(
        'inline-flex min-w-0 items-center gap-1.5 rounded-full border px-2 py-0.5 text-[11px]',
        active
          ? 'border-emerald-400/30 bg-emerald-400/10 text-emerald-200'
          : 'border-amber-400/25 bg-amber-400/10 text-amber-200',
      )}
      title={p ? `${p.name} — ${p.model}` : undefined}
    >
      <span
        className={cn(
          'size-1.5 shrink-0 rounded-full',
          active ? 'bg-emerald-400' : 'bg-amber-400',
          active && 'animate-pulse',
        )}
        aria-hidden="true"
      />
      <span className="shrink-0 font-semibold opacity-80">{label}</span>
      <span className="max-w-40 truncate">{p ? p.name : '—'}</span>
    </span>
  )
}

/** شريط الحالة: Active / Standby + المؤقت + مؤشر التبديل الآلي — زجاجي داكن متناسق مع الواجهة */
export function ChatLiveBar({ live }: { live: LiveChat }) {
  const { state } = live
  const showSwitch = state.loading && state.failures > 0
  return (
    <div
      dir="rtl"
      className="flex flex-wrap items-center gap-x-2 gap-y-1.5 rounded-xl border border-border/50 bg-card/30 px-2.5 py-1.5 backdrop-blur-md"
    >
      <Badge label="النشط" p={state.active} tone="active" />
      <Badge label="الاحتياطي" p={state.standby} tone="standby" />
      {state.manual && (
        <span className="rounded-full border border-violet-400/30 bg-violet-400/10 px-2 py-0.5 text-[10px] font-medium text-violet-200">
          اختيار يدوي
        </span>
      )}
      <span className="ms-auto flex items-center gap-1.5">
        <ReplyTimer startedAt={state.startedAt} running={state.loading} finalSeconds={state.finalSeconds} />
      </span>
      {showSwitch && (
        <span role="status" aria-live="polite" className="basis-full text-[11px] text-amber-300">
          جاري التبديل الآلي {state.failures}/{state.max}…
        </span>
      )}
    </div>
  )
}

/** اختيار النموذج: «آلي» أو مزود محدد — يمرّر providerId فيلغي الاختبار الآلي */
export function ModelPicker({ live }: { live: LiveChat }) {
  const providers = (live.fleet?.providers ?? []).filter((p) => p.enabled)
  const selected = providers.find((p) => p.id === live.providerId)
  const autoLabel = live.state.manual ? 'يدوي' : 'آلي'

  return (
    <div dir="rtl" className="flex min-w-0 flex-wrap items-center gap-2">
      <label
        className={cn(
          'inline-flex min-w-0 items-center gap-2 rounded-xl border px-2.5 py-1.5 transition-colors',
          live.providerId
            ? 'border-violet-400/35 bg-violet-400/10'
            : 'border-primary/30 bg-primary/10',
        )}
      >
        <Sparkles
          className={cn('size-3.5 shrink-0', live.providerId ? 'text-violet-300' : 'text-primary')}
          aria-hidden="true"
        />
        <span className="shrink-0 text-[11px] font-semibold text-muted-foreground">النموذج</span>
        <select
          value={live.providerId}
          onChange={(e) => live.setProviderId(e.target.value)}
          disabled={live.state.loading}
          aria-label="اختيار نموذج الذكاء الاصطناعي"
          className="max-w-56 min-w-0 cursor-pointer truncate rounded-lg border border-border/60 bg-background px-2 py-1 text-xs text-foreground outline-none transition-colors focus:border-primary/50 disabled:opacity-50"
        >
          <option value="">آلي — الأسرع والأكثر استقراراً ({autoLabel})</option>
          {providers.map((p) => (
            <option key={p.id} value={p.id}>
              {`${p.name}${p.ping ? (p.ping.ok ? ` — ${p.ping.ms}ms` : ' — لا يستجيب') : ''}`}
            </option>
          ))}
        </select>
      </label>

      {selected && (
        <span className="flex min-w-0 items-center gap-1.5 rounded-full border border-border/50 bg-card/40 px-2 py-0.5 font-mono text-[10px] text-muted-foreground" dir="ltr">
          <span
            className={cn(
              'size-1.5 shrink-0 rounded-full',
              selected.status === 'up' ? 'bg-emerald-400' : selected.status === 'down' ? 'bg-rose-400' : 'bg-muted-foreground/50',
            )}
            aria-hidden="true"
          />
          <span className="max-w-40 truncate">{selected.model}</span>
        </span>
      )}

      {live.providerId && (
        <button
          type="button"
          onClick={() => live.setStrictProvider(!live.strictProvider)}
          disabled={live.state.loading}
          aria-pressed={live.strictProvider}
          className={cn(
            'shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-medium transition-colors disabled:opacity-50',
            live.strictProvider
              ? 'border-rose-400/35 bg-rose-400/10 text-rose-200'
              : 'border-border/60 text-muted-foreground hover:bg-accent hover:text-foreground',
          )}
          title="بدون احتياطي: لو النموذج المختار فشل يتوقف الطلب بدل التحويل التلقائي"
        >
          بلا احتياطي
        </button>
      )}
    </div>
  )
}

/*
──────────────── الدمج في MarwaApp ────────────────
const live = useLiveChat(currentAgentKey)

// رأس الشات:
<ModelPicker live={live} />
<ChatLiveBar live={live} />

// عند الإرسال (بدل fetch('/api/chat') القديم):
const res = await live.send(messages.map(m => ({ role: m.role, content: m.content })))
if (res.ok) addAssistantMessage(res.text ?? '')
else addErrorMessage(res.reason ?? 'تعذر الحصول على رد')

// زر الإيقاف (اختياري): onClick={live.cancel}
*/
