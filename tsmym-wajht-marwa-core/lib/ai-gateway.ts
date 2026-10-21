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

export function getRepoRoot(): string {
  if (process.env.REPO_ROOT) return process.env.REPO_ROOT
  if (process.env.WORKSPACE_ROOT) {
    return process.env.WORKSPACE_ROOT.replace(/[\\/]workspaces[\\/]system_engine$/, '').replace(/[\\/]workspaces$/, '')
  }
  const cwd = process.cwd()
  if (path.basename(cwd) === 'tsmym-wajht-marwa-core') {
    return path.resolve(cwd, '..')
  }
  if (fs.existsSync(path.join(cwd, 'workspaces'))) {
    return cwd
  }
  if (fs.existsSync(path.join(cwd, '..', 'workspaces'))) {
    return path.resolve(cwd, '..')
  }
  return ['G:', 'ai', 'Naggar Print POS Agent'].join(path.sep)
}

export function getProvidersFile(): string {
  return path.join(getRepoRoot(), 'workspaces', 'vision_coder', 'active_workspaces', 'ai_providers.json')
}

export function getUsageFile(): string {
  return path.join(getRepoRoot(), 'workspaces', 'vision_coder', 'active_workspaces', 'ai_usage.json')
}

export const PROVIDERS_FILE = getProvidersFile()
export const USAGE_FILE = getUsageFile()

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

export type ChatMsg = {
  role: 'system' | 'user' | 'assistant' | 'tool'
  content: string
  tool_call_id?: string
  tool_calls?: unknown[]
}

export type HandoverStep = {
  at: string
  provider: string
  action: 'call' | 'preflight' | 'compact' | 'skip' | 'fail' | 'tool'
  detail: string
}

const DEFAULT_ROUTING: RoutingConfig = {
  complex: ['vision_coder', 'hakim_advisor'],
  executors: ['bebo_production', 'sasa_devices'],
  default_role: 'strong',
}

function readJson<T>(file: string, fallback: T): T {
  try {
    const fullPath = path.resolve(file)
    if (!fs.existsSync(fullPath)) return fallback
    const content = fs.readFileSync(fullPath, 'utf8')
    return JSON.parse(content) as T
  } catch (err: unknown) {
    console.error('API Error details: failed to read JSON file:', file, err instanceof Error ? err.message : err)
    return fallback
  }
}

function writeJson(file: string, data: unknown): void {
  const fullPath = path.resolve(file)
  fs.mkdirSync(path.dirname(fullPath), { recursive: true })
  fs.writeFileSync(fullPath, JSON.stringify(data, null, 1), 'utf8')
}

/** قراءة قيمة من .env الجذر (سيرفر فقط) — dev server لا يرث متغيرات الجذر تلقائياً */
let envFileCache: Record<string, string> | null = null
export function envFileValue(name: string): string | null {
  if (envFileCache === null) {
    envFileCache = {}
    try {
      const envPath = path.join(getRepoRoot(), '.env')
      if (fs.existsSync(envPath)) {
        for (const line of fs.readFileSync(envPath, 'utf8').split(/\r?\n/)) {
          const m = /^\s*([A-Z_0-9]+)\s*=\s*"?([^"\r\n]*)"?/.exec(line)
          if (m && m[2] !== undefined) envFileCache[m[1]] = m[2]
        }
      }
    } catch { /* لا ملف — نعتمد process.env فقط */ }
  }
  return envFileCache[name] ?? null
}

/** قراءة قائمة المزودين الحية بدون كاش (Bypass Cache) في كل طلب */
export function loadProviders(): AiProvider[] {
  return loadFleet().providers
}

