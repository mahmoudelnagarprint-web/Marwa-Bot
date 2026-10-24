// lib/tools/facebook-tools.ts — أدوات فيسبوك لصفحات النشاط التجاري (النجار برنت / وليان ستور)
// MARWA CORE task-7 — «الذكاء التفاعلي مع السوشيال ميديا» (أمر المالك 2026-10-24).
//
// 🔌 نمط التشغيل المزدوج (Seam):
//   - بدون FB_PAGE_ACCESS_TOKEN + FB_PAGE_ID في البيئة → وضع Mock موسوم بوضوح
//     (بيانات واقعية للاختبار وبناء الواجهة — بلا أي ادعاء أنه بيانات حية).
//   - بمجرد إضافة الرمزين → نفس الدوال تتحول تلقائياً لـGraph API الحقيقي (v21.0)
//     بلا أي تغيير في باقي المنظومة.
// ⚠️ الصلاحيات المطلوبة للوضع الحقيقي: pages_show_list, pages_read_engagement,
//    pages_manage_posts, pages_read_user_content (راجع INTEGRATIONS_SETUP.md لاحقاً).

import { z } from 'zod'
import type { SupabaseClient } from '@supabase/supabase-js'
import type { ToolContext, ToolResult, ToolSpec } from './types'

const GRAPH = 'https://graph.facebook.com/v21.0'

export type FbSource = 'mock' | 'graph'
export type FbPageName = 'النجار برنت' | 'ليان ستور'

// ─── المخططات (Function Calling) ───
export const FetchPagePostsInput = z.object({
  page: z.enum(['النجار برنت', 'ليان ستور']).describe('الصفحة المستهدفة'),
  limit: z.number().int().min(1).max(10).default(5).describe('أقصى عدد منشورات'),
})
export const FetchPostCommentsInput = z.object({
  postFbId: z.string().min(3).describe('معرف المنشور في فيسبوك'),
  page: z.enum(['النجار برنت', 'ليان ستور']).describe('الصفحة'),
})
export const ReplyToCommentInput = z.object({
  commentFbId: z.string().min(3).describe('معرف التعليق المراد الرد عليه'),
  replyText: z.string().min(1).describe('نص الرد المعتمد من المالك'),
  page: z.enum(['النجار برنت', 'ليان ستور']).describe('الصفحة'),
})
export const PublishPostInput = z.object({
  page: z.enum(['النجار برنت', 'ليان ستور']).describe('الصفحة'),
  message: z.string().min(5).describe('نص المنشور (يُلحق به التوقيع الرسمي)'),
  link: z.string().optional().describe('رابط اختياري يُرفق بالمنشور'),
})

export type FetchPagePostsInputT = z.infer<typeof FetchPagePostsInput>
export type FetchPostCommentsInputT = z.infer<typeof FetchPostCommentsInput>
export type ReplyToCommentInputT = z.infer<typeof ReplyToCommentInput>
export type PublishPostInputT = z.infer<typeof PublishPostInput>

// ─── الأنواع ───
export type FbPost = {
  fbPostId: string
  page: FbPageName
  message: string
  publishedAt: string
  likes: number
  commentsCount: number
  shares: number
  permalink: string
}

export type FbComment = {
  fbCommentId: string
  postFbId: string
  commenterName: string
  commentText: string
  createdAt: string
}

// ─── البيانات التجريبية (وضع Mock — موسومة بوضوح) ───
const MOCK_POSTS: FbPost[] = [
  {
    fbPostId: 'mock_post_101',
    page: 'النجار برنت',
    message: '🎁 بوكس الهدايا: مج ديجيتال + محفظة بالاسم + نوتبوك — هدية من قلبك باسمه!',
    publishedAt: '2026-10-22T18:30:00+02:00',
    likes: 87,
    commentsCount: 12,
    shares: 9,
    permalink: 'https://facebook.com/mock/101',
  },
  {
    fbPostId: 'mock_post_102',
    page: 'النجار برنت',
    message: '✨ تابلوهات خشب بأسمائكم — قص ليزر دقيق وتغليف فاخر.',
    publishedAt: '2026-10-21T20:00:00+02:00',
    likes: 54,
    commentsCount: 7,
    shares: 3,
    permalink: 'https://facebook.com/mock/102',
  },
  {
    fbPostId: 'mock_post_103',
    page: 'ليان ستور',
    message: '👗 وصل جديد كوليكشن الشتاء — القطع محدودة!',
    publishedAt: '2026-10-20T19:00:00+02:00',
    likes: 132,
    commentsCount: 21,
    shares: 14,
    permalink: 'https://facebook.com/mock/103',
  },
]

