// lib/ai-gateway.ts — بوابة الذكاء الاصطناعي (Enterprise AI Gateway) — v3 (Active / Hot-Standby)
// الجديد في v3:
//   * Auto-Test: Ping متوازٍ لكل المزودين (مخزّن 60ث مع تحديث خلفي) → الأسرع والأكثر استقراراً = Active، التالي = Hot Standby.
//   * Manual Override: providerId يلغي الاختبار الآلي ويجعل المزود المختار Active (strictProvider = بلا احتياطي).
//   * MAX_ATTEMPTS = 5 انتقالات، ومهلة صارمة 15ث لكل طلب HTTP (قابلة للضبط AI_GATEWAY_TIMEOUT_MS).
//   * onEvent: أحداث حية (plan / attempt / failover / tool) تغذّي مؤقت الواجهة وشريط الحالة.
// المبادئ القديمة باقية: مفاتيح لا تغادر السيرفر، قراءة ai_providers.json حية، Tools Fallback، Cooldown تصاعدي، Auto-Compact.
import fs from 'fs'
import path from 'path'
import { createHash } from 'crypto'

// ───────────────────────────── ثوابت قابلة للضبط ─────────────────────────────

function envInt(name: string, fallback: number): number {
  const n = Number(process.env[name])
  return Number.isFinite(n) && n > 0 ? n : fallback
}

const REQUEST_TIMEOUT_MS = envInt('AI_GATEWAY_TIMEOUT_MS', 10_000) // مهلة صارمة لكل طلب HTTP (قاطع الدائرة عند 10ث)
const TOTAL_BUDGET_MS = envInt('AI_GATEWAY_BUDGET_MS', 90_000) // سقف زمني كلي للطلب
const PING_TIMEOUT_MS = envInt('AI_GATEWAY_PING_TIMEOUT_MS', 4_000)
const PING_TTL_MS = envInt('AI_GATEWAY_PING_TTL_MS', 60_000) // عمر نتيجة الـ Ping قبل التحديث الخلفي
export const MAX_ATTEMPTS = 5
const NO_TOOLS_TTL_MS = 30 * 60_000

/** قاطع الدائرة: كل عطل «مهلة أو تجاوز حد» يبرّد المزود 5 دقائق كاملة بلا تصاعد. */
export const CIRCUIT_BREAKER_MS = envInt('AI_GATEWAY_BREAKER_MS', 5 * 60_000)

/** سقف أحرف تعليمات الخلفية بعد التقليم (التعليمات الأساسية فقط، بلا سجل دردشة). */
const BACKGROUND_SYSTEM_CAP = envInt('AI_GATEWAY_BACKGROUND_SYSTEM_CAP', 12_000)

// ───────────────────────────── المسارات ─────────────────────────────

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

// ───────────────────────────── الأنواع ─────────────────────────────

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

export type ErrorKind = 'overflow' | 'auth' | 'quota' | 'rate' | 'timeout' | 'server' | 'network' | 'gone' | 'unknown'

/** أسباب فشل الطلب كاملاً — تُمكّن عامل الخلفية من معرفة متى يُرجئ المهمة بدل إعادة المحاولة */
export type ExhaustReason = 'no_providers' | 'all_cooling' | 'all_failed'

export type ProviderState = {
  status: 'up' | 'down' | 'unknown'
  last_error?: string
  cooldown_until?: string
  prompt_tokens: number
  completion_tokens: number
  calls: number
  cooldown_kind?: ErrorKind
  fail_streak?: number
  fp?: string
  no_tools_until?: string
  /** عدد مرات ضرب القاطع لهذا المزود اليوم — يظهر في مركز الأسطول */
  breaker_hits?: number
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

export type ProviderBrief = { id: string; name: string; model: string }

/** أحداث حية تُبث للواجهة (عبر NDJSON في route.ts) */
export type GatewayEvent =
  | { type: 'plan'; active: ProviderBrief | null; standby: ProviderBrief | null; manual: boolean; pinged: boolean }
  | { type: 'attempt'; n: number; max: number; active: ProviderBrief; standby: ProviderBrief | null }
  | {
      type: 'failover'
      n: number
      max: number
      from: ProviderBrief
      to: ProviderBrief | null
      standby: ProviderBrief | null
      kind: ErrorKind
    }
  | { type: 'tool'; provider: ProviderBrief; tools: string[] }

const DEFAULT_ROUTING: RoutingConfig = {
  complex: ['vision_coder', 'hakim_advisor'],
  executors: ['bebo_production', 'sasa_devices'],
  default_role: 'strong',
}

function errMsg(err: unknown): string {
  return err instanceof Error ? err.message : String(err)
}

const sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms))

function brief(p: AiProvider): ProviderBrief {
  return { id: p.id, name: p.name, model: p.model }
}

// ───────────────────────────── القراءة والكتابة على القرص ─────────────────────────────

function readJson<T>(file: string, fallback: T): T {
  try {
    const fullPath = path.resolve(file)
    if (!fs.existsSync(fullPath)) return fallback
    const content = fs.readFileSync(fullPath, 'utf8').replace(/^\uFEFF/, '')
    return JSON.parse(content) as T
  } catch (err: unknown) {
    console.error('API Error details: failed to read JSON file:', file, errMsg(err))
    return fallback
  }
}

function writeJson(file: string, data: unknown): void {
  const fullPath = path.resolve(file)
  fs.mkdirSync(path.dirname(fullPath), { recursive: true })
  const payload = JSON.stringify(data, null, 1)
  const tmp = `${fullPath}.${process.pid}.${Date.now()}.tmp`
  try {
    fs.writeFileSync(tmp, payload, 'utf8')
    fs.renameSync(tmp, fullPath)
  } catch {
    try { fs.unlinkSync(tmp) } catch { /* نتجاهل */ }
    fs.writeFileSync(fullPath, payload, 'utf8')
  }
}

let envFileCache: { file: string; mtimeMs: number; size: number; values: Record<string, string> } | null = null

