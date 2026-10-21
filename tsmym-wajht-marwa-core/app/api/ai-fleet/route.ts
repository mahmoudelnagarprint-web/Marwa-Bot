// app/api/ai-fleet/route.ts — لوحة إدارة أسطول الذكاء الاصطناعي (غرفة فيجن)
// بأمر المالك 2026-10-21. تقرأ وتكتب workspaces/vision_coder/active_workspaces/ai_providers.json
// الخط الأحمر: GET لا يعيد مفتاحاً كاملاً أبداً — مقنعاً فقط؛ والملف محمي في .gitignore.
import { NextRequest, NextResponse } from 'next/server'
import {
  loadFleet, saveFleet, loadUsage, saveUsage, stateOf, maskKey, resolveApiKey,
  preflight, tokensOf, envFileValue, type AiProvider,
} from '@/lib/ai-gateway'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

function gaugeRatio(used: number, max: number): number {
  if (!max) return 0
  return Math.min(1, used / max)
}

export async function GET() {
  const fleet = loadFleet()
  const usage = loadUsage()
  const providers = fleet.providers.map((p) => {
    const st = stateOf(usage, p.id)
    const used = tokensOf(st)
    const ratio = gaugeRatio(used, p.max_tokens)
    return {
      id: p.id,
      name: p.name,
      base_url: p.base_url,
      model: p.model,
      max_tokens: p.max_tokens,
      enabled: p.enabled,
      role: p.role,
      env_key: p.env_key ?? null,
      key_masked: maskKey(p),
      has_key: Boolean(resolveApiKey(p)),
      status: st.status,
      last_error: st.last_error ?? null,
      cooldown_until: st.cooldown_until ?? null,
      usage: { prompt: st.prompt_tokens, completion: st.completion_tokens, total: used, calls: st.calls },
      gauge: {
        ratio: Math.round(ratio * 100) / 100,
        level: ratio >= 0.85 ? 'red' : ratio >= 0.6 ? 'yellow' : 'green',
      },
    }
  })
  return NextResponse.json({ ok: true, providers, routing: fleet.routing, day: usage.day })
}

