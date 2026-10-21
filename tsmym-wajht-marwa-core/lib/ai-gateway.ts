// lib/ai-gateway.ts — بوابة الذكاء الاصطناعي المتقدمة (Enterprise AI Gateway)
// بأمر المالك 2026-10-21: تشغيل الشات الحي Zero-Downtime.
// المبادئ:
//   * مفاتيح المزودين لا تغادر السيرفر أبداً — GET يعيد مفتاحاً مقنعاً فقط.
//   * مفتاح من process.env (env_key) مفضل على مفتاح مخزن — لا أسرار في ملفات شجرية.
//   * Pre-flight Check: قبل توجيه المحادثة لمزود احتياطي يتم Ping سريع (GET /models).
//   * Smart Handover: على Context Overflow يتم Auto-Compact للسجل (ملخص + آخر الرسائل).
//   * Role-Based Routing: الوكلاء المعقدون → الأقوى، التنفيذيون → الأخف.
import fs from 'fs'
import path from 'path'

const ROOT = 'G:\\ai\\Naggar Print POS Agent'
const ACTIVE_DIR = path.join(ROOT, 'workspaces', 'vision_coder', 'active_workspaces')
export const PROVIDERS_FILE = path.join(ACTIVE_DIR, 'ai_providers.json')
export const USAGE_FILE = path.join(ACTIVE_DIR, 'ai_usage.json')

export type AiProvider = {
  id: string
  name: string
  base_url: string
  model: string
  max_tokens: number
  api_key?: string
  env_key?: string
  enabled: boolean
  role: 'strong' | 'light'
  added_at?: string
}

export type RoutingConfig = {
  complex: string[]
  executors: string[]
  default_role: 'strong' | 'light'
}

export type ProviderState = {
  status: 'up' | 'down' | 'unknown'
  last_error?: string
  cooldown_until?: string
  prompt_tokens: number
  completion_tokens: number
  calls: number
}

export type UsageFile = { day: string; providers: Record<string, ProviderState> }

export type ChatMsg = { role: 'system' | 'user' | 'assistant'; content: string }

export type HandoverStep = {
  at: string
  provider: string
  action: 'call' | 'preflight' | 'compact' | 'skip' | 'fail'
  detail: string
}

const DEFAULT_ROUTING: RoutingConfig = {
  complex: ['vision_coder', 'hakim_advisor'],
  executors: ['bebo_production', 'sasa_devices'],
  default_role: 'strong',
}

function readJson<T>(file: string, fallback: T): T {
  try {
    return JSON.parse(fs.readFileSync(file, 'utf8')) as T
  } catch {
    return fallback
  }
}

function writeJson(file: string, data: unknown): void {
  fs.mkdirSync(path.dirname(file), { recursive: true })
  const tmp = `${file}.tmp`
  fs.writeFileSync(tmp, JSON.stringify(data, null, 1), 'utf8')
  fs.renameSync(tmp, file)
}

/** قراءة قيمة من .env الجذر (سيرفر فقط) — dev server لا يرث متغيرات الجذر تلقائياً */
let envFileCache: Record<string, string> | null = null
function envFileValue(name: string): string | null {
  if (envFileCache === null) {
    envFileCache = {}
    try {
      for (const line of fs.readFileSync(path.join(ROOT, '.env'), 'utf8').split(/\r?\n/)) {
        const m = /^\s*([A-Z_0-9]+)\s*=\s*"?([^"\r\n]*)"?/.exec(line)
        if (m && m[2] !== undefined) envFileCache[m[1]] = m[2]
      }
    } catch { /* لا ملف — نعتمد process.env فقط */ }
  }
  return envFileCache[name] ?? null
}

