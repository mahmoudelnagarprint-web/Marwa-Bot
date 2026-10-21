// app/api/ai-fleet/route.ts — لوحة إدارة أسطول الذكاء الاصطناعي (غرفة فيجن)
// بأمر المالك 2026-10-21. تقرأ وتكتب workspaces/vision_coder/active_workspaces/ai_providers.json
// الخط الأحمر: GET لا يعيد مفتاحاً كاملاً أبداً — مقنعاً فقط؛ والملف محمي في .gitignore.
import { NextRequest, NextResponse } from 'next/server'
import {
  loadFleet, saveFleet, loadUsage, saveUsage, stateOf, maskKey, resolveApiKey,
  preflight, tokensOf, type AiProvider,
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

  if (action === 'reset_usage') {
    saveUsage({ day: new Date().toISOString().slice(0, 10), providers: {} })
    return NextResponse.json({ ok: true, message: '🔄 عداد الجلسة صفّر' })
  }

  return NextResponse.json({ ok: false, message: `إجراء غير معروف: ${action}` }, { status: 400 })
}
