import { NextRequest, NextResponse } from 'next/server'
import { executeTaskById } from '@/lib/agent-task-runner'
import { checkDependencies } from '@/lib/agent-task-supervisor'
import { getSupabaseAdmin } from '@/lib/supabase-admin'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'
export const maxDuration = 120

/**
 * تنفيذ مهمة فوراً من الواجهة — تنفيذ حقيقي عبر النموذج، لا إغلاق صوري.
 * بوابة الاعتماديات تُفحص هنا على السيرفر قبل أي استدعاء.
 */
export async function POST(req: NextRequest) {
  let admin: ReturnType<typeof getSupabaseAdmin>
  try { admin = getSupabaseAdmin() } catch {
    return NextResponse.json({ ok: false, error: 'إعدادات Supabase الخادمية غير مكتملة' }, { status: 503 })
  }

  let body: { task_id?: unknown } = {}
  try { body = await req.json() as { task_id?: unknown } } catch {
    return NextResponse.json({ ok: false, error: 'جسم الطلب غير صالح' }, { status: 400 })
  }
  const taskId = typeof body.task_id === 'string' ? body.task_id.trim() : ''
  if (!taskId) return NextResponse.json({ ok: false, error: 'معرّف المهمة مطلوب' }, { status: 422 })

  const gate = await checkDependencies(admin, taskId)
  if (!gate.allowed) {
    return NextResponse.json({
      ok: false, blocked: true, blocked_by: gate.blockedBy, error: gate.reason,
    }, { status: 409, headers: { 'Cache-Control': 'no-store' } })
  }

  const result = await executeTaskById(admin, taskId)
  return NextResponse.json(result, {
    status: result.ok ? 200 : 502,
    headers: { 'Cache-Control': 'no-store' },
  })
}
