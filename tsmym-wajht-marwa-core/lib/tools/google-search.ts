// lib/tools/google-search.ts — بحث سريع عبر Google Custom Search JSON API
// MARWA CORE task-6 — متطلبات التشغيل: مفتاح API + معرف محرك البحث (cx)
//   (راجع INTEGRATIONS_SETUP.md القسم 3 — لا يحتاج OAuth، مفتاح API فقط)
// ⚠️ هذا الأداة الوحيدة بلا OAuth — تستخدم مفتاح API مباشر من البيئة (سيرفر فقط).

import { z } from 'zod'
import type { ToolResult, ToolSpec } from './types'

const SEARCH_API = 'https://www.googleapis.com/customsearch/v1'

// ─── المخططات ───
export const WebSearchInput = z.object({
  query: z.string().min(2).describe('عبارة البحث (مثال: سعر أكريليك 2.5مم مصر اليوم)'),
  num: z.number().int().min(1).max(10).default(5).describe('عدد النتائج (1-10)'),
})

export type WebSearchInputT = z.infer<typeof WebSearchInput>

export type SearchHit = { title: string; link: string; snippet: string }

// ─── التنفيذ ───
export async function webSearch(input: WebSearchInputT): Promise<ToolResult<SearchHit[]>> {
  try {
    const key = process.env.GOOGLE_SEARCH_API_KEY
    const cx = process.env.GOOGLE_SEARCH_CX
    if (!key || !cx) {
      return {
        ok: false,
        error: 'GOOGLE_SEARCH_API_KEY أو GOOGLE_SEARCH_CX غير مضبوطين — راجع INTEGRATIONS_SETUP.md القسم 3',
      }
    }
    const params = new URLSearchParams({ key, cx, q: input.query, num: String(input.num) })
    const res = await fetch(`${SEARCH_API}?${params}`)
    const json = (await res.json()) as {
      error?: { message?: string }
      items?: { title?: string; link?: string; snippet?: string }[]
    }
    if (!res.ok) throw new Error(`Google Search (${res.status}): ${json.error?.message ?? 'خطأ غير معروف'}`)
    const hits = (json.items ?? []).map((i) => ({
      title: i.title ?? '',
      link: i.link ?? '',
      snippet: (i.snippet ?? '').slice(0, 300),
    }))
    return { ok: true, data: hits }
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : String(e) }
  }
}

export const googleSearchSpecs: ToolSpec[] = [
  {
    name: 'google_search',
    description: 'بحث سريع في الويب عبر Google Custom Search — لأسعار الخامات المحدثة ومقارنة الموردين',
    parameters: z.toJSONSchema(WebSearchInput),
  },
]