export function envFileValue(name: string): string | null {
  const envPath = path.join(getRepoRoot(), '.env')
  try {
    const st = fs.statSync(envPath)
    if (!envFileCache || envFileCache.file !== envPath || envFileCache.mtimeMs !== st.mtimeMs || envFileCache.size !== st.size) {
      const values: Record<string, string> = {}
      for (const line of fs.readFileSync(envPath, 'utf8').replace(/^\uFEFF/, '').split(/\r?\n/)) {
        const m = /^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$/.exec(line)
        if (!m) continue
        let v = m[2].trim()
        if (v.length >= 2 && ((v.startsWith('"') && v.endsWith('"')) || (v.startsWith("'") && v.endsWith("'")))) {
          v = v.slice(1, -1)
        } else {
          v = v.replace(/\s+#.*$/, '')
        }
        values[m[1]] = v
      }
      envFileCache = { file: envPath, mtimeMs: st.mtimeMs, size: st.size, values }
    }
    return envFileCache.values[name] ?? null
  } catch {
    envFileCache = null
    return null
  }
}

// ───────────────────────────── الأسطول: قراءة حية من القرص في كل طلب ─────────────────────────────

let lastGoodFleet: { providers: AiProvider[]; routing: RoutingConfig } | null = null
const warnedInvalid = new Set<string>()

function normalizeProviders(list: unknown[]): AiProvider[] {
  const out: AiProvider[] = []
  list.forEach((item, idx) => {
    const p = item as Partial<AiProvider> | null
    const valid =
      !!p && typeof p === 'object' &&
      typeof p.id === 'string' && p.id.length > 0 &&
      typeof p.base_url === 'string' && p.base_url.length > 0 &&
      typeof p.model === 'string' && p.model.length > 0
    if (!valid) {
      const k = `${idx}:${(p as { id?: string } | null)?.id ?? '?'}`
      if (!warnedInvalid.has(k)) {
        warnedInvalid.add(k)
        console.warn(`[AI Gateway] تجاهل مزود غير صالح في ai_providers.json (الترتيب ${idx}) — يلزم id و base_url و model`)
      }
      return
    }
    out.push(p as AiProvider)
  })
  return out
}

function normalizeRouting(r: Partial<RoutingConfig> | undefined): RoutingConfig {
  return {
    complex: Array.isArray(r?.complex) ? (r!.complex as string[]) : DEFAULT_ROUTING.complex,
    executors: Array.isArray(r?.executors) ? (r!.executors as string[]) : DEFAULT_ROUTING.executors,
    default_role: r?.default_role === 'light' || r?.default_role === 'strong' ? r.default_role : DEFAULT_ROUTING.default_role,
  }
}

export function loadProviders(): AiProvider[] {
  return loadFleet().providers
}

export function loadFleet(): { providers: AiProvider[]; routing: RoutingConfig } {
  const filePath = getProvidersFile()
  let exists = false
  let raw: { providers?: unknown; routing?: Partial<RoutingConfig> } | null = null

  try {
    exists = fs.existsSync(filePath)
    if (exists) {
      const content = fs.readFileSync(filePath, 'utf8').replace(/^\uFEFF/, '')
      raw = JSON.parse(content) as { providers?: unknown; routing?: Partial<RoutingConfig> }
    }
  } catch (err: unknown) {
    console.error('API Error details: failed loading fleet from disk (الملف لن يُمس):', errMsg(err))
    if (lastGoodFleet) return lastGoodFleet
    return { providers: [], routing: { ...DEFAULT_ROUTING } }
  }

  const routing = normalizeRouting(raw?.routing)

  if (raw && Array.isArray(raw.providers)) {
    const fleet = { providers: normalizeProviders(raw.providers), routing }
    lastGoodFleet = fleet
    return fleet
  }

  if (exists) {
    console.error('API Error details: ai_providers.json لا يحتوي مصفوفة providers — لن يتم تعديل الملف')
    return { providers: [], routing }
  }

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
  try {
    saveFleet(seeded)
  } catch (err) {
    console.error('API Error details: تعذر حفظ الأسطول المبذور:', errMsg(err))
  }
  lastGoodFleet = seeded
  return seeded
}

export function saveFleet(fleet: { providers: AiProvider[]; routing: RoutingConfig }): void {
  writeJson(getProvidersFile(), fleet)
  lastGoodFleet = fleet
}

// ───────────────────────────── الاستخدام وحالة المزودين ─────────────────────────────

export function loadUsage(): UsageFile {
  const today = new Date().toISOString().slice(0, 10)
  const u = readJson<UsageFile | null>(getUsageFile(), null)
  if (u?.day === today && u.providers) return u
  return { day: today, providers: {} }
}

export function saveUsage(u: UsageFile): void {
  writeJson(getUsageFile(), u)
}

export function stateOf(u: UsageFile, id: string): ProviderState {
  return u.providers[id] ?? { status: 'unknown', prompt_tokens: 0, completion_tokens: 0, calls: 0 }
}

function mutateState(id: string, fn: (st: ProviderState) => void): void {
  try {
    const u = loadUsage()
    const st = stateOf(u, id)
    fn(st)
    u.providers[id] = st
    saveUsage(u)
  } catch (err) {
    console.error('[AI Gateway] تعذر حفظ حالة المزود', id, errMsg(err))
  }
}

function resetHealth(st: ProviderState): void {
  st.status = 'unknown'
  st.last_error = undefined
  st.cooldown_until = undefined
  st.cooldown_kind = undefined
  st.fail_streak = 0
  st.no_tools_until = undefined
  st.fp = undefined
}

export function resolveApiKey(p: AiProvider): string | null {
  if (p.env_key) {
    const v = envFileValue(p.env_key) || process.env[p.env_key]
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

function providerFingerprint(p: AiProvider): string {
  return createHash('sha256').update(`${p.base_url}|${p.model}|${resolveApiKey(p) ?? ''}`).digest('hex').slice(0, 12)
}

function syncStateWithConfig(p: AiProvider, usage: UsageFile): void {
  const st = stateOf(usage, p.id)
  if (st.fp && st.fp !== providerFingerprint(p)) {
    resetHealth(st)
    usage.providers[p.id] = st
    mutateState(p.id, resetHealth)
    pingCache.delete(p.id)
    console.warn(`[AI Gateway] تغيّر إعداد المزود [${p.name}] (مفتاح/نموذج/عنوان) → إلغاء التبريد والحالة السابقة`)
  }
}

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
  const ctl = new AbortController()
  const timer = setTimeout(() => ctl.abort(), PING_TIMEOUT_MS)
  try {
    const res = await fetch(`${p.base_url.replace(/\/$/, '')}/models`, {
      headers: { Authorization: `Bearer ${key}`, 'cache-control': 'no-store' },
      cache: 'no-store',
      signal: ctl.signal,
    })
    return { ok: res.ok, status: res.status, ms: Date.now() - t0 }
  } catch (e) {
    const cause = (e as { cause?: { code?: string; message?: string } })?.cause
    return { ok: false, ms: Date.now() - t0, detail: `${String(e).slice(0, 80)} | ${cause?.code ?? ''} ${cause?.message ?? ''}`.slice(0, 160) }
  } finally {
    clearTimeout(timer)
  }
}

// ───────────────────────────── (v3) الاختبار الآلي: Ping + ترتيب Active / Standby ─────────────────────────────

export type PingResult = { id: string; ok: boolean; ms: number; status?: number; checkedAt: number; detail?: string }

const pingCache = new Map<string, PingResult & { fp: string }>()
let pingRefreshedAt = 0
let pingInflight: Promise<void> | null = null

async function pingProvider(p: AiProvider): Promise<PingResult> {
  const r = await preflight(p)
  // بعض المزودين لا يوفرون /models (404/405/501) لكن الخادم نفسه حي → نعتبره متاحاً
  const reachable = r.ok || (r.status !== undefined && [404, 405, 501].includes(r.status))
  return { id: p.id, ok: reachable, ms: r.ms, status: r.status, checkedAt: Date.now(), detail: r.detail }
}

function runPing(providers: AiProvider[]): Promise<void> {
  if (!pingInflight) {
    pingInflight = (async () => {
      const results = await Promise.all(providers.map(pingProvider))
      for (const r of results) {
        const p = providers.find((x) => x.id === r.id)
        if (p) pingCache.set(r.id, { ...r, fp: providerFingerprint(p) })
      }
      pingRefreshedAt = Date.now()
    })().finally(() => {
      pingInflight = null
    })
  }
  return pingInflight
}

/** أول مرة (أو مزود جديد/معدّل) ننتظر الـ Ping؛ بعدها نستخدم النتيجة المخزنة ونحدّثها في الخلفية */
async function ensurePings(providers: AiProvider[]): Promise<void> {
  if (providers.length === 0) return
  const missing = providers.some((p) => {
    const c = pingCache.get(p.id)
    return !c || c.fp !== providerFingerprint(p)
  })
  if (missing) {
    await runPing(providers)
    return
  }
  if (Date.now() - pingRefreshedAt > PING_TTL_MS) void runPing(providers)
}

/** الأقل درجة = الأفضل: زمن الـ Ping + عقوبة الأعطال المتتالية + مكافأة تطابق الدور */
function rankByPing(providers: AiProvider[], role: 'strong' | 'light', usage: UsageFile): AiProvider[] {
  const score = (p: AiProvider) => {
    const c = pingCache.get(p.id)
    const st = stateOf(usage, p.id)
    let s: number
    if (!c) s = 3000
    else if (!c.ok) s = 100_000 + c.ms
    else s = c.ms
    s += (st.fail_streak ?? 0) * 1500
    if (st.status === 'down') s += 2000
    if (p.role === role) s -= 200
    return s
  }
  return [...providers].sort((a, b) => score(a) - score(b))
}

type GatewayPlan = {
  queue: AiProvider[] // queue[0] = Active ، التالي = Hot Standby
  manual: AiProvider | null
  pinged: boolean
  skipped: { name: string; detail: string }[]
  notes: string[]
}

function isCooling(usage: UsageFile, p: AiProvider): boolean {
  const st = stateOf(usage, p.id)
  return !!st.cooldown_until && Date.parse(st.cooldown_until) > Date.now()
}

/** أقرب وقت يعود فيه مزود للخدمة — يُستخدم لتحديد مدة إرجاء مهام الخلفية. */
export function earliestCooldownRemaining(usage: UsageFile, providers: AiProvider[]): number {
  const now = Date.now()
  const ends = providers
    .map((p) => Date.parse(stateOf(usage, p.id).cooldown_until ?? ''))
    .filter((t) => Number.isFinite(t) && t > now)
  if (ends.length === 0) return 0
  return Math.min(...ends) - now
}

async function buildPlan(
  agentWs: string,
  fleet: { providers: AiProvider[]; routing: RoutingConfig },
  usage: UsageFile,
  o?: { providerId?: string; strictProvider?: boolean; patient?: boolean },
): Promise<GatewayPlan> {
  const role = roleForAgent(agentWs, fleet.routing)
  const enabled = fleet.providers.filter((p) => p.enabled)
  const notes: string[] = []
  const skipped: { name: string; detail: string }[] = []
  const manual = o?.providerId ? (enabled.find((p) => p.id === o.providerId) ?? null) : null
  if (o?.providerId && !manual) {
    notes.push(`المزود المحدد يدوياً (${o.providerId}) غير موجود أو معطّل — عودة للاختيار الآلي`)
  }

  // الاختيار اليدوي المطلق: لا Ping، والمزود المختار Active حتى لو كان في تبريد
  if (manual) {
    const queue: AiProvider[] = [manual]
    if (!o?.strictProvider) {
      const others = enabled.filter((p) => p.id !== manual.id && !isCooling(usage, p))
      queue.push(...rankByPing(others, role, usage)) // ترتيب من آخر Ping مخزّن فقط، بلا اختبار جديد
    }
    notes.push(`اختيار يدوي: ${manual.name} (تجاوز الاختبار الآلي${o?.strictProvider ? '، بلا احتياطي' : ''})`)
    return { queue, manual, pinged: false, skipped, notes }
  }

  await ensurePings(enabled)

  const cooling = enabled.filter((p) => isCooling(usage, p))
  for (const p of cooling) {
    const st = stateOf(usage, p.id)
    skipped.push({
      name: p.name,
      detail: `تخطي فوري (تبريد ${st.cooldown_kind ?? ''} حتى ${(st.cooldown_until ?? '').slice(11, 19)} UTC)`,
    })
  }
  let queue = rankByPing(
    enabled.filter((p) => !isCooling(usage, p)),
    role,
    usage,
  )
  if (queue.length === 0 && cooling.length > 0 && !o?.patient) {
    // كل المزودين مبرّدون: محاولة أخيرة للأقرب انتهاءً (عدا الذين «اختفوا» 404/410)
    // patient=true (مهمة خلفية): لا نحاول إطلاقاً — نُرجع النفاد فوراً ليجدول العامل إرجاعاً متزايداً
    queue = cooling
      .filter((p) => stateOf(usage, p.id).cooldown_kind !== 'gone')
      .sort((a, b) => Date.parse(stateOf(usage, a.id).cooldown_until ?? '') - Date.parse(stateOf(usage, b.id).cooldown_until ?? ''))
      .slice(0, 2)
    if (queue.length > 0) notes.push(`كل المزودين في تبريد — محاولة أخيرة على ${queue.map((x) => x.name).join(' / ')}`)
  }
  return { queue, manual: null, pinged: true, skipped, notes }
}

/** حالة الأسطول للواجهة (GET /api/chat): القائمة المنسدلة + Active/Standby الحاليان */
export async function describeFleet(agentWs: string, o?: { providerId?: string }) {
  const fleet = loadFleet()
  const usage = loadUsage()
  for (const p of fleet.providers.filter((x) => x.enabled)) syncStateWithConfig(p, usage)
  const plan = await buildPlan(agentWs, fleet, usage, { providerId: o?.providerId })
  const active = plan.queue[0] ?? null
  const standby = plan.queue.find((p) => active && p.id !== active.id) ?? null
  return {
    manual: !!plan.manual,
    active: active ? brief(active) : null,
    standby: standby ? brief(standby) : null,
    providers: fleet.providers.map((p) => {
      const c = pingCache.get(p.id)
      const st = stateOf(usage, p.id)
      return {
        id: p.id,
        name: p.name,
        model: p.model,
        role: p.role,
        enabled: p.enabled,
        status: st.status,
        cooling: isCooling(usage, p),
        ping: c ? { ok: c.ok, ms: c.ms, at: new Date(c.checkedAt).toISOString() } : null,
      }
    }),
  }
}

// ───────────────────────────── تصنيف الأخطاء والتبريد ─────────────────────────────

export function classifyFailure(status: number | null, body: string): ErrorKind {
  const b = (body || '').toLowerCase()
  if (status === 413) return 'overflow'
  if (status === 400 && (b.includes('context') || b.includes('maximum') || b.includes('token') || b.includes('length'))) {
    return 'overflow'
  }
  if (status === 404 || status === 410) return 'gone'
  if (status === 401 || status === 403) return 'auth'
  if (status === 402) return 'quota'
  if (status === 429) return 'rate'
  if (status !== null && status >= 500) return 'server'
  // مهلة داخلية بلا استجابة HTTP = قاطع الدائرة (لا خطأ شبكة عابر)
  if (status === null) return /انتهت (مهلة|المهلة)|timeout|timed out|aborted/i.test(body || '') ? 'timeout' : 'network'
  return 'unknown'
}

const COOLDOWN_RULES: Partial<Record<ErrorKind, { base: number; max: number }>> = {
  gone: { base: 10 * 60_000, max: 24 * 3600_000 },
  auth: { base: 2 * 60_000, max: 30 * 60_000 },
  quota: { base: CIRCUIT_BREAKER_MS, max: 6 * 3600_000 },
  // قاطع الدائرة: المهلة و429 يبرّدان 5 دقائق ثابتة (بلا تصاعد) عشان الاختيار الآلي يعديهم فوراً
  rate: { base: CIRCUIT_BREAKER_MS, max: CIRCUIT_BREAKER_MS },
  timeout: { base: CIRCUIT_BREAKER_MS, max: CIRCUIT_BREAKER_MS },
  server: { base: 30_000, max: 10 * 60_000 },
  network: { base: 30_000, max: 10 * 60_000 },
}

function cooldownFor(kind: ErrorKind, status: number | null, streak: number, retryAfterMs?: number): number {
  const rule = COOLDOWN_RULES[kind]
  if (!rule) return 0
  // القاطع الثابت: تجاوز الحد أو المهلة → 5 دقائق دائماً، ولو طلب المزود Retry-After أقل
  if (kind === 'rate' || kind === 'timeout') {
    return Math.max(rule.base, Math.min(retryAfterMs ?? 0, rule.max))
  }
  let base = rule.base
  if (status === 410) base = Math.max(base, 60 * 60_000)
  let ms = Math.min(rule.max, base * Math.pow(2, Math.min(Math.max(streak - 1, 0), 10)))
  if (retryAfterMs && (kind === 'server' || kind === 'quota')) {
    ms = Math.min(rule.max, Math.max(retryAfterMs, 5_000))
  }
  return ms
}

// ───────────────────────────── Smart Handover / Routing ─────────────────────────────

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

/**
 * التقليم الذكي للسياق — لمهام الخلفية فقط (العامل المجدول والنبض الاستباقي).
 * مهمة خلفية لا تحتاج سجل دردشة إطلاقاً: نُبقي «التعليمات الأساسية + بيانات المهمة» فقط،
 * ونحذف الرسائل السابقة وكتل البيانات الحية المحقونة في الـ System Prompt (POS والغرف)
 * لأن الوكيل يستدعيها بنفسه عبر الأداة عند الحاجة. النتيجة: Payload أصغر وتوفير مباشر في التوكنز.
 */
const BACKGROUND_BLOCK_MARK = '--- بيانات '

/** يحذف كتلة بيانات حية محقونة: من سطر العنوان حتى أول فاصل سطرين فارغين. */
function stripInjectedBlocks(text: string): string {
  let out = text
  let guard = 0
  while (guard++ < 8) {
    const i = out.indexOf(BACKGROUND_BLOCK_MARK)
    if (i === -1) break
    const end = out.indexOf('\n\n', i + BACKGROUND_BLOCK_MARK.length)
    out = end === -1 ? out.slice(0, i) : out.slice(0, i) + out.slice(end)
  }
  return out
}

export function trimBackgroundMessages(
  messages: ChatMsg[],
  o?: { systemCap?: number; taskCap?: number },
): { messages: ChatMsg[]; dropped: number; savedChars: number; systemChars: number } {
  const systemCap = o?.systemCap ?? BACKGROUND_SYSTEM_CAP
  const taskCap = o?.taskCap ?? 4000
  const before = messages.reduce((s, m) => s + m.content.length, 0)

  const system = messages
    .filter((m) => m.role === 'system')
    .map((m) => stripInjectedBlocks(m.content).trim())
    .filter(Boolean)
    .join('\n\n')
  const cappedSystem =
    system.length > systemCap ? `${system.slice(0, systemCap)}\n[اقتُطع السياق لتوفير التوكنز]` : system

  const userMsgs = messages.filter((m) => m.role === 'user')
  const taskMsg = userMsgs[userMsgs.length - 1] // بيانات المهمة المطلوبة فقط

  const out: ChatMsg[] = []
  if (cappedSystem) out.push({ role: 'system', content: cappedSystem })
  if (taskMsg) {
    const content = taskMsg.content.length > taskCap ? `${taskMsg.content.slice(0, taskCap)}\n[اقتُطعت المهمة]` : taskMsg.content
    out.push({ role: 'user', content })
  }

  const after = out.reduce((s, m) => s + m.content.length, 0)
  return {
    messages: out,
    dropped: messages.length - out.length,
    savedChars: Math.max(0, before - after),
    systemChars: cappedSystem.length,
  }
}

export function roleForAgent(agentWs: string, routing: RoutingConfig): 'strong' | 'light' {
  if (routing.complex.includes(agentWs)) return 'strong'
  if (routing.executors.includes(agentWs)) return 'light'
  return routing.default_role
}

/** (قديم — محفوظ للتوافق) ترتيب بالحالة المسجلة بدون Ping. المحرك الجديد يستخدم buildPlan */
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

// ───────────────────────────── سجل الأخطاء التفصيلي ─────────────────────────────

function redact(text: string, key?: string | null): string {
  let out = text
  if (key && key.length >= 8) out = out.split(key).join('***')
  return out.replace(/(Bearer\s+)[A-Za-z0-9._\-]{12,}/gi, '$1***')
}

function prettyBody(data: unknown): string {
  if (data === undefined || data === null || data === '') return '(فارغ)'
  let s: string
  if (typeof data === 'string') {
    try {
      s = JSON.stringify(JSON.parse(data), null, 2)
    } catch {
      s = data
    }
  } else {
    try {
      s = JSON.stringify(data, null, 2)
    } catch {
      s = String(data)
    }
  }
  return s.length > 1500 ? `${s.slice(0, 1500)}… [مقتطع]` : s
}

function logProviderError(
  p: AiProvider,
  info: {
    status?: number | null
    statusText?: string
    data?: unknown
    error?: unknown
    key?: string | null
    toolsSent?: boolean
    note?: string
  },
): void {
  const err = info.error as
    | { name?: string; message?: string; cause?: { code?: string; message?: string }; response?: { data?: unknown; status?: number } }
    | undefined
  const lines: string[] = [`❌ [AI Gateway] ${p.name} (${p.model}) @ ${p.base_url}`]
  const status = info.status ?? err?.response?.status
  if (status !== undefined && status !== null) {
    lines.push(`   HTTP ${status}${info.statusText ? ` ${info.statusText}` : ''}${info.toolsSent ? '  [الطلب كان يحمل tools]' : ''}`)
  }
  if (info.note) lines.push(`   ${info.note}`)
  const data = info.data !== undefined ? info.data : err?.response?.data
  if (data !== undefined) lines.push(`   response.data: ${prettyBody(data)}`)
  if (err && (err.message || err.name)) {
    lines.push(`   error: ${err.name ?? 'Error'}: ${err.message ?? ''}`)
    if (err.cause && (err.cause.code || err.cause.message)) {
      lines.push(`   cause: ${err.cause.code ?? ''} ${err.cause.message ?? ''}`.trimEnd())
    }
  }
  console.error(redact(lines.join('\n'), info.key))
}

function parseRetryAfter(v: string | null): number | undefined {
  if (!v) return undefined
  const secs = Number(v)
  if (Number.isFinite(secs)) return Math.max(0, secs * 1000)
  const when = Date.parse(v)
  return Number.isFinite(when) ? Math.max(0, when - Date.now()) : undefined
}

// ───────────────────────────── استدعاء المزود ─────────────────────────────

type ToolCall = { id: string; type: string; function: { name: string; arguments: string } }
type CallOk = {
  ok: true
  text: string
  tool_calls?: ToolCall[]
  prompt_tokens: number
  completion_tokens: number
  model: string
}
type CallFail = { ok: false; status: number | null; body: string; kind?: ErrorKind; retryAfterMs?: number }
type CallResult = CallOk | CallFail

async function callOnce(
  p: AiProvider,
  messages: ChatMsg[],
  maxTokens: number,
  tools: unknown[] | undefined,
  timeoutMs: number,
): Promise<CallResult> {
  const key = resolveApiKey(p)
  if (!key) {
    logProviderError(p, { note: 'لا يوجد مفتاح API صالح (تحقق من env_key/.env أو api_key)' })
    return { ok: false, status: null, body: 'لا مفتاح متاح للمزود', kind: 'auth' }
  }
  const toolsSent = Array.isArray(tools) && tools.length > 0
  const ctl = new AbortController()
  const timer = setTimeout(() => ctl.abort(), timeoutMs) // مؤقت صارم: يشمل قراءة الجسم أيضاً
  try {
    const bodyPayload: Record<string, unknown> = {
      model: p.model,
      messages,
      max_tokens: maxTokens,
      temperature: 0.6,
    }
    if (toolsSent) {
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
      logProviderError(p, { status: res.status, statusText: res.statusText, data: fullText, key, toolsSent })
      return {
        ok: false,
        status: res.status,
        body: fullText.slice(0, 600),
        retryAfterMs: parseRetryAfter(res.headers.get('retry-after')),
      }
    }

    let j: {
      choices?: {
        message?: {
          content?: string
          reasoning?: string
          tool_calls?: ToolCall[]
        }
      }[]
      usage?: { prompt_tokens?: number; completion_tokens?: number }
      error?: { message?: string; code?: number | string; type?: string } | string
    }
    try {
      j = JSON.parse(fullText) as typeof j
    } catch {
      logProviderError(p, { status: res.status, data: fullText.slice(0, 500), key, note: 'رد غير JSON من المزود' })
      return { ok: false, status: res.status, body: 'رد غير JSON من المزود' }
    }

    if (j.error && !j.choices?.length) {
      const e = j.error
      const msg = typeof e === 'string' ? e : e.message ?? JSON.stringify(e)
      const code = typeof e === 'object' && e !== null && typeof e.code === 'number' ? e.code : 502
      logProviderError(p, { status: code, data: j.error, key, toolsSent, note: 'المزود أعاد HTTP 200 مع خطأ داخل الجسم' })
      return { ok: false, status: code, body: String(msg).slice(0, 600) }
    }

    const choice = j.choices?.[0]?.message
    let text = choice?.content ?? ''
    let tool_calls = choice?.tool_calls
    if (!text.trim() && choice?.reasoning) {
      text = choice.reasoning
    }
    text = text.replace(/<think>[\s\S]*?<\/think>/gi, '').trim()

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
      logProviderError(p, { status: res.status, data: fullText.slice(0, 500), key, note: 'رد بلا محتوى ولا tool_calls' })
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
    const timedOut = ctl.signal.aborted
    logProviderError(p, {
      error: e,
      key,
      toolsSent,
      note: timedOut ? `انتهت المهلة (${timeoutMs}ms)` : undefined,
    })
    const axiosData = (e as { response?: { data?: unknown } })?.response?.data
    const body = timedOut
      ? `انتهت مهلة المزود (${timeoutMs}ms)`
      : axiosData !== undefined
        ? prettyBody(axiosData).slice(0, 200)
        : e instanceof Error
          ? e.message.slice(0, 200)
          : 'شبكة'
    // المهلة عطل مستقل (قاطع الدائرة): لا يُخلط مع أخطاء الشبكة العابرة
    return { ok: false, status: null, body, kind: timedOut ? 'timeout' : 'network' }
  } finally {
    clearTimeout(timer)
  }
}

// ───────────────────────────── Tools Fallback ─────────────────────────────

const TOOL_HINT = /\btools?\b|function[_ ]?call|tool[_ ]?(use|choice|calls?)|\bfunctions?\b/i

function isToolsRejection(status: number | null, body: string): boolean {
  if (status === null) return false
  if (status === 400 || status === 422) return true
  if (status === 404 || status === 405 || status === 501) return TOOL_HINT.test(body)
  return false
}

/** deadline = سقف زمني مطلق للمحاولة الحالية (طلب الأدوات + إعادة بلا أدوات + حلقة الأدوات) */
type AttemptCtx = { toolsOff: boolean; fellBack: boolean; deadline: number }

function timeLeftFail(): CallFail {
  return { ok: false, status: null, body: 'انتهت مهلة المحاولة', kind: 'timeout' }
}

async function callProvider(
  p: AiProvider,
  msgs: ChatMsg[],
  maxTokens: number,
  tools: unknown[] | undefined,
  ctx: AttemptCtx,
  note: (provider: string, action: HandoverStep['action'], detail: string) => void,
): Promise<CallResult> {
  const wantTools = Array.isArray(tools) && tools.length > 0 && !ctx.toolsOff
  const budget1 = ctx.deadline - Date.now()
  if (budget1 < 500) return timeLeftFail()
  const first = await callOnce(p, msgs, maxTokens, wantTools ? tools : undefined, Math.min(REQUEST_TIMEOUT_MS, budget1))
  if (first.ok || !wantTools || !isToolsRejection(first.status, first.body)) return first

  console.warn(`[AI Gateway Tools Fallback] [${p.name}] (${p.model}) رفض tools (HTTP ${first.status}) → إعادة المحاولة فوراً بدون tools`)
  note(p.name, 'call', 'إعادة المحاولة بدون أدوات (Tools Fallback)')
  const budget2 = ctx.deadline - Date.now()
  if (budget2 < 500) return timeLeftFail()
  const retry = await callOnce(p, msgs, maxTokens, undefined, Math.min(REQUEST_TIMEOUT_MS, budget2))
  if (retry.ok) {
    ctx.toolsOff = true
    ctx.fellBack = true
    const fp = providerFingerprint(p)
    mutateState(p.id, (st) => {
      st.no_tools_until = new Date(Date.now() + NO_TOOLS_TTL_MS).toISOString()
      st.fp = fp
    })
  }
  return retry
}

// ───────────────────────────── المحرك الرئيسي ─────────────────────────────

export type ChatResult =
  | {
      ok: true
      text: string
      provider: { id: string; name: string; model: string }
      standby: ProviderBrief | null
      manual: boolean
      attempts: number
      handover: HandoverStep[]
      compacted: boolean
      usage: { prompt: number; completion: number }
      toolsFallback?: boolean
      /** السياق المقتطع (مهام الخلفية) — أرقام للتحقق من التوفير */
      trimmed?: { dropped: number; savedChars: number }
    }
  | {
      ok: false
      reason: string
      attempts: number
      handover: HandoverStep[]
      /** سبب النفاد: يمكّن عامل الخلفية من قرار الإرجاء بدل المحاولة الفورية */
      exhausted?: ExhaustReason
      retryAfterMs?: number
    }

export type ChatOptions = {
  maxTokens?: number
  tools?: unknown[]
  toolExecutor?: (name: string, args: Record<string, unknown>) => Promise<unknown>
  /** اختيار يدوي مطلق: يلغي Auto-Test ويجعل هذا المزود Active */
  providerId?: string
  /** مع providerId: لا انتقال لمزود آخر عند الفشل (الافتراضي false = يبقى احتياطي آلي) */
  strictProvider?: boolean
  /**
   * مهمة خلفية (عامل مجدول / نبض استباقي): يُقلَّم السياق تلقائياً —
   * تعليمات أساسية + بيانات المهمة فقط، بلا سجل دردشة ولا كتل بيانات محقونة.
   */
  background?: boolean
  onEvent?: (e: GatewayEvent) => void
  signal?: AbortSignal
}

/** أنواع أعطال يستحق معها إعادة المحاولة على نفس المزود لاحقاً ضمن الـ 5 محاولات (شبكة/5xx فقط) */
const RETRYABLE: ErrorKind[] = ['server', 'network']

/** المحرك الكامل: Active/Hot-Standby + failover (حد أقصى 5) + مهلة صارمة + auto-compact + tool calling + tools fallback */
export async function chatWithFailover(agentWs: string, messages: ChatMsg[], opts?: ChatOptions): Promise<ChatResult> {
  const startedAt = Date.now()
  const fleet = loadFleet() // قراءة حية من القرص في كل طلب
  const handover: HandoverStep[] = []
  const note = (provider: string, action: HandoverStep['action'], detail: string) => {
    handover.push({ at: new Date().toISOString(), provider, action, detail })
  }

  // (0) التقليم الذكي للسياق: مهام الخلفية تُرسل التعليمات + المهمة فقط
  let trimmed: { dropped: number; savedChars: number } | undefined
  let effectiveMessages = messages
  if (opts?.background) {
    const t = trimBackgroundMessages(messages)
    effectiveMessages = t.messages
    trimmed = { dropped: t.dropped, savedChars: t.savedChars }
    if (t.dropped > 0 || t.savedChars > 0) {
      note('gateway', 'compact', `تقليم خلفي: ${t.dropped} رسالة محذوفة، توفير ${t.savedChars} حرف`)
    }
  } else {
    trimmed = undefined
  }
  const emit = (e: GatewayEvent) => {
    try {
      opts?.onEvent?.(e)
    } catch {
      /* مستمع الأحداث لا يجوز أن يُسقط الطلب */
    }
  }

  if (fleet.providers.length === 0) {
    return {
      ok: false,
      reason: 'لا مزودين — أضفهم من أسطول الذكاء في مركز القيادة التقنية',
      attempts: 0,
      handover,
      exhausted: 'no_providers',
    }
  }

  const maxTokens = Math.max(opts?.maxTokens ?? 2048, 2048)
  let lastError = ''

  const usage = loadUsage()
  const enabledProviders = fleet.providers.filter((p) => p.enabled)
  if (enabledProviders.length === 0) {
    return {
      ok: false,
      reason: 'كل المزودين معطّلون (enabled=false) — فعّل مزوداً واحداً على الأقل',
      attempts: 0,
      handover,
      exhausted: 'no_providers',
    }
  }
  for (const p of enabledProviders) syncStateWithConfig(p, usage)

  // (1) الخطة: Auto-Test → Active + Hot Standby، أو اختيار يدوي مطلق
  const plan = await buildPlan(agentWs, fleet, usage, {
    providerId: opts?.providerId,
    strictProvider: opts?.strictProvider,
    // مهام الخلفية صبورة: لو الأسطول كله في تبريد نُرجع النفاد فوراً بدل انتظار محاولة فاشلة
    patient: !!opts?.background,
  })
  for (const n of plan.notes) note('gateway', 'call', n)
  for (const s of plan.skipped) note(s.name, 'skip', s.detail)

  if (plan.queue.length === 0) {
    return {
      ok: false,
      reason: 'جميع مزودي الذكاء الاصطناعي في فترة تبريد مؤقتة (مهلة/تجاوز حد/أعطال) — راجع أسطول الذكاء وسجل الكونسول',
      attempts: 0,
      handover,
      exhausted: 'all_cooling',
      retryAfterMs: earliestCooldownRemaining(usage, fleet.providers.filter((p) => p.enabled)),
    }
  }

  const first = plan.queue[0]
  const firstStandby = plan.queue.find((x) => x.id !== first.id) ?? null
  emit({
    type: 'plan',
    active: brief(first),
    standby: firstStandby ? brief(firstStandby) : null,
    manual: !!plan.manual,
    pinged: plan.pinged,
  })

  // طابور دوّار: الفاشل بسبب مهلة/شبكة/5xx يعود لآخر الطابور؛ الفاشل بسبب مفتاح/اختفاء/حصة/طلب معيب يُستبعد
  const rotation = [...plan.queue]
  const triedIds = new Set<string>()
  let attempt = 0

  while (attempt < MAX_ATTEMPTS && rotation.length > 0) {
    if (opts?.signal?.aborted) {
      note('gateway', 'skip', 'أُلغي الطلب من العميل')
      break
    }
    if (Date.now() - startedAt > TOTAL_BUDGET_MS) {
      note('gateway', 'skip', `توقف: تجاوز الميزانية الزمنية الكلية (${Math.round(TOTAL_BUDGET_MS / 1000)}ث)`)
      break
    }

    const p = rotation.shift()!
    attempt++
    const standby = rotation.find((x) => x.id !== p.id) ?? null
    emit({ type: 'attempt', n: attempt, max: MAX_ATTEMPTS, active: brief(p), standby: standby ? brief(standby) : null })
    if (triedIds.has(p.id)) await sleep(400) // إعادة مزود سبق فشله: تنفّس قصير
    triedIds.add(p.id)

    const fp = providerFingerprint(p)
    const st0 = stateOf(loadUsage(), p.id)
    const ctx: AttemptCtx = {
      toolsOff: !!st0.no_tools_until && Date.parse(st0.no_tools_until) > Date.now(),
      fellBack: false,
      // سقف المحاولة: مهلتان (طلب + جولة أدوات) دون تجاوز الميزانية الكلية
      deadline: Math.min(Date.now() + REQUEST_TIMEOUT_MS * 2, startedAt + TOTAL_BUDGET_MS),
    }
    if (ctx.toolsOff && opts?.tools?.length) {
      note(p.name, 'call', 'المزود لا يدعم الأدوات (محفوظ مؤقتاً) — إرسال بدون tools')
    }

    let attemptCompacted = false
    let msgs = [...effectiveMessages]
    const estPrompt = msgs.reduce((s, m) => s + estimateTokens(m.content), 0)
    if (estPrompt > (p.max_tokens || 8000) * 0.9) {
      const c = compactMessages(effectiveMessages)
      attemptCompacted = c.dropped > 0
      msgs = c.messages
      note(p.name, 'compact', `استباق Context Overflow — حُذف ${c.dropped} رسالة`)
    }

    note(p.name, 'call', `محاولة ${attempt}/${MAX_ATTEMPTS} (${p.model})`)
    let r: CallResult = await callProvider(p, msgs, maxTokens, opts?.tools, ctx, note)

    if (!r.ok && (r.kind ?? classifyFailure(r.status, r.body)) === 'overflow') {
      const c = compactMessages(effectiveMessages)
      attemptCompacted = c.dropped > 0
      msgs = c.messages
      note(p.name, 'compact', `ضُغط السجل — حُذف ${c.dropped} رسالة`)
      r = await callProvider(p, msgs, maxTokens, opts?.tools, ctx, note)
    }

    // Dynamic Tool Calling Loop
    let toolTurns = 0
    while (r.ok && r.tool_calls && r.tool_calls.length > 0 && toolTurns < 3 && opts?.toolExecutor) {
      toolTurns++
      const calls: ToolCall[] = r.tool_calls
      note(p.name, 'tool', `استدعاء أداة (${calls.map((t) => t.function.name).join(', ')})`)
      emit({ type: 'tool', provider: brief(p), tools: calls.map((t) => t.function.name) })

      msgs.push({ role: 'assistant', content: r.text || '', tool_calls: calls })

      for (const tc of calls) {
        let argsObj: Record<string, unknown> = {}
        try {
          const parsed: unknown = JSON.parse(tc.function.arguments || '{}')
          argsObj =
            parsed && typeof parsed === 'object' && !Array.isArray(parsed)
              ? (parsed as Record<string, unknown>)
              : { sql: tc.function.arguments }
        } catch {
          argsObj = { sql: tc.function.arguments }
        }
        let toolResult: unknown
        try {
          toolResult = await opts.toolExecutor(tc.function.name, argsObj)
        } catch (err) {
          console.error(`[AI Gateway] فشل تنفيذ الأداة ${tc.function.name}:`, errMsg(err))
          toolResult = { ok: false, error: `فشل تنفيذ الأداة: ${errMsg(err).slice(0, 200)}` }
        }
        msgs.push({
          role: 'tool',
          content: typeof toolResult === 'string' ? toolResult : JSON.stringify(toolResult),
          tool_call_id: tc.id,
        })
      }

      const nextTools = toolTurns >= 2 ? undefined : opts?.tools
      r = await callProvider(p, msgs, maxTokens, nextTools, ctx, note)
    }

    if (r.ok && toolTurns > 0 && !r.text.trim()) {
      r = await callProvider(p, msgs, maxTokens, undefined, ctx, note)
    }

    if (r.ok) {
      const okR = r
      mutateState(p.id, (ps) => {
        ps.status = 'up'
        ps.calls += 1
        ps.prompt_tokens += okR.prompt_tokens
        ps.completion_tokens += okR.completion_tokens
        ps.last_error = undefined
        ps.cooldown_until = undefined
        ps.cooldown_kind = undefined
        ps.fail_streak = 0
        ps.fp = fp
      })
      return {
        ok: true,
        text: okR.text,
        provider: { id: p.id, name: p.name, model: okR.model },
        standby: standby ? brief(standby) : null,
        manual: !!plan.manual && plan.manual.id === p.id,
        attempts: attempt,
        handover,
        compacted: attemptCompacted,
        usage: { prompt: okR.prompt_tokens, completion: okR.completion_tokens },
        toolsFallback: ctx.fellBack || undefined,
        trimmed,
      }
    }

    // فشل → تصنيف + قاطع دائرة (مهلة/429 = 5 دقائق) + تحويل فوري للـ Standby (المستخدم لا يرى خطأ)
    const failR = r
    const kind = failR.kind ?? classifyFailure(failR.status, failR.body)
    let appliedMs = 0
    mutateState(p.id, (ps) => {
      ps.status = 'down'
      ps.last_error = `${kind}: ${failR.body.slice(0, 160)}`
      ps.fp = fp
      const streak = (ps.fail_streak ?? 0) + 1
      const ms = cooldownFor(kind, failR.status, streak, failR.retryAfterMs)
      if (ms > 0) {
        ps.fail_streak = streak
        ps.cooldown_until = new Date(Date.now() + ms).toISOString()
        ps.cooldown_kind = kind
        if (kind === 'rate' || kind === 'timeout') ps.breaker_hits = (ps.breaker_hits ?? 0) + 1
        appliedMs = ms
      }
    })
    // نتيجة الـ Ping القديمة لم تعد صحيحة: نُنزل المزود فوراً في الترتيب القادم
    const pc = pingCache.get(p.id)
    if (pc) pingCache.set(p.id, { ...pc, ok: false, checkedAt: Date.now() })

    lastError = `${p.name}: ${kind} ${failR.status ?? ''} ${failR.body.slice(0, 80)}`.trim()
    console.warn(
      `[AI Gateway] failover من [${p.name}] (محاولة ${attempt}/${MAX_ATTEMPTS}): ${kind} HTTP ${failR.status ?? '—'} → ` +
        (appliedMs > 0
          ? kind === 'rate' || kind === 'timeout'
            ? `قاطع الدائرة: تنحية ${Math.round(appliedMs / 1000)} ثانية`
            : `تبريد ${Math.round(appliedMs / 1000)} ثانية`
          : 'بدون تبريد (خطأ خاص بالطلب)'),
    )
    note(p.name, 'fail', `${kind} ${failR.status ?? ''} ${failR.body.slice(0, 80)}`.trim())

    if (RETRYABLE.includes(kind)) rotation.push(p)

    const next = rotation[0] ?? null
    const nextStandby = next ? (rotation.find((x) => x.id !== next.id) ?? null) : null
    emit({
      type: 'failover',
      n: attempt,
      max: MAX_ATTEMPTS,
      from: brief(p),
      to: next ? brief(next) : null,
      standby: nextStandby ? brief(nextStandby) : null,
      kind,
    })
  }

  // نفاد كل المحاولات: نُبلّغ الحالة بدقة حتى يقرر عامل الخلفية الإرجاء بدل الحرق
  const finalUsage = loadUsage()
  const stillCooling = enabledProviders.filter((p) => isCooling(finalUsage, p))
  const allCooling = stillCooling.length === enabledProviders.length && enabledProviders.length > 0
  return {
    ok: false,
    reason: `جميع مزودي الذكاء الاصطناعي غير متاحين حالياً — تحقق من الاتصال${lastError ? ` (آخر خطأ: ${lastError})` : ''}`,
    attempts: attempt,
    handover,
    exhausted: allCooling ? 'all_cooling' : 'all_failed',
    retryAfterMs: earliestCooldownRemaining(finalUsage, enabledProviders) || undefined,
  }
}
