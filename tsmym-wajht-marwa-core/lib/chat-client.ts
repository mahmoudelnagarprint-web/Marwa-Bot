// lib/chat-client.ts — عميل المتصفح لـ /api/chat (بث NDJSON + حالة الأسطول)

export type ProviderBrief = { id: string; name: string; model: string }

export type GatewayEvent =
  | { type: 'plan'; active: ProviderBrief | null; standby: ProviderBrief | null; manual: boolean; pinged: boolean }
  | { type: 'attempt'; n: number; max: number; active: ProviderBrief; standby: ProviderBrief | null }
  | { type: 'failover'; n: number; max: number; from: ProviderBrief; to: ProviderBrief | null; standby: ProviderBrief | null; kind: string }
  | { type: 'tool'; provider: ProviderBrief; tools: string[] }

export type ChatDone = {
  ok: boolean
  status?: number
  text?: string
  reason?: string
  provider?: ProviderBrief
  standby?: ProviderBrief | null
  attempts?: number
  manual?: boolean
  latency_ms?: number
  [key: string]: unknown
}

export type FleetProvider = {
  id: string
  name: string
  model: string
  role: 'strong' | 'light'
  enabled: boolean
  status: 'up' | 'down' | 'unknown'
  cooling: boolean
  ping: { ok: boolean; ms: number; at: string } | null
}

export type FleetPlan = {
  ok: boolean
  manual: boolean
  active: ProviderBrief | null
  standby: ProviderBrief | null
  providers: FleetProvider[]
}

export type StreamChatBody = {
  agent: string
  messages: { role: 'user' | 'assistant'; content: string }[]
  maxTokens?: number
  providerId?: string // فارغ/undefined = اختيار آلي
  strictProvider?: boolean
}

export async function fetchFleet(agent: string, providerId?: string, signal?: AbortSignal): Promise<FleetPlan | null> {
  try {
    const qs = new URLSearchParams({ agent })
    if (providerId) qs.set('providerId', providerId)
    const res = await fetch(`/api/chat?${qs.toString()}`, { cache: 'no-store', signal })
    if (!res.ok) return null
    return (await res.json()) as FleetPlan
  } catch {
    return null
  }
}

/** يرسل الرسالة ويقرأ أحداث NDJSON الحية؛ يعيد السطر النهائي (type:"done") دائماً ولا يرمي إلا عند الإلغاء */
export async function streamChat(
  body: StreamChatBody,
  onEvent: (e: GatewayEvent) => void,
  signal?: AbortSignal,
): Promise<ChatDone> {
  const res = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...body, stream: true }),
    signal,
  })

  // أخطاء ما قبل البث (413 / 400) تأتي JSON عادياً
  if (!res.body) {
    return { ok: false, reason: 'المتصفح لا يدعم قراءة البث' }
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let done: ChatDone | null = null

  const handleLine = (line: string) => {
    const t = line.trim()
    if (!t) return
    let ev: { type?: string } & Record<string, unknown>
    try {
      ev = JSON.parse(t) as typeof ev
    } catch {
      return
    }
    if (ev.type === 'done' || ev.type === undefined) done = ev as unknown as ChatDone
    else onEvent(ev as unknown as GatewayEvent)
  }

  for (;;) {
    const { value, done: finished } = await reader.read()
    if (value) {
      buffer += decoder.decode(value, { stream: true })
      let idx: number
      while ((idx = buffer.indexOf('\n')) >= 0) {
        handleLine(buffer.slice(0, idx))
        buffer = buffer.slice(idx + 1)
      }
    }
    if (finished) break
  }
  buffer += decoder.decode()
  handleLine(buffer)

  return done ?? { ok: false, reason: 'انقطع الاتصال قبل اكتمال الرد' }
}