const MOCK_COMMENTS: Record<string, FbComment[]> = {
  mock_post_101: [
    {
      fbCommentId: 'mock_cmt_1',
      postFbId: 'mock_post_101',
      commenterName: 'أم يوسف',
      commentText: 'السعر كام يا ادارة؟ وفيه تسليم لأسوان؟',
      createdAt: '2026-10-23T21:10:00+02:00',
    },
    {
      fbCommentId: 'mock_cmt_2',
      postFbId: 'mock_post_101',
      commenterName: 'محمود عبد الله',
      commentText: 'تحفة يا جماعة، شغل نظيف جداً 👏',
      createdAt: '2026-10-23T22:40:00+02:00',
    },
  ],
  mock_post_103: [
    {
      fbCommentId: 'mock_cmt_3',
      postFbId: 'mock_post_103',
      commenterName: 'هدى',
      commentText: 'المقاسات المتاحة إيه؟ وممكن تشوفوه قبل الشراء؟',
      createdAt: '2026-10-23T23:05:00+02:00',
    },
  ],
}

// ─── الوضع الحقيقي (Graph API) ───
function realApiConfigured(): boolean {
  return Boolean(process.env.FB_PAGE_ACCESS_TOKEN && process.env.FB_PAGE_ID)
}

async function graphGet(path: string, params: Record<string, string>): Promise<unknown> {
  const qs = new URLSearchParams({ ...params, access_token: process.env.FB_PAGE_ACCESS_TOKEN ?? '' })
  const res = await fetch(`${GRAPH}/${path}?${qs}`)
  const json = (await res.json()) as { error?: { message?: string }; data?: unknown }
  if (!res.ok) throw new Error(`Graph API (${res.status}): ${json.error?.message ?? 'خطأ'}`)
  return json
}

