// app/api/facebook/interactions/decide/route.ts — قرار المالك على رد مقترح
// POST { id, action: 'approve'|'reject', editedReply? }:
//   approve → الرد على التعليق عبر أدوات فيسبوك (mock/Graph) ثم status='sent'
//             (وإن عدّل المالك الرد يُستخدم نصه المعدل) + replied_at/replied_by
//   reject  → status='rejected' (يُحفظ الرد المرفوض للتعلم — بلا حذف — قاعدة W3)
import { NextRequest, NextResponse } from 'next/server'
import { supabase, supabaseConfigured } from '@/lib/supabase'
import { replyToComment } from '@/lib/tools/facebook-tools'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

export async function POST(req: NextRequest) {
  if (!supabaseConfigured || !supabase) {
    return NextResponse.json({ success: false, error: 'الإعدادات السحابية غير مهيأة' }, { status: 500 })
  }
  try {
    const body = (await req.json()) as { id?: string; action?: string; editedReply?: string }
    const id = body.id
    const action = body.action
    if (!id || (action !== 'approve' && action !== 'reject')) {
      return NextResponse.json({ success: false, error: 'معطيات ناقصة (id + action)' }, { status: 400 })
    }

    const { data: row, error: fetchErr } = await supabase
      .from('facebook_interactions')
      .select('*')
      .eq('id', id)
      .limit(1)
      .maybeSingle()
    if (fetchErr || !row) {
      return NextResponse.json({ success: false, error: 'التفاعل غير موجود' }, { status: 404 })
    }
    if (row.reply_status !== 'pending') {
      return NextResponse.json({ success: false, error: `التفاعل حُسم مسبقاً (${row.reply_status})` }, { status: 409 })
    }

    if (action === 'reject') {
      const { error } = await supabase
        .from('facebook_interactions')
        .update({ reply_status: 'rejected', replied_by: 'mahmoud', replied_at: new Date().toISOString() })
        .eq('id', id)
      if (error) return NextResponse.json({ success: false, error: error.message }, { status: 500 })
      return NextResponse.json({ success: true, status: 'rejected' })
    }

    // اعتماد: النص المعدل إن وُجد وإلا المسودة المقترحة
    const finalReply = (body.editedReply?.trim() || row.suggested_reply || '').trim()
    if (!finalReply) {
      return NextResponse.json({ success: false, error: 'لا يوجد رد لاعتماده' }, { status: 400 })
    }

    const page = (row.page_name ?? 'النجار برنت') as 'النجار برنت' | 'ليان ستور'
    const send = await replyToComment(
      { commentFbId: row.fb_comment_id, replyText: finalReply, page },
      { accessToken: '' }, // الأداة تستخدم توكن الصفحة من البيئة داخلياً (mock حالياً)
    )
    if (!send.ok) {
      return NextResponse.json({ success: false, error: `فشل الإرسال: ${send.error}` }, { status: 502 })
    }

    const { error } = await supabase
      .from('facebook_interactions')
      .update({
        suggested_reply: finalReply, // نحفظ النسخة النهائية المعتمدة (المعدلة أو الأصلية)
        reply_status: 'sent',
        replied_at: new Date().toISOString(),
        replied_by: 'mahmoud',
        meta: { send_source: send.data.source },
      })
      .eq('id', id)
    if (error) return NextResponse.json({ success: false, error: error.message }, { status: 500 })

    return NextResponse.json({
      success: true,
      status: 'sent',
      source: send.data.source, // 'mock' الآن — 'graph' بعد إضافة توكن الصفحة
    })
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e)
    return NextResponse.json({ success: false, error: msg }, { status: 500 })
  }
}
