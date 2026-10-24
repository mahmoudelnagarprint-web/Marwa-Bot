// app/api/facebook/oversight/route.ts — دورة إشراف كاملة (بأمر المالك 2026-10-24)
// POST: يجلب منشورات وتعليقات الصفحات (indra of facebook-tools — mock/Graph حسب التهيئة)
// → لكل تعليق جديد: سلمى تولّد رداً مقترحاً (chatWithFailover — salma_crm)
// → يُسجل في facebook_interactions (بانتظار اعتماد المالك)
// → + تنبيه لحظي في agent_updates يظهر في شات سلمى فوراً (القناة القائمة).
// الحد الأقصى: 3 توليدات ردود في الدورة الواحدة (حماية تكلفة/زمن).

import { NextResponse } from 'next/server'
import { supabase, supabaseConfigured } from '@/lib/supabase'
import { chatWithFailover } from '@/lib/ai-gateway'
import { buildAgentSystemPrompt } from '@/lib/agent-intelligence'
import { fetchPagePosts, fetchPostComments, persistPost, persistInteraction, type FbComment, type FbPageName } from '@/lib/tools/facebook-tools'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'
export const maxDuration = 300

const PAGES: FbPageName[] = ['النجار برنت', 'ليان ستور']
const MAX_REPLY_GENERATIONS = 3

export async function POST() {
  const t0 = Date.now()
  if (!supabaseConfigured || !supabase) {
    return NextResponse.json({ success: false, error: 'الإعدادات السحابية غير مهيأة (.env.local)' }, { status: 500 })
  }

  const summary: {
    pagesChecked: string[]
    postsCollected: number
    commentsSeen: number
    newComments: { commenter: string; post: string; reply: string; alertId?: string }[]
    errors: string[]
  } = { pagesChecked: [], postsCollected: 0, commentsSeen: 0, newComments: [], errors: [] }

  let replyBudget = MAX_REPLY_GENERATIONS

  for (const page of PAGES) {
    try {
      const postsRes = await fetchPagePosts({ page, limit: 5 })
      if (!postsRes.ok) {
        summary.errors.push(`${page}: ${postsRes.error}`)
        continue
      }
      summary.pagesChecked.push(page)

      for (const post of postsRes.data.posts) {
        await persistPost(supabase, post)
        summary.postsCollected++

        const cmtsRes = await fetchPostComments({ postFbId: post.fbPostId, page })
        if (!cmtsRes.ok) {
          summary.errors.push(`تعليقات ${page}: ${cmtsRes.error}`)
          continue
        }
        summary.commentsSeen += cmtsRes.data.comments.length

        for (const c of cmtsRes.data.comments as FbComment[]) {
          if (replyBudget <= 0) break

          // توليد رد سلمى المقترح — LLM بسياق كامل (التعليق + المنشور + سياق الورشة)
          const userPrompt =
            `تعليق جديد على منشور فيسبوك لصفحة «${page}»:\n` +
            `• المعلق: ${c.commenterName}\n` +
            `• نص التعليق: «${c.commentText}»\n` +
            `• المنشور: «${post.message.slice(0, 200)}»\n\n` +
            `اكتب رداً مقترحاً احترافياً قصيراً (سطر إلى سطرين) باسم الصفحة — بالعامية المصرية الودودة، ` +
            `وتعاملي مع الحالة: لو سؤال سعر حوّليه لبيبو، لو مجاملة اشكريه، لو استفسار تسليم طمئنيه بموعد تقريبي.`

          const gen = await chatWithFailover(
            'salma_crm',
            [
              { role: 'system', content: buildAgentSystemPrompt('salma', userPrompt) },
              { role: 'user', content: userPrompt },
            ],
            { maxTokens: 400 },
          )

          const suggestedReply = gen.ok && gen.text?.trim() ? gen.text.trim() : null
          if (!suggestedReply) {
            summary.errors.push(`تعذر توليد رد لـ${c.commenterName}: ${gen.ok ? 'رد فارغ' : String((gen as { reason?: string }).reason ?? '')}`)
            continue
          }
          replyBudget--

          const saved = await persistInteraction(supabase, {
            pageName: page,
            comment: c,
            postPreview: post.message,
            suggestedReply,
          })
          if (saved.duplicate) continue // تعليق مُسجل سابقاً — لا إشعار مكرر
          if (!saved.ok) {
            summary.errors.push(`فشل حفظ تفاعل ${c.commenterName}`)
            continue
          }

          // تنبيه لحظي — يظهر في شات سلمى فوراً عبر قناة Realtime القائمة
          const alert = await supabase
            .from('agent_updates')
            .insert({
              agent_id: 'salma',
              kind: 'alert',
              severity: 'عالي',
              title: `💬 تعليق فيسبوك جديد من ${c.commenterName} — بانتظار اعتماد الرد`,
              body: `التعليق: «${c.commentText.slice(0, 150)}»\nالرد المقترح: «${suggestedReply.slice(0, 150)}»`,
              source: 'facebook_oversight',
            })
            .select('id')
            .limit(1)

          summary.newComments.push({
            commenter: c.commenterName,
            post: post.fbPostId,
            reply: suggestedReply.slice(0, 120),
            alertId: alert.data?.[0]?.id,
          })
        }
      }
    } catch (e) {
      summary.errors.push(`${page}: ${e instanceof Error ? e.message : String(e)}`)
    }
  }

  return NextResponse.json(
    { success: true, ...summary, ms: Date.now() - t0 },
    { headers: { 'Cache-Control': 'no-store' } },
  )
}