export async function POST(req: NextRequest) {
  let body: Record<string, unknown>
  try {
    body = (await req.json()) as Record<string, unknown>
  } catch {
    return NextResponse.json({ ok: false, message: 'جسم الطلب غير صالح' }, { status: 400 })
  }
  const action = String(body.action ?? '')
  const fleet = loadFleet()

  if (action === 'add_provider') {
    const name = String(body.name ?? '').trim()
    const base_url = String(body.base_url ?? '').trim().replace(/\/$/, '')
    const model = String(body.model ?? '').trim()
    const max_tokens = Math.max(1000, Number(body.max_tokens ?? 8000))
    const env_key = body.env_key ? String(body.env_key).trim() : undefined
    const api_key = body.api_key ? String(body.api_key).trim() : undefined
    const role = body.role === 'light' ? 'light' : 'strong'
    if (!name || !base_url || !model || (!env_key && !api_key)) {
      return NextResponse.json({ ok: false, message: 'الاسم والـ Base URL والموديل ومفتاح (أو اسم متغير بيئة) مطلوبة' }, { status: 400 })
    }
    const p: AiProvider = {
      id: `p-${Date.now().toString(36)}`,
      name, base_url, model, max_tokens,
      api_key: env_key ? undefined : api_key,
      env_key: env_key || undefined,
      enabled: true,
      role,
      added_at: new Date().toISOString(),
    }
    fleet.providers.push(p)
    saveFleet(fleet)
    return NextResponse.json({ ok: true, message: `➕ ${name} انضم للأسطول`, id: p.id })
  }

  if (action === 'update_provider') {
    const id = String(body.id ?? '')
    const p = fleet.providers.find((x) => x.id === id)
    if (!p) return NextResponse.json({ ok: false, message: 'المزود غير موجود' }, { status: 404 })
    if (typeof body.name === 'string' && body.name.trim()) p.name = body.name.trim()
    if (typeof body.base_url === 'string' && body.base_url.trim()) p.base_url = body.base_url.trim().replace(/\/$/, '')
    if (typeof body.model === 'string' && body.model.trim()) p.model = body.model.trim()
    if (body.max_tokens !== undefined) p.max_tokens = Math.max(1000, Number(body.max_tokens))
    if (body.role === 'light' || body.role === 'strong') p.role = body.role
    if (typeof body.enabled === 'boolean') p.enabled = body.enabled
    if (typeof body.api_key === 'string' && body.api_key.trim()) { p.api_key = body.api_key.trim(); p.env_key = undefined }
    if (typeof body.env_key === 'string' && body.env_key.trim()) { p.env_key = body.env_key.trim(); p.api_key = undefined }
    saveFleet(fleet)
    return NextResponse.json({ ok: true, message: `✏️ ${p.name} اتحدث` })
  }

  if (action === 'remove_provider') {
    const id = String(body.id ?? '')
    const before = fleet.providers.length
    fleet.providers = fleet.providers.filter((p) => p.id !== id)
    if (fleet.providers.length === before) return NextResponse.json({ ok: false, message: 'المزود غير موجود' }, { status: 404 })
    saveFleet(fleet)
    return NextResponse.json({ ok: true, message: '🗑️ اتشال من الأسطول' })
  }

  if (action === 'set_routing') {
    if (Array.isArray(body.complex)) fleet.routing.complex = (body.complex as unknown[]).map(String)
    if (Array.isArray(body.executors)) fleet.routing.executors = (body.executors as unknown[]).map(String)
    if (body.default_role === 'light' || body.default_role === 'strong') fleet.routing.default_role = body.default_role
    saveFleet(fleet)
    return NextResponse.json({ ok: true, message: '🎯 التوجيه حسب الدور اتحدث' })
  }

  if (action === 'test_provider') {
    const id = String(body.id ?? '')
    const p = fleet.providers.find((x) => x.id === id)
    if (!p) return NextResponse.json({ ok: false, message: 'المزود غير موجود' }, { status: 404 })
    if (!resolveApiKey(p)) return NextResponse.json({ ok: false, message: 'لا مفتاح متاح للمزود' })
    const ping = await preflight(p)
    const usage = loadUsage()
    const st = stateOf(usage, p.id)
    st.status = ping.ok ? 'up' : 'down'
    st.last_error = ping.ok ? undefined : `preflight ${ping.status ?? 'شبكة'} ${ping.detail ?? ''}`
    usage.providers[p.id] = st
    saveUsage(usage)
    return NextResponse.json({ ok: ping.ok, message: ping.ok ? `✅ جاهز (${ping.ms}ms)` : `⚠️ لا يستجيب (${ping.status ?? 'شبكة'}) ${ping.detail ?? ''}`, detail: ping.detail ?? null })
  }

  // سحب النماذج ديناميكياً — GET /v1/models القياسية (أمر المالك 2026-10-21: إلزامي)
  // يقبل إما {id مزود محفوظ} أو {base_url + مفتاح خام} (أثناء الإضافة قبل الحفظ)
  if (action === 'list_models') {
    let base_url = ''
    let key: string | null = null
    const id = body.id !== undefined ? String(body.id) : ''
    const env_key = body.env_key ? String(body.env_key).trim() : undefined
    const api_key = body.api_key ? String(body.api_key).trim() : undefined
    if (id) {
      const p = fleet.providers.find((x) => x.id === id)
      if (!p) return NextResponse.json({ ok: false, message: 'المزود غير موجود' }, { status: 404 })
      base_url = p.base_url
      key = resolveApiKey(p)
    } else {
      base_url = String(body.base_url ?? '').trim().replace(/\/$/, '')
      key = (env_key ? process.env[env_key] || envFileValue(env_key) : api_key) ?? null
    }
    if (!base_url || !key) {
      return NextResponse.json({ ok: false, message: 'Base URL والمفتاح مطلوبان لسحب النماذج' }, { status: 400 })
    }
    try {
      const ctl = new AbortController()
      const timer = setTimeout(() => ctl.abort(), 8000)
      const res = await fetch(`${base_url}/models`, {
        headers: { Authorization: `Bearer ${key}`, 'cache-control': 'no-store' },
        cache: 'no-store',
        signal: ctl.signal,
      })
      clearTimeout(timer)
      if (!res.ok) return NextResponse.json({ ok: false, message: `المزود رفض (${res.status})` })
      const j = (await res.json()) as { data?: { id?: string }[] }
      const models = (j.data ?? []).map((m) => String(m.id ?? '')).filter(Boolean).sort()
      return NextResponse.json({ ok: true, models })
    } catch (e) {
      const cause = (e as { cause?: { code?: string } })?.cause
      return NextResponse.json({ ok: false, message: `شبكة: ${String(e).slice(0, 80)} ${cause?.code ?? ''}` })
    }
  }

  // اختبار حقيقي: رسالة Ping فعلية للنموذج المختار — تقيس سرعة الاستجابة الحقيقية
  if (action === 'ping_chat') {
    const id = String(body.id ?? '')
    const p = fleet.providers.find((x) => x.id === id)
    if (!p) return NextResponse.json({ ok: false, message: 'المزود غير موجود' }, { status: 404 })
    const key = resolveApiKey(p)
    if (!key) return NextResponse.json({ ok: false, message: 'لا مفتاح متاح للمزود' })
    const t0 = Date.now()
    try {
      const ctl = new AbortController()
      const timer = setTimeout(() => ctl.abort(), 30_000)
      const res = await fetch(`${p.base_url}/chat/completions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${key}` },
        body: JSON.stringify({
          model: p.model,
          messages: [{ role: 'user', content: 'Reply with the single word: Pong' }],
          max_tokens: 400,
          temperature: 0,
        }),
        cache: 'no-store',
        signal: ctl.signal,
      })
      clearTimeout(timer)
      const ms = Date.now() - t0
      const text = await res.text()
      if (!res.ok) {
        const st2 = stateOf(loadUsage(), p.id)
        st2.status = 'down'
        st2.last_error = `ping ${res.status} ${text.slice(0, 120)}`
        const u2 = loadUsage()
        u2.providers[p.id] = st2
        saveUsage(u2)
        return NextResponse.json({ ok: false, message: `⚠️ فشل (${res.status}): ${text.slice(0, 120)}` })
      }
      const j = JSON.parse(text) as { choices?: { message?: { content?: string } }[] }
      const reply = j.choices?.[0]?.message?.content?.trim() ?? ''
      if (!reply) return NextResponse.json({ ok: false, message: '⚠️ رد بلا محتوى — جرّب موديلاً آخر أو ارفع Max Tokens' })
      const u3 = loadUsage()
      const st3 = stateOf(u3, p.id)
      st3.status = 'up'
      st3.calls += 1
      st3.prompt_tokens += 15
      st3.completion_tokens += Math.ceil(reply.length / 3)
      u3.providers[p.id] = st3
      saveUsage(u3)
      return NextResponse.json({ ok: true, ms, reply: reply.slice(0, 120), message: `✅ رد حقيقي في ${ms}ms: «${reply.slice(0, 60)}»` })
    } catch (e) {
      return NextResponse.json({ ok: false, message: `⚠️ شبكة/مهلة: ${String(e).slice(0, 120)}` })
    }
  }

  if (action === 'reset_usage') {
    saveUsage({ day: new Date().toISOString().slice(0, 10), providers: {} })
    return NextResponse.json({ ok: true, message: '🔄 عداد الجلسة صفّر' })
  }

  return NextResponse.json({ ok: false, message: `إجراء غير معروف: ${action}` }, { status: 400 })
}