async function graphPost(path: string, body: Record<string, string>): Promise<unknown> {
  const res = await fetch(`${GRAPH}/${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...body, access_token: process.env.FB_PAGE_ACCESS_TOKEN ?? '' }),
  })
  const json = (await res.json()) as { error?: { message?: string }; id?: string }
  if (!res.ok) throw new Error(`Graph API (${res.status}): ${json.error?.message ?? 'خطأ'}`)
  return json
}

// ─── الأدوات الأربع ───

/** جلب منشورات الصفحة مع مقاييس التفاعل (mock أو Graph حسب التهيئة) */
export async function fetchPagePosts(input: FetchPagePostsInputT): Promise<
  ToolResult<{ source: FbSource; posts: FbPost[] }>
> {
  if (!realApiConfigured()) {
    const posts = MOCK_POSTS.filter((p) => p.page === input.page).slice(0, input.limit)
    return { ok: true, data: { source: 'mock', posts } }
  }
  try {
    const pageId = input.page === 'ليان ستور' ? process.env.FB_PAGE_ID_LIAN ?? process.env.FB_PAGE_ID : process.env.FB_PAGE_ID
    const data = (await graphGet(`${pageId}/posts`, {
      fields: 'message,created_time,likes.summary(true),comments.summary(true),shares,permalink_url',
      limit: String(input.limit),
    })) as {
      data?: { id: string; message?: string; created_time?: string; likes?: { summary?: { total_count?: number } }; comments?: { summary?: { total_count?: number } }; shares?: { count?: number }; permalink_url?: string }[]
    }
    const posts = (data.data ?? []).map((p) => ({
      fbPostId: p.id,
      page: input.page,
      message: p.message ?? '',
      publishedAt: p.created_time ?? '',
      likes: p.likes?.summary?.total_count ?? 0,
      commentsCount: p.comments?.summary?.total_count ?? 0,
      shares: p.shares?.count ?? 0,
      permalink: p.permalink_url ?? '',
    }))
    return { ok: true, data: { source: 'graph', posts } }
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : String(e) }
  }
}

/** جلب تعليقات منشور (mock أو Graph حسب التهيئة) */
export async function fetchPostComments(
  input: FetchPostCommentsInputT,
): Promise<ToolResult<{ source: FbSource; comments: FbComment[] }>> {
  if (!realApiConfigured()) {
    return { ok: true, data: { source: 'mock', comments: MOCK_COMMENTS[input.postFbId] ?? [] } }
  }
  try {
    const data = (await graphGet(`${input.postFbId}/comments`, {
      fields: 'from{name},message,created_time',
      limit: '50',
    })) as { data?: { id: string; from?: { name?: string }; message?: string; created_time?: string }[] }
    const comments = (data.data ?? []).map((c) => ({
      fbCommentId: c.id,
      postFbId: input.postFbId,
      commenterName: c.from?.name ?? 'مستخدم فيسبوك',
      commentText: c.message ?? '',
      createdAt: c.created_time ?? '',
    }))
    return { ok: true, data: { source: 'graph', comments } }
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : String(e) }
  }
}

/** الرد على تعليق — يتطلب توكن صفحة حقيقي؛ في وضع Mock يعيد نجاحاً موسوماً */
export async function replyToComment(
  input: ReplyToCommentInputT,
  ctx: ToolContext, // محجوز — الرد يستخدم توكن الصفحة من البيئة (موحد للصفحتين حالياً)
): Promise<ToolResult<{ repliedId: string; source: FbSource }>> {
  if (!realApiConfigured()) {
    return { ok: true, data: { repliedId: `mock_reply_${Date.now()}`, source: 'mock' } }
  }
  try {
    const data = (await graphPost(`${input.commentFbId}/comments`, { message: input.replyText })) as { id?: string }
    return { ok: true, data: { repliedId: data.id ?? '', source: 'graph' } }
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : String(e) }
  }
}

/** نشر منشور جديد على الصفحة (يُلحق التوقيع الرسمي في طبقة أعلى — قاعدة كوكو) */
export async function publishPost(
  input: PublishPostInputT,
  ctx: ToolContext,
): Promise<ToolResult<{ postId: string; source: FbSource }>> {
  if (!realApiConfigured()) {
    return { ok: true, data: { postId: `mock_post_${Date.now()}`, source: 'mock' } }
  }
  try {
    const pageId = input.page === 'ليان ستور' ? process.env.FB_PAGE_ID_LIAN ?? process.env.FB_PAGE_ID : process.env.FB_PAGE_ID
    const body: Record<string, string> = { message: input.message }
    if (input.link) body.link = input.link
    const data = (await graphPost(`${pageId}/feed`, body)) as { id?: string }
    return { ok: true, data: { postId: data.id ?? '', source: 'graph' } }
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : String(e) }
  }
}

// ─── التخزين السحابي (facebook_posts / facebook_interactions / social_reports) ───

/** حفظ/تحديث منشور في جدول facebook_posts (upsert على fb_post_id) */
export async function persistPost(supabase: SupabaseClient, post: FbPost): Promise<void> {
  await supabase.from('facebook_posts').upsert(
    {
      page_name: post.page,
      fb_post_id: post.fbPostId,
      message: post.message,
      published_at: post.publishedAt || null,
      likes: post.likes,
      comments_count: post.commentsCount,
      shares: post.shares,
      permalink: post.permalink,
    },
    { onConflict: 'fb_post_id' },
  )
}

export type FbInteractionRow = {
  id: string
  page_name: string
  fb_comment_id: string
  post_fb_id: string | null
  post_preview: string | null
  commenter_name: string
  comment_text: string
  suggested_reply: string | null
  reply_status: 'pending' | 'approved' | 'sent' | 'rejected' | 'skipped'
  replied_at: string | null
  created_at: string
}

/** تسجيل تعليق جديد مع الرد المقترح — ينتظر قرار المالك (اعتماد/تعديل/رفض) */
export async function persistInteraction(
  supabase: SupabaseClient,
  row: {
    pageName: FbPageName
    comment: FbComment
    postPreview: string
    suggestedReply: string
  },
): Promise<{ ok: boolean; id?: string; duplicate?: boolean }> {
  const { data, error } = await supabase
    .from('facebook_interactions')
    .insert({
      page_name: row.pageName,
      fb_comment_id: row.comment.fbCommentId,
      post_fb_id: row.comment.postFbId,
      post_preview: row.postPreview.slice(0, 200),
      commenter_name: row.comment.commenterName,
      comment_text: row.comment.commentText,
      comment_created_at: row.comment.createdAt || null,
      suggested_reply: row.suggestedReply,
      reply_status: 'pending',
    })
    .select('id')
    .limit(1)
  if (error) {
    const m = `${error.message} ${error.code ?? ''}`
    if (m.includes('duplicate key') || m.includes('23505')) return { ok: true, duplicate: true }
    return { ok: false }
  }
  return { ok: true, id: data?.[0]?.id }
}

/** حفظ تقرير كوكو الدوري */
export async function persistSocialReport(
  supabase: SupabaseClient,
  report: { periodLabel: string; metrics: Record<string, unknown>; bestPosts: unknown[]; analysis: string; suggestions: string },
): Promise<{ ok: boolean; id?: string }> {
  const { data, error } = await supabase
    .from('social_reports')
    .insert({
      agent_id: 'koko',
      period_label: report.periodLabel,
      metrics: report.metrics,
      best_posts: report.bestPosts,
      analysis: report.analysis,
      suggestions: report.suggestions,
    })
    .select('id')
    .limit(1)
  if (error) return { ok: false }
  return { ok: true, id: data?.[0]?.id }
}

// ─── مواصفات Function Calling ───
export const facebookSpecs: ToolSpec[] = [
  {
    name: 'facebook_fetch_page_posts',
    description: 'جلب آخر منشورات صفحة فيسبوك مع مقاييس التفاعل (لايكات/تعليقات/مشاركة/وصول)',
    parameters: z.toJSONSchema(FetchPagePostsInput),
  },
  {
    name: 'facebook_fetch_post_comments',
    description: 'جلب تعليقات منشور محدد لتحليلها وتجهيز الردود',
    parameters: z.toJSONSchema(FetchPostCommentsInput),
  },
  {
    name: 'facebook_reply_to_comment',
    description: 'الرد على تعليق — يُنفَّذ فقط بعد اعتماد المالك للرد المقترح',
    parameters: z.toJSONSchema(ReplyToCommentInput),
  },
  {
    name: 'facebook_publish_post',
    description: 'نشر منشور جديد على الصفحة — يُنفَّذ فقط بأمر المالك الصريح',
    parameters: z.toJSONSchema(PublishPostInput),
  },
]