/** أول تشغيل/تفريغ: بذر مزود Dahl من .env (مفتاح env فقط — لا سر في الملف) */
export function loadFleet(): { providers: AiProvider[]; routing: RoutingConfig } {
  const raw = readJson<{ providers?: AiProvider[]; routing?: RoutingConfig } | null>(PROVIDERS_FILE, null)
  const routing: RoutingConfig = { ...DEFAULT_ROUTING, ...raw?.routing }
  if (raw?.providers?.length) {
    return { providers: raw.providers, routing }
  }
  // self-heal: مزود Dahl يُبذر تلقائياً (الملف فاضي أو غير موجود) — بلا تكرار
  const dahlUrl = process.env.DAHL_API_URL || envFileValue('DAHL_API_URL')
  const dahlModel = process.env.DAHL_MODEL || envFileValue('DAHL_MODEL')
  const existing = raw?.providers ?? []
  if (dahlUrl && (process.env.DAHL_API_KEY || envFileValue('DAHL_API_KEY')) && !existing.some((p) => p.id === 'dahl-primary')) {
    existing.push({
      id: 'dahl-primary',
      name: 'Dahl (من .env)',
      base_url: dahlUrl,
      model: dahlModel || 'default-model',
      max_tokens: 8000,
      env_key: 'DAHL_API_KEY',
      enabled: true,
      role: 'strong',
      added_at: new Date().toISOString(),
    })
    const seeded = { providers: existing, routing }
    saveFleet(seeded)
    return seeded
  }
  const seeded = { providers: existing, routing }
  if (!raw) saveFleet(seeded)
  return seeded
}

export function saveFleet(fleet: { providers: AiProvider[]; routing: RoutingConfig }): void {
  writeJson(PROVIDERS_FILE, fleet)
}

export function loadUsage(): UsageFile {
  const today = new Date().toISOString().slice(0, 10)
  const u = readJson<UsageFile | null>(USAGE_FILE, null)
  if (u?.day === today && u.providers) return u
  // يوم جديد → عداد جلسة نظيف (Gauge يبدأ من صفر)
  return { day: today, providers: {} }
}

export function saveUsage(u: UsageFile): void {
  writeJson(USAGE_FILE, u)
}

export function stateOf(u: UsageFile, id: string): ProviderState {
  return u.providers[id] ?? { status: 'unknown', prompt_tokens: 0, completion_tokens: 0, calls: 0 }
}

export function resolveApiKey(p: AiProvider): string | null {
  if (p.env_key) {
    const v = process.env[p.env_key] || envFileValue(p.env_key)
    return v ? v : null
  }
  return p.api_key || null
}

export function maskKey(p: AiProvider): string {
  if (p.env_key) return `🔑 ${p.env_key} (من .env)`
  const k = p.api_key ?? ''
  if (!k) return '—'
  return `${k.slice(0, 6)}…${k.slice(-4)}`
}

/** تقدير التوكنز — عربي/إنجليزي مختلط: ~3 محارف لكل توكن */
export function estimateTokens(text: string): number {
  return Math.ceil((text || '').length / 3)
}

export function tokensOf(st: ProviderState): number {
  return st.prompt_tokens + st.completion_tokens
}

/** Pre-flight Check: Ping سريع (GET /models) بلا استهلاك توكنز */
export async function preflight(p: AiProvider): Promise<{ ok: boolean; status?: number; ms: number; detail?: string }> {
  const t0 = Date.now()
  const key = resolveApiKey(p)
  if (!key) return { ok: false, ms: 0, detail: 'لا مفتاح' }
  try {
    const ctl = new AbortController()
    const timer = setTimeout(() => ctl.abort(), 4000)
    const res = await fetch(`${p.base_url.replace(/\/$/, '')}/models`, {
      headers: { Authorization: `Bearer ${key}`, 'cache-control': 'no-store' },
      cache: 'no-store',
      signal: ctl.signal,
    })
    clearTimeout(timer)
    return { ok: res.ok, status: res.status, ms: Date.now() - t0 }
  } catch (e) {
    const cause = (e as { cause?: { code?: string; message?: string } })?.cause
    return { ok: false, ms: Date.now() - t0, detail: `${String(e).slice(0, 80)} | ${cause?.code ?? ''} ${cause?.message ?? ''}`.slice(0, 160) }
  }
}

export type ErrorKind = 'overflow' | 'auth' | 'quota' | 'rate' | 'server' | 'network' | 'unknown'

