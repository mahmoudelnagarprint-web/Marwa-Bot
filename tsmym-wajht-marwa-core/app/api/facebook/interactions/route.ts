// app/api/facebook/interactions/route.ts — قائمة التفاعلات (للوحة سلمى)
// GET: المعلقة أولاً ثم الأحدث — مع الحالة والرد المقترح.
import { NextResponse } from 'next/server'
import { supabase, supabaseConfigured } from '@/lib/supabase'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

export async function GET() {
  if (!supabaseConfigured || !supabase) {
    return NextResponse.json({ success: false, error: 'الإعدادات السحابية غير مهيأة' }, { status: 500 })
  }
  const { data, error } = await supabase
    .from('facebook_interactions')
    .select('*')
    .order('reply_status', { ascending: false }) // pending قبل sent/rejected أبجدياً... نجعل الفرز بثلاث مفاتيح:
    .limit(50)
  // فرز أدق: pending أولاً ثم الأحدث
  const sorted = (data ?? []).sort((a, b) => {
    const rank = (s: string) => (s === 'pending' ? 0 : s === 'approved' ? 1 : 2)
    const ra = rank(a.reply_status) - rank(b.reply_status)
    if (ra !== 0) return ra
    return new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  })
  return NextResponse.json({ success: true, interactions: sorted }, { headers: { 'Cache-Control': 'no-store' } })
}
