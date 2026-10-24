// lib/tools/canva-api.ts — أدوات Canva Connect (توليد تصميمات من القوالب وتصديرها)
// MARWA CORE task-6 — متطلبات التشغيل: تطبيق Canva Developer + نطاقات
//   design:content:write • design:content:read • asset:write (راجع INTEGRATIONS_SETUP.md القسم 2)
// ملاحظة واجهة Canva: المصادقة OAuth 2.0 + PKCE — الأداة تستقبل accessToken جاهزاً
// من طبقة الخزنة (tokens.ts) ولا تعرف شيئاً عن التخزين.

import { z } from 'zod'
import type { ToolContext, ToolResult, ToolSpec } from './types'

const CANVA_API = 'https://api.canva.com/rest/v1'

// ─── المخططات ───
export const CreateFromTemplateInput = z.object({
  templateId: z.string().min(5).describe('معرف القالب من Canva (design id)'),
  title: z.string().min(1).describe('عنوان التصميم الجديد'),
  /** حقول النص المراد تعديلها داخل القالب: اسم الحقل → النص الجديد */
  replacements: z.record(z.string(), z.string()).optional().describe('استبدالات نصية اختيارية: {اسم العنصر: النص}'),
})
export const ExportDesignInput = z.object({
  designId: z.string().min(5).describe('معرف التصميم'),
  format: z.enum(['png', 'pdf', 'jpg']).default('png').describe('صيغة التصدير'),
})

export type CreateFromTemplateInputT = z.infer<typeof CreateFromTemplateInput>
export type ExportDesignInputT = z.infer<typeof ExportDesignInput>

// ─── التنفيذ ───
async function canvaFetch(path: string, token: string, init?: RequestInit): Promise<unknown> {
  const res = await fetch(`${CANVA_API}${path}`, {
    ...init,
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  })
  const json = (await res.json().catch(() => ({}))) as { message?: string; job?: { id?: string; status?: string } }
  if (!res.ok) throw new Error(`Canva (${res.status}): ${json.message ?? 'خطأ غير معروف'}`)
  return json
}

/** إنشاء تصميم من قالب — يعيد معرف التصميم ورابط التحرير */
export async function createFromTemplate(
  input: CreateFromTemplateInputT,
  ctx: ToolContext,
): Promise<ToolResult<{ designId: string; editUrl: string }>> {
  try {
    const data = (await canvaFetch('/designs', ctx.accessToken, {
      method: 'POST',
      body: JSON.stringify({
        design_template: { id: input.templateId },
        title: input.title,
        // ملاحظة: تعديل عناصر القالب (replacements) يتم بعد الإنشاء عبر
        // autofill API — الواجهة الكاملة تُستكمل عند ربط الحساب الفعلي (مرحلة 2).
      }),
    })) as { design?: { id?: string; urls?: { edit_url?: string } } }
    const id = data.design?.id
    if (!id) return { ok: false, error: 'لم تُرجع Canva معرف التصميم' }
    return { ok: true, data: { designId: id, editUrl: data.design?.urls?.edit_url ?? '' } }
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : String(e) }
  }
}

/** تصدير تصميم — يعيد رابط تحميل مؤقت (تنتهي صلاحية الروابط سريعاً) */
export async function exportDesign(
  input: ExportDesignInputT,
  ctx: ToolContext,
): Promise<ToolResult<{ jobId: string }>> {
  try {
    const data = (await canvaFetch('/exports', ctx.accessToken, {
      method: 'POST',
      body: JSON.stringify({ design_id: input.designId, format: input.format }),
    })) as { job?: { id?: string } }
    const jobId = data.job?.id
    if (!jobId) return { ok: false, error: 'لم تُرجع Canva معرف مهمة التصدير' }
    // الاستعلام عن جاهزية التصدير: GET /exports/{job_id} — يعمل حتى الحالة success
    return { ok: true, data: { jobId } }
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : String(e) }
  }
}

export const canvaSpecs: ToolSpec[] = [
  {
    name: 'canva_create_from_template',
    description: 'إنشاء تصميم تسويقي جديد من قالب Canva (بوستات، إعلانات، عروض) — بإذن المالك فقط',
    parameters: z.toJSONSchema(CreateFromTemplateInput),
  },
  {
    name: 'canva_export_design',
    description: 'تصدير تصميم Canva إلى PNG/PDF/JPG — يعيد مهمة تصدير يُستعلم عنها',
    parameters: z.toJSONSchema(ExportDesignInput),
  },
]