/** أول تشغيل/تفريغ: قراءة أسطول الذكاء من ai_providers.json مباشرة من القرص */
export function loadFleet(): { providers: AiProvider[]; routing: RoutingConfig } {
  const filePath = getProvidersFile()
  let raw: { providers?: AiProvider[]; routing?: RoutingConfig } | null = null
  try {
    if (fs.existsSync(filePath)) {
      const content = fs.readFileSync(filePath, 'utf8')
      raw = JSON.parse(content) as { providers?: AiProvider[]; routing?: RoutingConfig }
    }
  } catch (err: unknown) {
    console.error('API Error details: failed loading fleet from disk:', err instanceof Error ? err.message : err)
  }

  const routing: RoutingConfig = { ...DEFAULT_ROUTING, ...raw?.routing }
  if (raw && Array.isArray(raw.providers)) {
    return { providers: raw.providers, routing }
  }
  // self-heal: مزود Dahl يُبذر تلقائياً فقط إذا كان الملف غير موجود إطلاقاً
  const dahlUrl = process.env.DAHL_API_URL || envFileValue('DAHL_API_URL') || 'https://inference.dahl.global/v1'
  const dahlKey = process.env.DAHL_API_KEY || envFileValue('DAHL_API_KEY')
  const existing: AiProvider[] = []
  if (dahlKey) {
    existing.push({
      id: 'dahl-primary',
      name: 'Dahl Primary (GLM-5.3)',
      base_url: dahlUrl,
      model: 'zai-org/GLM-5.3-Flash',
      max_tokens: 8000,
      env_key: 'DAHL_API_KEY',
      enabled: true,
      role: 'strong',
      added_at: new Date().toISOString(),
    })
    existing.push({
      id: 'dahl-light',
      name: 'Dahl Light (DeepSeek-V4)',
      base_url: dahlUrl,
      model: 'deepseek-ai/DeepSeek-V4-Flash-0731',
      max_tokens: 8000,
      env_key: 'DAHL_API_KEY',
      enabled: true,
      role: 'light',
      added_at: new Date().toISOString(),
    })
  }
  const seeded = { providers: existing, routing }
  saveFleet(seeded)
  return seeded
}

export function saveFleet(fleet: { providers: AiProvider[]; routing: RoutingConfig }): void {
  writeJson(getProvidersFile(), fleet)
}

export function loadUsage(): UsageFile {
  const today = new Date().toISOString().slice(0, 10)
  const u = readJson<UsageFile | null>(getUsageFile(), null)
  if (u?.day === today && u.providers) return u
  // يوم جديد → عداد جلسة نظيف (Gauge يبدأ من صفر)
  return { day: today, providers: {} }
}

