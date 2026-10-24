// lib/tools/index.ts — سجل أدوات الوكلاء الخارجية (Function Calling Registry)
// MARWA CORE task-6: يُصدَّر من هنا إلى بوابة الذكاء (ai-gateway) بصيغة tools[]
// عندما يأتي أمر المالك بتفعيل الاستدعاء — نفس نمط POS_DB_TOOLS الحالي.
//
// ⚠️ الترتيب التنفيذي (بأمر المالك):
//   1) اربط حساباتك من الإعدادات (أزرار Connect — تكتب في خزنة السيرفر المشفرة)
//   2) فعّل حقل tools في استدعاء chatWithFailover وأضف executeToolTool هنا
//   3) النماذج (GLM/DeepSeek) تستدعي الأدوات بأسمائها ويُنفذها السيرفر برموز صالحة

import { googleSheetsSpecs } from './google-sheets'
import { googleCalendarSpecs } from './google-calendar'
import { canvaSpecs } from './canva-api'
import { googleSearchSpecs } from './google-search'
import type { ToolSpec } from './types'

/** كل مواصفات الأدوات الخارجية — تُصدر لبوابة النماذج عند تفعيل Function Calling */
export const EXTERNAL_TOOL_SPECS: ToolSpec[] = [
  ...googleSheetsSpecs,
  ...googleCalendarSpecs,
  ...canvaSpecs,
  ...googleSearchSpecs,
]

/** تنفيذ أداة بالاسم (يُربط بمنفذ الأدوات في ai-gateway عند التفعيل) */
export async function executeExternalTool(
  name: string,
  rawInput: unknown,
  getAccessToken: (provider: 'google' | 'canva') => Promise<string>,
): Promise<unknown> {
  const { getValidAccessToken } = await import('./tokens')
  switch (name) {
    case 'google_sheets_create': {
      const { createSpreadsheet } = await import('./google-sheets')
      const { CreateSpreadsheetInput } = await import('./google-sheets')
      const input = CreateSpreadsheetInput.parse(rawInput)
      return createSpreadsheet(input, { accessToken: await getValidAccessToken('google') })
    }
    case 'google_sheets_append_rows': {
      const { appendRows, AppendRowsInput } = await import('./google-sheets')
      const input = AppendRowsInput.parse(rawInput)
      return appendRows(input, { accessToken: await getValidAccessToken('google') })
    }
    case 'google_sheets_read_range': {
      const { readRange, ReadRangeInput } = await import('./google-sheets')
      const input = ReadRangeInput.parse(rawInput)
      return readRange(input, { accessToken: await getValidAccessToken('google') })
    }
    case 'google_calendar_create_event': {
      const { createEvent, CreateEventInput } = await import('./google-calendar')
      const input = CreateEventInput.parse(rawInput)
      return createEvent(input, { accessToken: await getValidAccessToken('google') })
    }
    case 'google_calendar_list_upcoming': {
      const { listUpcoming, ListUpcomingInput } = await import('./google-calendar')
      const input = ListUpcomingInput.parse(rawInput)
      return listUpcoming(input, { accessToken: await getValidAccessToken('google') })
    }
    case 'canva_create_from_template': {
      const { createFromTemplate, CreateFromTemplateInput } = await import('./canva-api')
      const input = CreateFromTemplateInput.parse(rawInput)
      return createFromTemplate(input, { accessToken: await getValidAccessToken('canva') })
    }
    case 'canva_export_design': {
      const { exportDesign, ExportDesignInput } = await import('./canva-api')
      const input = ExportDesignInput.parse(rawInput)
      return exportDesign(input, { accessToken: await getValidAccessToken('canva') })
    }
    case 'google_search': {
      const { webSearch, WebSearchInput } = await import('./google-search')
      const input = WebSearchInput.parse(rawInput)
      return webSearch(input)
    }
    default:
      return { ok: false, error: `أداة خارجية غير معروفة: ${name}` }
  }
}

export { getValidAccessToken, getStatus, clearTokens } from './tokens'
export type { IntegrationStatus } from './tokens'