export function classifyFailure(status: number | null, body: string): ErrorKind {
  const b = (body || '').toLowerCase()
  if (status === 400 && (b.includes('context') || b.includes('maximum') || b.includes('token') || b.includes('length'))) {
    return 'overflow'
  }
  if (status === 401 || status === 403) return 'auth'
  if (status === 402) return 'quota'
  if (status === 429) return 'rate'
  if (status !== null && status >= 500) return 'server'
  if (status === null) return 'network'
  return 'unknown'
}

/** Smart Handover — Auto-Compact: ملخص الحالة + المهام الأخيرة فقط */
export function compactMessages(
  messages: ChatMsg[],
  keepLast = 8,
): { messages: ChatMsg[]; dropped: number; summary: string } {
  if (messages.length <= keepLast + 1) {
    return { messages, dropped: 0, summary: '' }
  }
  const system = messages[0]?.role === 'system' ? [messages[0]] : []
  const rest = messages[0]?.role === 'system' ? messages.slice(1) : messages
  const keep = rest.slice(-keepLast)
  const dropped = rest.length - keep.length
  const userGoals = rest.filter((m) => m.role === 'user').slice(0, -keepLast).map((m) => m.content.slice(0, 60))
  const summary =
    `【ملخص الحالة — Auto-Compact】 سجل أطول من حد المزود فاختُصر: ${dropped} رسالة سابقة ` +
    (userGoals.length ? `كانت حول: ${userGoals.join(' ؛ ').slice(0, 300)}. ` : '') +
    'المهام الأخيرة في الرسائل التالية.'
  return { messages: [...system, { role: 'user', content: summary }, ...keep], dropped, summary }
}

export function roleForAgent(agentWs: string, routing: RoutingConfig): 'strong' | 'light' {
  if (routing.complex.includes(agentWs)) return 'strong'
  if (routing.executors.includes(agentWs)) return 'light'
  return routing.default_role
}

/** ترتيب المحاولة: دور الوكيل أولاً ثم بقية المزودين (failover chain) */
export function orderForAgent(agentWs: string, fleet: { providers: AiProvider[]; routing: RoutingConfig }): AiProvider[] {
  const role = roleForAgent(agentWs, fleet.routing)
  const enabled = fleet.providers.filter((p) => p.enabled)
  const preferred = enabled.filter((p) => p.role === role)
  const rest = enabled.filter((p) => p.role !== role)
  return [...preferred, ...rest]
}

async function callOnce(
  p: AiProvider,
  messages: ChatMsg[],
  maxTokens: number,
): Promise<{ ok: true; text: string; prompt_tokens: number; completion_tokens: number; model: string } | { ok: false; status: number | null; body: string }> {
  const key = resolveApiKey(p)
  if (!key) return { ok: false, status: null, body: 'لا مفتاح متاح للمزود' }
  const ctl = new AbortController()
  const timer = setTimeout(() => ctl.abort(), 60_000)
  try {
    const res = await fetch(`${p.base_url.replace(/\/$/, '')}/chat/completions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${key}` },
      body: JSON.stringify({ model: p.model, messages, max_tokens: maxTokens, temperature: 0.6 }),
      signal: ctl.signal,
    })
    const fullText = await res.text()
    if (!res.ok) return { ok: false, status: res.status, body: fullText.slice(0, 600) }
    let j: {
      choices?: { message?: { content?: string } }[]
      usage?: { prompt_tokens?: number; completion_tokens?: number }
    }
    try {
      j = JSON.parse(fullText) as typeof j
    } catch {
      return { ok: false, status: res.status, body: 'رد غير JSON من المزود' }
    }
    if (!j.choices?.[0]?.message?.content) {
      return { ok: false, status: res.status, body: 'رد بلا محتوى من المزود' }
    }
    return {
      ok: true,
      text: j.choices[0].message.content,
      prompt_tokens: j.usage?.prompt_tokens ?? messages.reduce((s, m) => s + estimateTokens(m.content), 0),
      completion_tokens: j.usage?.completion_tokens ?? estimateTokens(j.choices[0].message.content),
      model: p.model,
    }
  } catch (e) {
    return { ok: false, status: null, body: e instanceof Error ? e.message.slice(0, 200) : 'شبكة' }
  } finally {
    clearTimeout(timer)
  }
}

