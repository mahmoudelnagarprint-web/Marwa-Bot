// lib/tools/google-sheets.ts — أدوات Google Sheets (إنشاء وقراءة جداول)
// MARWA CORE task-6 — هيكل Function Calling: مخططات Zod + مواصفة + تنفيذ REST v4.
// متطلبات التشغيل: OAuth بنطاق https://www.googleapis.com/auth/spreadsheets
// (راجع INTEGRATIONS_SETUP.md القسم 1)

import { z } from 'zod'
import type { ToolContext, ToolResult, ToolSpec } from './types'

const SHEETS_API = 'https://sheets.googleapis.com/v4/spreadsheets'

// ─── المخططات (Function Calling) ───
export const CreateSpreadsheetInput = z.object({
  title: z.string().min(1).describe('عنوان الجدول الجديد (مثال: تقفيلة يوم 2026-10-24)'),
  sheetName: z.string().min(1).default('الرئيسية').describe('اسم التبويب الأول'),
})
export const AppendRowsInput = z.object({
  spreadsheetId: z.string().min(10).describe('معرف الجدول من الرابط'),
  range: z.string().min(3).describe('النطاق بصيغة A1 مثل: الرئيسية!A1'),
  rows: z.array(z.array(z.union([z.string(), z.number()]))).min(1).describe('صفوف القيم — كل صف مصفوفة خلايا'),
})
export const ReadRangeInput = z.object({
  spreadsheetId: z.string().min(10).describe('معرف الجدول من الرابط'),
  range: z.string().min(3).describe('النطاق بصيغة A1 مثل: الرئيسية!A1:C10'),
})

export type CreateSpreadsheetInputT = z.infer<typeof CreateSpreadsheetInput>
export type AppendRowsInputT = z.infer<typeof AppendRowsInput>
export type ReadRangeInputT = z.infer<typeof ReadRangeInput>

// ─── التنفيذ (REST v4 — بلا مكتبات خارجية) ───
async function sheetsFetch(path: string, token: string, init?: RequestInit): Promise<unknown> {
  const res = await fetch(`${SHEETS_API}${path}`, {
    ...init,
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  })
  const json = (await res.json()) as { error?: { message?: string } }
  if (!res.ok) throw new Error(`Google Sheets (${res.status}): ${json.error?.message ?? 'خطأ غير معروف'}`)
  return json
}

export async function createSpreadsheet(
  input: CreateSpreadsheetInputT,
  ctx: ToolContext,
): Promise<ToolResult<{ spreadsheetId: string; url: string }>> {
  try {
    const data = (await sheetsFetch('', ctx.accessToken, {
      method: 'POST',
      body: JSON.stringify({ properties: { title: input.title }, sheets: [{ properties: { title: input.sheetName } }] }),
    })) as { spreadsheetId?: string; spreadsheetUrl?: string }
    if (!data.spreadsheetId) return { ok: false, error: 'لم تُرجع Google معرف الجدول' }
    return { ok: true, data: { spreadsheetId: data.spreadsheetId, url: data.spreadsheetUrl ?? '' } }
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : String(e) }
  }
}

export async function appendRows(
  input: AppendRowsInputT,
  ctx: ToolContext,
): Promise<ToolResult<{ updatedCells: number }>> {
  try {
    const data = (await sheetsFetch(
      `/${input.spreadsheetId}/values/${encodeURIComponent(input.range)}:append?valueInputOption=USER_ENTERED`,
      ctx.accessToken,
      { method: 'POST', body: JSON.stringify({ values: input.rows }) },
    )) as { updates?: { updatedCells?: number } }
    return { ok: true, data: { updatedCells: data.updates?.updatedCells ?? 0 } }
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : String(e) }
  }
}

export async function readRange(input: ReadRangeInputT, ctx: ToolContext): Promise<ToolResult<string[][]>> {
  try {
    const data = (await sheetsFetch(
      `/${input.spreadsheetId}/values/${encodeURIComponent(input.range)}`,
      ctx.accessToken,
    )) as { values?: string[][] }
    return { ok: true, data: data.values ?? [] }
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : String(e) }
  }
}

// ─── مواصفات Function Calling (تُضاف لسجل الأدوات في index.ts) ───
export const googleSheetsSpecs: ToolSpec[] = [
  {
    name: 'google_sheets_create',
    description: 'إنشاء جدول Google Sheets جديد بعنوان وتبويب محددين — يعيد المعرف والرابط',
    parameters: z.toJSONSchema(CreateSpreadsheetInput),
  },
  {
    name: 'google_sheets_append_rows',
    description: 'إضافة صفوف قيم إلى نطاق في جدول موجود (تقفيلات، مبيعات، متابعات)',
    parameters: z.toJSONSchema(AppendRowsInput),
  },
  {
    name: 'google_sheets_read_range',
    description: 'قراءة نطاق من جدول موجود وإعادة القيم كصفوف',
    parameters: z.toJSONSchema(ReadRangeInput),
  },
]
