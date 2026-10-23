import { NextRequest, NextResponse } from 'next/server'
import { createDirectTask } from '@/lib/direct-task'
import { createClient } from '@supabase/supabase-js'
import { AGENT_MAP, enqueueInboxTask, lookupAgentKey } from '@/lib/agent-intelligence'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

type Payload = {
  text?: unknown
  agent_ids?: unknown
  agent_id?: unknown
}

type Delegated = { agent: string; name: string; taskId: string | null; error?: string }

/**
 * الإسناد المباشر من الشات الرئيسي.
 * مساران:
 *  - أمر سلاش خام: { text: "/task @salma ..." } — يبقه متوافقاً مع router_daemon.
 *  - أزرار الوكلاء (متعدد): { agent_ids: ['salma','fares'], text: "..." } — بلا تحليل سلاش.
 */
export async function POST(req: NextRequest) {
  let body: Payload
  try { body = await req.json() as Payload } catch {
    return NextResponse.json({ ok: false, message: 'جسم الطلب غير صالح.' }, { status: 400, headers: { 'Cache-Control': 'no-store' } })
  }

  const text = typeof body.text === 'string' ? body.text.trim() : ''
  const rawAgents = Array.isArray(body.agent_ids)
    ? body.agent_ids
    : typeof body.agent_id === 'string' ? [body.agent_id] : []

  // المسار الأول: شريط الأوامر الخام — سلوكه القديم كما هو
  if (!rawAgents.length) {
    if (!text || text.length > 2200) {
      return NextResponse.json({ ok: false, message: 'اكتب المهمة أولاً (حد أقصى 2200 حرف).' }, { status: 422, headers: { 'Cache-Control': 'no-store' } })
    }
    const result = await createDirectTask(text)
    return NextResponse.json(result, { status: result.ok ? 200 : 422, headers: { 'Cache-Control': 'no-store' } })
  }

  // المسار الثاني: أزرار الوكلاء — إسناد لعدة وكلاء في نفس اللحظة
  if (!text || text.length < 2) {
    return NextResponse.json({ ok: false, message: 'اكتب تفاصيل المهمة قبل اختيار الوكيل.' }, { status: 422, headers: { 'Cache-Control': 'no-store' } })
  }
  if (text.length > 2000) {
    return NextResponse.json({ ok: false, message: 'تفاصيل المهمة طويلة — حد أقصى 2000 حرف.' }, { status: 422, headers: { 'Cache-Control': 'no-store' } })
  }

  const resolved = [...new Set(rawAgents
    .filter((v): v is string => typeof v === 'string')
    .map((v) => lookupAgentKey(v))
    .filter((v): v is NonNullable<ReturnType<typeof lookupAgentKey>> => !!v))]
  if (!resolved.length) {
    return NextResponse.json({ ok: false, message: 'لم يتم اختيار أي وكيل معروف.' }, { status: 422, headers: { 'Cache-Control': 'no-store' } })
  }

  const url = process.env.NEXT_PUBLIC_SUPABASE_URL
  const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
  if (!url || !anonKey) {
    return NextResponse.json({ ok: false, message: 'إعداد Supabase غير مكتمل؛ لم تُنشأ المهام.' }, { status: 503, headers: { 'Cache-Control': 'no-store' } })
  }
  const client = createClient(url, anonKey, { auth: { persistSession: false, autoRefreshToken: false } })
  const title = text.replace(/\s+/g, ' ').slice(0, 120)
  const delegated: Delegated[] = []

  for (const agentId of resolved) {
    const { data, error } = await client.from('agent_tasks').insert({
      agent_id: agentId,
      title,
      description: text,
      status: 'pending',
      priority: 'normal',
      source: 'ui',
      created_by: 'mahmoud',
    }).select('id').single()
    const name = AGENT_MAP[agentId].name
    if (error || !data?.id) {
      delegated.push({ agent: agentId, name, taskId: null, error: error?.message || 'استجابة غير مكتملة' })
      continue
    }
    // صندوق الوارد المحلي: يبقى متاحاً حتى لو تعطل السحابة
    enqueueInboxTask({ from: 'marwa', to: agentId, type: 'task', body: text })
    delegated.push({ agent: agentId, name, taskId: data.id })
  }

  const done = delegated.filter((d) => d.taskId)
  const failed = delegated.filter((d) => !d.taskId)
  const names = done.map((d) => d.name).join('، ')
  const message = done.length
    ? failed.length
      ? `اتسجلت المهمة لـ${names} في قاعدة المهام، وتعذر الإسناد لـ${failed.map((f) => f.name).join('، ')}.`
      : `اتسجلت المهمة لـ${names} في قاعدة المهام ووصلت لصندوق الوارد.`
    : `تعذر حفظ المهام: ${failed.map((f) => `${f.name} (${f.error})`).join(' | ')}`

  return NextResponse.json({
    ok: done.length > 0,
    message,
    delegated,
    task_ids: done.map((d) => d.taskId),
  }, { status: done.length ? 200 : 503, headers: { 'Cache-Control': 'no-store' } })
}