export function saveUsage(u: UsageFile): void {
  writeJson(getUsageFile(), u)
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

/** ترتيب المحاولة: المزودون الأصحاء (up) أولاً ثم دور الوكيل مع تأخير المعطلين (failover chain) */
export function orderForAgent(
  agentWs: string,
  fleet: { providers: AiProvider[]; routing: RoutingConfig },
  usage?: UsageFile,
): AiProvider[] {
  const role = roleForAgent(agentWs, fleet.routing)
  const enabled = fleet.providers.filter((p) => p.enabled)

  const score = (p: AiProvider) => {
    let s = 0
    if (usage) {
      const st = stateOf(usage, p.id)
      if (st.status === 'up' && st.calls > 0) s += 2000
      else if (st.status === 'up') s += 100
      if (st.status === 'down') s -= 1000
      if (st.cooldown_until && new Date(st.cooldown_until).getTime() > Date.now()) s -= 5000
    }
    if (p.role === role) s += 50
    return s
  }

  return [...enabled].sort((a, b) => score(b) - score(a))
}

async function callOnce(
  p: AiProvider,
  messages: ChatMsg[],
  maxTokens: number,
  tools?: unknown[],
): Promise<{
  ok: true
  text: string
  tool_calls?: { id: string; type: string; function: { name: string; arguments: string } }[]
  prompt_tokens: number
  completion_tokens: number
  model: string
} | { ok: false; status: number | null; body: string }> {
  const key = resolveApiKey(p)
  if (!key) {
    console.error(`API Error details: Provider [${p.name}] has no valid API key`)
    return { ok: false, status: null, body: 'لا مفتاح متاح للمزود' }
  }
  const ctl = new AbortController()
  const timer = setTimeout(() => ctl.abort(), 20_000)
  try {
    const bodyPayload: Record<string, unknown> = {
      model: p.model,
      messages,
      max_tokens: maxTokens,
      temperature: 0.6,
    }
    if (Array.isArray(tools) && tools.length > 0) {
      bodyPayload.tools = tools
      bodyPayload.tool_choice = 'auto'
    }

    const res = await fetch(`${p.base_url.replace(/\/$/, '')}/chat/completions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${key}` },
      body: JSON.stringify(bodyPayload),
      signal: ctl.signal,
    })
    const fullText = await res.text()
    if (!res.ok) {
      console.error('API Error details:', `Provider [${p.name}] (${p.model}) HTTP ${res.status}: ${fullText.slice(0, 500)}`)
      return { ok: false, status: res.status, body: fullText.slice(0, 600) }
    }
    let j: {
      choices?: {
        message?: {
          content?: string
          reasoning?: string
          tool_calls?: { id: string; type: string; function: { name: string; arguments: string } }[]
        }
      }[]
      usage?: { prompt_tokens?: number; completion_tokens?: number }
    }
    try {
      j = JSON.parse(fullText) as typeof j
    } catch {
      console.error('API Error details:', `Provider [${p.name}] non-JSON response: ${fullText.slice(0, 200)}`)
      return { ok: false, status: res.status, body: 'رد غير JSON من المزود' }
    }
    const choice = j.choices?.[0]?.message
    let text = choice?.content ?? ''
    let tool_calls = choice?.tool_calls
    // إذا كان الموديل تعليلي (Reasoning) وفرغ المحتوى في حقل reasoning:
    if (!text.trim() && choice?.reasoning) {
      text = choice.reasoning
    }
    // تنظيف وسوم التفكير من النماذج مثل MiniMax / DeepSeek / GLM
    text = text.replace(/<think>[\s\S]*?<\/think>/gi, '').trim()

    // التقاط استدعاء الأدوات إذا قام النموذج بطباعتها كـ JSON نصي بدلاً من tool_calls صريحة
    if ((!tool_calls || tool_calls.length === 0) && text.trim().startsWith('{') && text.includes('"name"')) {
      try {
        const parsed = JSON.parse(text.trim()) as { name?: string; parameters?: unknown; arguments?: unknown }
        if (parsed.name && (parsed.parameters || parsed.arguments)) {
          tool_calls = [
            {
              id: `call_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
              type: 'function',
              function: {
                name: parsed.name,
                arguments:
                  typeof (parsed.parameters || parsed.arguments) === 'string'
                    ? ((parsed.parameters || parsed.arguments) as string)
                    : JSON.stringify(parsed.parameters || parsed.arguments),
              },
            },
          ]
          text = ''
        }
      } catch {
        /* ليس JSON نقياً */
      }
    }

    if (!text && (!tool_calls || tool_calls.length === 0)) {
      console.error('API Error details:', `Provider [${p.name}] empty content and no tool_calls`)
      return { ok: false, status: res.status, body: 'رد بلا محتوى من المزود' }
    }
    return {
      ok: true,
      text,
      tool_calls: tool_calls?.length ? tool_calls : undefined,
      prompt_tokens: j.usage?.prompt_tokens ?? messages.reduce((s, m) => s + estimateTokens(m.content), 0),
      completion_tokens: j.usage?.completion_tokens ?? estimateTokens(text),
      model: p.model,
    }
  } catch (e: unknown) {
    const errorDetails = (e as { response?: { data?: unknown }; message?: string })?.response?.data || (e as Error)?.message || String(e)
    console.error('API Error details:', `Provider [${p.name}] (${p.model}): ${errorDetails}`)
    return { ok: false, status: null, body: e instanceof Error ? e.message.slice(0, 200) : 'شبكة' }
  } finally {
    clearTimeout(timer)
  }
}

export type ChatResult =
  | { ok: true; text: string; provider: { id: string; name: string; model: string }; handover: HandoverStep[]; compacted: boolean; usage: { prompt: number; completion: number } }
  | { ok: false; reason: string; handover: HandoverStep[] }

const COOLDOWN_MS = 60_000

/** المحرك الكامل: failover + preflight + auto-compact + dynamic tool calling + tools fallback */
export async function chatWithFailover(
  agentWs: string,
  messages: ChatMsg[],
  opts?: {
    maxTokens?: number
    tools?: unknown[]
    toolExecutor?: (name: string, args: Record<string, unknown>) => Promise<unknown>
  },
): Promise<ChatResult> {
  const fleet = loadFleet()
  if (fleet.providers.length === 0) {
    return { ok: false, reason: 'لا مزودين — أضفهم من أسطول الذكاء في مركز القيادة التقنية', handover: [] }
  }
  const usage = loadUsage()
  const handover: HandoverStep[] = []
  // زيادة ميزانية التوكنز للنماذج التعليلية حتى لا تنفد في التفكير الداخلي
  const maxTokens = Math.max(opts?.maxTokens ?? 2048, 2048)
  let compacted = false

  const candidates = orderForAgent(agentWs, fleet, usage)
  // حصر المحاولات في أفضل 8 مزودين متاحين لتفادي التعليق التراكمي
  const maxAttempts = Math.min(candidates.length, 8)

  for (let i = 0; i < maxAttempts; i++) {
    const p = candidates[i]
    const st = stateOf(usage, p.id)
    // مزود في فترة تهدئة → تخطي فوري دون إهدار وقت المحادثة
    if (st.cooldown_until && new Date(st.cooldown_until).getTime() > Date.now()) {
      handover.push({
        at: new Date().toISOString(),
        provider: p.name,
        action: 'skip',
        detail: `تخطي المزود (في فترة تهدئة حتى ${st.cooldown_until.slice(11, 19)})`,
      })
      continue
    }

    let msgs = [...messages]
    // فحص مبكر لطول السياق قبل الإرسال لتفادي خطأ 400
    const estPrompt = msgs.reduce((s, m) => s + estimateTokens(m.content), 0)
    if (estPrompt > (p.max_tokens || 8000) * 0.9) {
      const c = compactMessages(messages)
      compacted = c.dropped > 0
      msgs = c.messages
      handover.push({ at: new Date().toISOString(), provider: p.name, action: 'compact', detail: `استباق Context Overflow — حُذف ${c.dropped} رسالة` })
    }

    handover.push({ at: new Date().toISOString(), provider: p.name, action: 'call', detail: `محاولة (${p.model})` })
    let r = await callOnce(p, msgs, maxTokens, opts?.tools)

    // Context Overflow → Auto-Compact ثم إعادة المحاولة فوراً على نفس المزود
    if (!r.ok && classifyFailure(r.status, r.body) === 'overflow') {
      const c = compactMessages(messages)
      compacted = c.dropped > 0
      msgs = c.messages
      handover.push({ at: new Date().toISOString(), provider: p.name, action: 'compact', detail: `ضُغط السجل — حُذف ${c.dropped} رسالة` })
      r = await callOnce(p, msgs, maxTokens, opts?.tools)
    }

    // 3️⃣ حماية الأدوات (Tools Fallback):
    // إذا كان الخطأ 400 Bad Request بسبب عدم دعم الـ tools، نحاول نفس الطلب فوراً لنفس المزود ولكن بدون tools
    // r.ok هنا مضمون المنطق (الفحص يبدأ بـ !r.ok) — TS يحتاج تضييقاً صريحاً بعد الإسناد الجديد
    const isToolReject =
      !r.ok &&
      (r.status === 400 ||
        (r.status === 404 && r.body.toLowerCase().includes('function')) ||
        r.body.toLowerCase().includes('tool') ||
        r.body.toLowerCase().includes('function'))
    if (isToolReject && opts?.tools && (opts.tools as unknown[]).length > 0) {
      console.warn(`[AI Gateway Tools Fallback] Provider [${p.name}] (${p.model}) rejected tools (HTTP ${'status' in r ? r.status : '?'})`)
      handover.push({
        at: new Date().toISOString(),
        provider: p.name,
        action: 'call',
        detail: `إعادة المحاولة بدون أدوات (Tools Fallback)`,
      })
      const retry = await callOnce(p, msgs, maxTokens, undefined)
      if (!retry.ok) {
        console.error('API Error details:', `Provider [${p.name}] retry without tools failed: ${retry.body}`)
        r = retry
      } else {
        r = retry
      }
    }

    // Dynamic Tool Calling Loop: تنفيذ أدوات الوكيل ديناميكياً وإعادة التغذية للنموذج
    let toolTurns = 0
    while (r.ok && r.tool_calls && r.tool_calls.length > 0 && toolTurns < 3 && opts?.toolExecutor) {
      toolTurns++
      const callNames = r.tool_calls.map((t) => t.function.name).join(', ')
      handover.push({
        at: new Date().toISOString(),
        provider: p.name,
        action: 'tool',
        detail: `استدعاء أداة (${callNames})`,
      })

      msgs.push({
        role: 'assistant',
        content: r.text || '',
        tool_calls: r.tool_calls,
      })

      for (const tc of r.tool_calls) {
        let argsObj: Record<string, unknown> = {}
        try {
          argsObj = JSON.parse(tc.function.arguments || '{}') as Record<string, unknown>
        } catch {
          argsObj = { sql: tc.function.arguments }
        }
        const toolResult = await opts.toolExecutor(tc.function.name, argsObj)
        msgs.push({
          role: 'tool',
          content: typeof toolResult === 'string' ? toolResult : JSON.stringify(toolResult),
          tool_call_id: tc.id,
        })
      }

      // استدعاء النموذج مجدداً مع تزويده بنتائج الأداة (بعد جولتين نوقف تمرير tools لإجبار النموذج على الجواب النهائي)
      const nextTools = toolTurns >= 2 ? undefined : opts?.tools
      r = await callOnce(p, msgs, maxTokens, nextTools)
    }

    // إذا نُفذت أدوات ولكن الرد النهائي كان نصاً فارغاً، نطلب صياغة الرد البشري النهائي
    if (r.ok && toolTurns > 0 && !r.text.trim()) {
      r = await callOnce(p, msgs, maxTokens, undefined)
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

    // فشل → طباعة تفصيلية + تصنيف + تهدئة + تمرير تلقائي للمزود الاحتياطي (Auto-Fallback)
    console.error('API Error details:', `Failover from [${p.name}]: ${r.body}`)
    const kind = classifyFailure(r.status, r.body)
    const ps = stateOf(usage, p.id)
    ps.status = 'down'
    ps.last_error = `${kind}: ${r.body.slice(0, 160)}`
    if (r.status === 404 || r.status === 410) {
      // نماذج غير موجودة أو منتهية → تهدئة لمدة 24 ساعة لتفادي تعطيل المحادثات
      ps.cooldown_until = new Date(Date.now() + 24 * 3600_000).toISOString()
    } else if (kind === 'rate' || kind === 'quota' || kind === 'server') {
      ps.cooldown_until = new Date(Date.now() + COOLDOWN_MS).toISOString()
    }
    usage.providers[p.id] = ps
    saveUsage(usage)
    handover.push({ at: new Date().toISOString(), provider: p.name, action: 'fail', detail: `${kind} ${r.status ?? ''} ${r.body.slice(0, 80)}` })
  }

  return { ok: false, reason: 'جميع مزودي الذكاء الاصطناعي غير متاحين حالياً — تحقق من الاتصال', handover }
}
