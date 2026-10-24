// app/api/facebook/report/route.ts — تقارير السوشيال ميديا الدورية (كوكو)
// GET  : قائمة التقارير المحفوظة (الأحدث أولاً)
// POST : توليد تقرير جديد — يجلب المنشورات عبر أدوات فيسبوك → يبني المقاييس →
//        كوكو (koko_marketing) يحلل ويكتب التحليل والمقترحات بالعربي → يُحفظ في
//        social_reports ويُعرض في تاب «تقارير السوشيال ميديا» بغرفة كوكو.

import { NextResponse } from 'next/server'
import { supabase, supabaseConfigured } from '@/lib/supabase'
import { chatWithFailover } from '@/lib/ai-gateway'
import { buildAgentSystemPrompt } from '@/lib/agent-intelligence'
import { fetchPagePosts, type FbPost } from '@/lib/tools/facebook-tools'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'
export const maxDuration = 300

export async function GET() {
  if (!supabaseConfigured || !supabase) {
    return NextResponse.json({ success: false, error: 'الإعدادات السحابية غير مهيأة' }, { status: 500 })
  }
  const { data, error } = await supabase
    .from('social_reports')
    .select('*')
    .order('created_at', { ascending: false })
    .limit(10)
  if (error) return NextResponse.json({ success: false, error: error.message }, { status: 500 })
  return NextResponse.json({ success: true, reports: data ?? [] }, { headers: { 'Cache-Control': 'no-store' } })
}

function engagement(p: FbPost): number {
  return p.likes + p.commentsCount * 3 + p.shares * 2 // وزن التعليق أعلى (تفاعل حقيقي)
}

export async function POST() {
  const t0 = Date.now()
  if (!supabaseConfigured || !supabase) {
    return NextResponse.json({ success: false, error: 'الإعدادات السحابية غير مهيأة' }, { status: 500 })
  }

  try {
    // 1) جمع المنشورات من الصفحتين
    const allPosts: (FbPost & { engagement: number })[] = []
    for (const page of ['النجار برنت', 'ليان ستور'] as const) {
      const res = await fetchPagePosts({ page, limit: 8 })
      if (res.ok) {
        for (const p of res.data.posts) allPosts.push({ ...p, engagement: engagement(p) })
      }
    }
    if (allPosts.length === 0) {
      return NextResponse.json({ success: false, error: 'لا توجد منشورات لتحليلها بعد' }, { status: 422 })
    }

    // 2) المقاييس المحسوبة من البرنامج (لا اختراع)
    const totalLikes = allPosts.reduce((s, p) => s + p.likes, 0)
    const totalComments = allPosts.reduce((s, p) => s + p.commentsCount, 0)
    const totalShares = allPosts.reduce((s, p) => s + p.shares, 0)
    const best = [...allPosts].sort((a, b) => b.engagement - a.engagement).slice(0, 3)
    const periodLabel = `مراجعة ${new Date().toLocaleDateString('ar-EG', { day: '2-digit', month: 'long' })}`

    // 3) كوكو يحلل ويكتب — البيانات الحية حقنت له في البرومبت
    const dataForKoko =
      `بيانات آخر ${allPosts.length} منشور (مصدر: أدوات فيسبوك — ${allPosts[0].page === 'النجار برنت' ? 'mock/حية' : 'mock/حية'}):\n` +
      allPosts.map((p) => `• [${p.page}] «${p.message.slice(0, 80)}» — لايكات ${p.likes} • تعليقات ${p.commentsCount} • مشاركات ${p.shares}`).join('\n') +
      `\nأعلى 3 تفاعلاً: ${best.map((b) => `«${b.message.slice(0, 50)}» (تفاعل ${b.engagement})`).join(' • ')}\n` +
      `الإجماليات: لايكات ${totalLikes} • تعليقات ${totalComments} • مشاركات ${totalShares}`

    const sys = buildAgentSystemPrompt('koko', dataForKoko)
    const gen = await chatWithFailover(
      'koko_marketing',
      [
        { role: 'system', content: sys },
        {
          role: 'user',
          content:
            'اكتب تقرير أداء السوشيال ميديا الدوري (بالعربي المصري، بنقطتين منفصلتين بسطر فارغ):\n' +
            '1) سطر «التحليل المبدئي:» — 2-3 نقاط عن أفضل الأداء ولماذا (اربط بالنشاط التجاري).\n' +
            '2) سطر «مقترحات الحملة القادمة:» — 2-3 اقتراحات تنفيذية محددة.\n' +
            'استخدم الأرقام المعطاة فقط ولا تخترع أرقاماً.',
        },
      ],
      { maxTokens: 900 },
    )
    const rawText = gen.ok && gen.text ? gen.text.trim() : ''
    if (!rawText) {
      return NextResponse.json(
        { success: false, error: `تعذر توليد التقرير: ${String((gen as { reason?: string }).reason ?? 'رد فارغ')}` },
        { status: 502 },
      )
    }

    // فصل التحليل عن المقترحات من نص النموذج (المحدد بنقطتي البداية)
    const analysisMatch = rawText.match(/التحليل المبدئي:?([\s\S]*?)(?=مقترحات الحملة|$)/i)
    const suggestMatch = rawText.match(/مقترحات الحملة القادمة:?([\s\S]*)/i)
    const analysis = (analysisMatch?.[1] ?? rawText).trim()
    const suggestions = (suggestMatch?.[1] ?? '—').trim()

    const metrics = {
      total_posts: allPosts.length,
      total_likes: totalLikes,
      total_comments: totalComments,
      total_shares: totalShares,
      window: 'آخر 8 منشورات لكل صفحة',
    }
    const bestPosts = best.map((b) => ({
      page: b.page,
      message: b.message.slice(0, 120),
      likes: b.likes,
      comments: b.commentsCount,
      shares: b.shares,
      engagement: b.engagement,
      fbPostId: b.fbPostId,
    }))

    // 4) الحفظ في social_reports
    const saved = await supabase
      .from('social_reports')
      .insert({ agent_id: 'koko', period_label: periodLabel, metrics, best_posts: bestPosts, analysis, suggestions })
      .select('id')
      .limit(1)

    return NextResponse.json(
      {
        success: true,
        report: { id: saved.data?.[0]?.id ?? null, periodLabel, metrics, bestPosts, analysis, suggestions, rawText },
        ms: Date.now() - t0,
      },
      { headers: { 'Cache-Control': 'no-store' } },
    )
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e)
    return NextResponse.json({ success: false, error: msg, ms: Date.now() - t0 }, { status: 500 })
  }
}
