// lib/tools/google-calendar.ts — أدوات Google Calendar (جدولة مواعيد تسليم الطلبات)
// MARWA CORE task-6 — متطلبات التشغيل: نطاق https://www.googleapis.com/auth/calendar
// (راجع INTEGRATIONS_SETUP.md القسم 1)

import { z } from 'zod'
import type { ToolContext, ToolResult, ToolSpec } from './types'

const CAL_API = 'https://www.googleapis.com/calendar/v3/calendars'

// ─── المخططات ───
export const CreateEventInput = z.object({
  calendarId: z.string().default('primary').describe('معرف التقويم (الافتراضي: primary)'),
  title: z.string().min(1).describe('عنوان الحدث (مثال: تسليم أوردر #331 — وشاح تخرج)'),
  description: z.string().optional().describe('تفاصيل اختيارية (العميل، المبلغ المتبقي...)'),
  /** ISO 8601 بتوقيت القاهرة: 2026-10-25T14:00:00+02:00 */
  startIso: z.string().min(10).describe('بداية الحدث ISO مع توقيت القاهرة (+02:00)'),
  endIso: z.string().min(10).describe('نهاية الحدث ISO مع توقيت القاهرة (+02:00)'),
  remindersMinutes: z.array(z.number()).default([1440, 180]).describe('تنبيهات بالدقائق قبل الموعد (يوم + 3 ساعات افتراضياً)'),
})
export const ListUpcomingInput = z.object({
  calendarId: z.string().default('primary').describe('معرف التقويم'),
  maxResults: z.number().int().min(1).max(25).default(10).describe('أقصى عدد أحداث'),
})

export type CreateEventInputT = z.infer<typeof CreateEventInput>
export type ListUpcomingInputT = z.infer<typeof ListUpcomingInput>

// ─── التنفيذ ───
async function calFetch(path: string, token: string, init?: RequestInit): Promise<unknown> {
  const res = await fetch(`${CAL_API}${path}`, {
    ...init,
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  })
  const json = (await res.json()) as { error?: { message?: string } }
  if (!res.ok) throw new Error(`Google Calendar (${res.status}): ${json.error?.message ?? 'خطأ غير معروف'}`)
  return json
}

export async function createEvent(
  input: CreateEventInputT,
  ctx: ToolContext,
): Promise<ToolResult<{ eventId: string; htmlLink: string }>> {
  try {
    const calId = encodeURIComponent(input.calendarId || 'primary')
    const data = (await calFetch(`/${calId}/events`, ctx.accessToken, {
      method: 'POST',
      body: JSON.stringify({
        summary: input.title,
        description: input.description ?? '',
        start: { dateTime: input.startIso, timeZone: 'Africa/Cairo' },
        end: { dateTime: input.endIso, timeZone: 'Africa/Cairo' },
        reminders: {
          useDefault: false,
          overrides: input.remindersMinutes.map((m) => ({ method: 'popup', minutes: m })),
        },
      }),
    })) as { id?: string; htmlLink?: string }
    if (!data.id) return { ok: false, error: 'لم تُرجع Google معرف الحدث' }
    return { ok: true, data: { eventId: data.id, htmlLink: data.htmlLink ?? '' } }
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : String(e) }
  }
}

export async function listUpcoming(
  input: ListUpcomingInputT,
  ctx: ToolContext,
): Promise<ToolResult<{ title: string; start: string; link: string }[]>> {
  try {
    const calId = encodeURIComponent(input.calendarId || 'primary')
    const params = new URLSearchParams({
      timeMin: new Date().toISOString(),
      singleEvents: 'true',
      orderBy: 'startTime',
      maxResults: String(input.maxResults),
    })
    const data = (await calFetch(`/${calId}/events?${params}`, ctx.accessToken)) as {
      items?: { summary?: string; start?: { dateTime?: string; date?: string }; htmlLink?: string }[]
    }
    const items = (data.items ?? []).map((i) => ({
      title: i.summary ?? '(بدون عنوان)',
      start: i.start?.dateTime ?? i.start?.date ?? '',
      link: i.htmlLink ?? '',
    }))
    return { ok: true, data: items }
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : String(e) }
  }
}

export const googleCalendarSpecs: ToolSpec[] = [
  {
    name: 'google_calendar_create_event',
    description: 'جدولة موعد تسليم أو متابعة في تقويم جوجل — بتنبيهات تلقائية (يوم و3 ساعات قبل الموعد)',
    parameters: z.toJSONSchema(CreateEventInput),
  },
  {
    name: 'google_calendar_list_upcoming',
    description: 'قراءة المواعيد القادمة من تقويم جوجل (مواعيد تسليم العملاء)',
    parameters: z.toJSONSchema(ListUpcomingInput),
  },
]
