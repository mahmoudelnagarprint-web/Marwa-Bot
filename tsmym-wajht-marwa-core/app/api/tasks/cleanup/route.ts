import { NextRequest, NextResponse } from 'next/server'
import { getSupabaseAdmin } from '@/lib/supabase-admin'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'
export const maxDuration = 60

/**
 * تنظيف بيانات الاختبار من قاعدة المهام.
 * وضعان:
 *  - archive (الافتراضي، آمن): كل المهام والتقارير تُؤرشف وتُخفى من الواجهة، وسجل التدقيق يبقى.
 *  - purge (يحتاج تأكيداً صريحاً): حذف فعلي كامل — يحتاج مفتاح الخدمة، وهو المسار الوحيد المسموح له بالحذف.
 * القرار للمالك: «نبدأ على نظافة» ⇒ purge، وبدونه يبقى archive.
 */
const CONFIRM_WORD = 'امسح'

export async function POST(req: NextRequest) {
  let admin: ReturnType<typeof getSupabaseAdmin>
  try { admin = getSupabaseAdmin() } catch {
    return NextResponse.json({ ok: false, error: 'إعدادات Supabase الخادمية غير مكتملة' }, { status: 503 })
  }

  let body: { mode?: unknown; confirm?: unknown } = {}
  try { body = await req.json() as { mode?: unknown; confirm?: unknown } } catch { /* جسم فارغ = أرشيف */ }
  const mode = body.mode === 'purge' ? 'purge' : 'archive'
  const confirm = typeof body.confirm === 'string' ? body.confirm.trim() : ''

  const now = new Date().toISOString()

  // 1) المهام: أرشفة أو حذف
  if (mode === 'purge') {
    if (confirm !== CONFIRM_WORD) {
      return NextResponse.json({
        ok: false,
        error: `للحذف الفعلي اكتب كلمة التأكيد «${CONFIRM_WORD}» — بدونها سنؤرشف فقط.`,
        mode,
      }, { status: 422 })
    }
    const { error: depError } = await admin.from('agent_tasks').update({ dependency_id: null }).not('dependency_id', 'is', null)
    if (depError) return NextResponse.json({ ok: false, error: `تعذر فكّ الاعتماديات: ${depError.message}` }, { status: 503 })
    // Supabase يرفض DELETE بلا شرط WHERE — الشرط الزمني يغطي كل الصفوف ويحقق شرط الأمان
    const epoch = '1970-01-01T00:00:00.000Z'
    const { error: taskError, count: taskCount } = await admin
      .from('agent_tasks').delete({ count: 'exact' }).gte('created_at', epoch)
    if (taskError) return NextResponse.json({ ok: false, error: `تعذر حذف المهام: ${taskError.message}` }, { status: 503 })
    const { error: updError, count: updCount } = await admin
      .from('agent_updates').delete({ count: 'exact' }).gte('created_at', epoch)
    if (updError) return NextResponse.json({ ok: false, error: `تعذر حذف التقارير: ${updError.message}` }, { status: 503 })
    return NextResponse.json({
      ok: true, mode: 'purge',
      tasks_deleted: taskCount ?? 0, updates_deleted: updCount ?? 0,
      message: `تم الحذف الفعلي: ${taskCount ?? 0} مهمة و${updCount ?? 0} تقرير — القاعدة نظيفة تماماً.`,
    })
  }

  // أرشفة: المهام + التقارير القديمة (التحديثات المعلقة تُرفض حتى لا تعلق في الواجهة)
  const { error: taskError, count: taskCount } = await admin
    .from('agent_tasks')
    .update({ archived_at: now, updated_at: now }, { count: 'exact' })
    .is('archived_at', null)
  if (taskError) return NextResponse.json({ ok: false, error: `تعذر أرشفة المهام: ${taskError.message}` }, { status: 503 })

  const { error: pendingError, count: rejectedCount } = await admin
    .from('agent_updates')
    .update({ status: 'rejected', decided_by: 'mahmoud', decided_at: now }, { count: 'exact' })
    .eq('status', 'pending')
  if (pendingError) return NextResponse.json({ ok: false, error: `تعذر رفض التقارير المعلقة: ${pendingError.message}` }, { status: 503 })

  return NextResponse.json({
    ok: true, mode: 'archive',
    tasks_archived: taskCount ?? 0, updates_rejected: rejectedCount ?? 0,
    message: `تم أرشفة ${taskCount ?? 0} مهمة ورفض ${rejectedCount ?? 0} تقرير معلق — الواجهة صارت نظيفة وسجل التدقيق محفوظ.`,
  })
}

/** عدّاد ما في القاعدة الآن — يعرضه الزر قبل التنظيف */
export async function GET() {
  let admin: ReturnType<typeof getSupabaseAdmin>
  try { admin = getSupabaseAdmin() } catch {
    return NextResponse.json({ ok: false, error: 'إعدادات Supabase الخادمية غير مكتملة' }, { status: 503 })
  }
  const [tasks, activeTasks, updates, pendingUpdates] = await Promise.all([
    admin.from('agent_tasks').select('id', { count: 'exact', head: true }),
    admin.from('agent_tasks').select('id', { count: 'exact', head: true }).is('archived_at', null),
    admin.from('agent_updates').select('id', { count: 'exact', head: true }),
    admin.from('agent_updates').select('id', { count: 'exact', head: true }).eq('status', 'pending'),
  ])
  return NextResponse.json({
    ok: true,
    tasks_total: tasks.count ?? 0,
    tasks_active: activeTasks.count ?? 0,
    updates_total: updates.count ?? 0,
    updates_pending: pendingUpdates.count ?? 0,
  }, { headers: { 'Cache-Control': 'no-store' } })
}
