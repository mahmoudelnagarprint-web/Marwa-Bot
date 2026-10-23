import { NextRequest, NextResponse } from 'next/server'
import { cairoDay } from '@/lib/agent-task-runner'
import { runSupervisorSweep, SUPERVISOR_AGENT_ID } from '@/lib/agent-task-supervisor'
import { getSupabaseAdmin } from '@/lib/supabase-admin'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'
export const maxDuration = 60

/** هل نفّذ المشرف العام مسح اليوم؟ يمنع تكرار القرارات بنفس اليوم */
async function alreadySweptToday(admin: ReturnType<typeof getSupabaseAdmin>): Promise<boolean> {
  const { data } = await admin
    .from('agent_updates')
    .select('id')
    .eq('op_id', `supervisor:${cairoDay()}`)
    .maybeSingle()
  return !!data?.id
}

/** مسح المشرف العام — قابل للتشغيل من الزر في الواجهة أو من العامل المجدول */
export async function POST(req: NextRequest) {
  let admin: ReturnType<typeof getSupabaseAdmin>
  try { admin = getSupabaseAdmin() } catch {
    return NextResponse.json({ ok: false, error: 'إعدادات Supabase الخادمية غير مكتملة' }, { status: 503 })
  }

  let body: { force?: unknown } = {}
  try { body = await req.json() as { force?: unknown } } catch { /* جسم فارغ مقبول */ }
  const force = body.force === true

  if (!force && await alreadySweptToday(admin)) {
    const { data: existing } = await admin
      .from('agent_updates')
      .select('id,title,body,created_at')
      .eq('op_id', `supervisor:${cairoDay()}`)
      .maybeSingle()
    return NextResponse.json({
      ok: true, already_ran: true, day: cairoDay(),
      supervisor: SUPERVISOR_AGENT_ID, report: existing?.body ?? null, report_id: existing?.id ?? null,
    })
  }

  try {
    const report = await runSupervisorSweep(admin)
    if (!report.ok) return NextResponse.json({ ok: false, error: report.error || 'تعذر المسح' }, { status: 503 })
    return NextResponse.json({
      ok: true,
      already_ran: false,
      day: report.day,
      supervisor: SUPERVISOR_AGENT_ID,
      scanned: report.scanned,
      decisions: report.decisions,
      decision_count: report.decisions.length,
      report_id: report.reportId,
    })
  } catch (error) {
    return NextResponse.json({
      ok: false,
      error: error instanceof Error ? error.message : 'تعذر تشغيل المشرف العام',
    }, { status: 500 })
  }
}

/** حالة المشرف العام: هل مسح اليوم؟ وكم قرار؟ */
export async function GET() {
  let admin: ReturnType<typeof getSupabaseAdmin>
  try { admin = getSupabaseAdmin() } catch {
    return NextResponse.json({ ok: false, error: 'إعدادات Supabase الخادمية غير مكتملة' }, { status: 503 })
  }
  const day = cairoDay()
  const { data } = await admin
    .from('agent_updates')
    .select('id,title,body,created_at,payload')
    .eq('op_id', `supervisor:${day}`)
    .maybeSingle()
  return NextResponse.json({
    ok: true,
    supervisor: SUPERVISOR_AGENT_ID,
    supervisor_name: 'مروة',
    day,
    swept_today: !!data?.id,
    report_id: data?.id ?? null,
    report_title: data?.title ?? null,
    report_body: data?.body ?? null,
    ran_at: data?.created_at ?? null,
  }, { headers: { 'Cache-Control': 'no-store' } })
}
