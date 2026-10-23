import { NextRequest, NextResponse } from 'next/server'
import { createClient } from '@supabase/supabase-js'
import { AGENT_MAP, lookupAgentKey } from '@/lib/agent-intelligence'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

function parseDailySchedule(text: string) {
  const normalized = text.replace(/[٠-٩]/g, (d) => String('٠١٢٣٤٥٦٧٨٩'.indexOf(d)))
  if (!/كل\s*يوم|يومياً|يوميًا/.test(normalized) || !/اعملي|اعمل|احصر|حصر|تقرير|ملخص|راجع|تابع/.test(normalized)) return null

  const timeMatch = /(?:الساعة\s*)?(\d{1,2})(?:\s*[:.]\s*(\d{2}))?\s*(صباح|مساء|بالليل|ص|م|am|pm)(?:ً)?(?=\s|$)/i.exec(normalized)
  if (!timeMatch) return null
  let hour = Number(timeMatch[1])
  const minute = Number(timeMatch[2] || '0')
  const period = timeMatch[3].toLowerCase()
  if (hour > 12 || minute > 59 || hour < 1) return null
  const isPm = period.includes('مساء') || period.includes('بالليل') || period === 'م' || period === 'pm'
  const isAm = period.includes('صباح') || period === 'ص' || period === 'am'
  if (!isAm && !isPm) return null
  hour = hour % 12 + (isPm ? 12 : 0)
  const scheduled_time = `${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}`

  const explicitAgent = /@([\p{L}][\p{L}\p{N}_-]*)/iu.exec(normalized)?.[1]
  const inferred = explicitAgent
    ? lookupAgentKey(explicitAgent)
    : /تصنيع|خط\s*الإنتاج|ماكينة|الخامات/.test(normalized) ? lookupAgentKey('bebo')
      : /دين|تحصيل|رصيد|فاتورة|خزنة/.test(normalized) ? lookupAgentKey('fares')
        : /تسعير|تسعيرة|تكلفة/.test(normalized) ? lookupAgentKey('hakim')
          : /كود|برمج|تطبيق|ذكاء\s*اصطناعي/.test(normalized) ? lookupAgentKey('vision')
            : /جهاز|صيانة|عتاد/.test(normalized) ? lookupAgentKey('sasa')
              : /تسويق|حملة|عرض/.test(normalized) ? lookupAgentKey('koko')
                : /ابتكار|أفكار|افكار|فكرة/.test(normalized) ? lookupAgentKey('afkar')
                  : /مراقبة|تنبيه|صحة\s*النظام/.test(normalized) ? lookupAgentKey('rased')
                    : lookupAgentKey('salma')
  if (!inferred || !AGENT_MAP[inferred]) return null

  const title = normalized
    .replace(/@[\p{L}][\p{L}\p{N}_-]*/igu, '')
    .replace(/كل\s*يوم|يومياً|يوميًا/ig, '')
    .replace(/(?:الساعة\s*)?\d{1,2}(?:\s*[:.]\s*\d{2})?\s*(?:صباح|مساء|بالليل|ص|م|am|pm)(?:ً)?(?=\s|$)/ig, '')
    .replace(/اعملي|اعمل/ig, '')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 160) || 'مهمة يومية مجدولة'

  return {
    title,
    description: `مهمة دورية يومية من طلب المالك: ${text.trim().slice(0, 500)}`,
    agent_id: inferred,
    source: 'marwa',
    priority: 'normal',
    status: 'pending',
    schedule_type: 'daily',
    scheduled_time,
    schedule_timezone: 'Africa/Cairo',
  }
}

export async function POST(req: NextRequest) {
  let body: { text?: unknown }
  try { body = await req.json() as { text?: unknown } } catch {
    return NextResponse.json({ ok: false, error: 'جسم الطلب غير صالح' }, { status: 400 })
  }
  const text = typeof body.text === 'string' ? body.text.trim() : ''
  const task = parseDailySchedule(text)
  if (!task) return NextResponse.json({ ok: true, scheduled: false })

  const url = process.env.NEXT_PUBLIC_SUPABASE_URL
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
  if (!url || !key) return NextResponse.json({ ok: false, error: 'إعداد Supabase غير مكتمل' }, { status: 503 })

  const client = createClient(url, key, { auth: { persistSession: false, autoRefreshToken: false } })
  const { data, error } = await client.from('agent_tasks').insert(task)
    .select('id,title,agent_id,scheduled_time,schedule_timezone').single()
  if (error) {
    const migrationRequired = error.message.includes('schedule_type') || error.message.includes('scheduled_time')
    return NextResponse.json({ ok: false, error: migrationRequired ? 'يلزم تطبيق الترحيل 007 على Supabase لتفعيل الجدولة.' : error.message }, { status: 503 })
  }
  return NextResponse.json({ ok: true, scheduled: true, task })
}