export type ChatResult =
  | { ok: true; text: string; provider: { id: string; name: string; model: string }; handover: HandoverStep[]; compacted: boolean; usage: { prompt: number; completion: number } }
  | { ok: false; reason: string; handover: HandoverStep[] }

const COOLDOWN_MS = 90_000

/** المحرك الكامل: failover + preflight + auto-compact + عداد استهلاك */
export async function chatWithFailover(
  agentWs: string,
  messages: ChatMsg[],
  opts?: { maxTokens?: number },
): Promise<ChatResult> {
  const fleet = loadFleet()
  if (fleet.providers.length === 0) {
    return { ok: false, reason: 'لا مزودين — أضفهم من أسطول الذكاء في مركز القيادة التقنية', handover: [] }
  }
  const usage = loadUsage()
  const handover: HandoverStep[] = []
  const maxTokens = opts?.maxTokens ?? 700
  let compacted = false

  for (const p of orderForAgent(agentWs, fleet)) {
    const st = stateOf(usage, p.id)
    // مزود في فترة تهدئة → Pre-flight Ping قبل الثقة به (Zero-Downtime)
    if (st.cooldown_until && new Date(st.cooldown_until).getTime() > Date.now()) {
      const ping = await preflight(p)
      handover.push({ at: new Date().toISOString(), provider: p.name, action: 'preflight', detail: ping.ok ? `جاهز (${ping.ms}ms)` : `لا يستجيب (${ping.status ?? 'شبكة'})` })
      if (!ping.ok) continue
      st.cooldown_until = undefined
    }

    // حد التوكنز للجلسة اقترب → لا نضيف حمل على مزود شبه ممتلئ (تفادي خطأ 400)
    const sessionTokens = tokensOf(st)
    const gaugeRatio = p.max_tokens > 0 ? sessionTokens / p.max_tokens : 0
    if (gaugeRatio >= 1) {
      handover.push({ at: new Date().toISOString(), provider: p.name, action: 'skip', detail: `استهلاك الجلسة ${sessionTokens} وصل الحد ${p.max_tokens}` })
      continue
    }

    let msgs = messages
    handover.push({ at: new Date().toISOString(), provider: p.name, action: 'call', detail: `محاولة (${p.model})` })
    let r = await callOnce(p, msgs, maxTokens)

    // Context Overflow → Auto-Compact ثم إعادة على نفس المزود
    if (!r.ok && classifyFailure(r.status, r.body) === 'overflow') {
      const c = compactMessages(messages)
      compacted = c.dropped > 0
      msgs = c.messages
      handover.push({ at: new Date().toISOString(), provider: p.name, action: 'compact', detail: `ضُغط السجل — حُذف ${c.dropped} رسالة` })
      r = await callOnce(p, msgs, maxTokens)
    }

    if (r.ok) {
      const ps = stateOf(usage, p.id)
      ps.status = 'up'
      ps.calls += 1
      ps.prompt_tokens += r.prompt_tokens
      ps.completion_tokens += r.completion_tokens
      ps.last_error = undefined
      ps.cooldown_until = undefined
      usage.providers[p.id] = ps
      saveUsage(usage)
      return {
        ok: true,
        text: r.text,
        provider: { id: p.id, name: p.name, model: r.model },
        handover,
        compacted,
        usage: { prompt: r.prompt_tokens, completion: r.completion_tokens },
      }
    }

    // فشل → تصنيف + تهدئة + تمرير للتالي
    const kind = classifyFailure(r.status, r.body)
    const ps = stateOf(usage, p.id)
    ps.status = 'down'
    ps.last_error = `${kind}: ${r.body.slice(0, 160)}`
    if (kind === 'rate' || kind === 'quota' || kind === 'server') ps.cooldown_until = new Date(Date.now() + COOLDOWN_MS).toISOString()
    usage.providers[p.id] = ps
    saveUsage(usage)
    handover.push({ at: new Date().toISOString(), provider: p.name, action: 'fail', detail: `${kind} ${r.status ?? ''} ${r.body.slice(0, 80)}` })
  }

  return { ok: false, reason: 'كل المزودين غير متاحين حالياً', handover }
}
