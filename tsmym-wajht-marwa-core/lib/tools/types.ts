// lib/tools/types.ts — الأنواع المشتركة لأدوات الوكلاء الخارجية (MARWA CORE task-6)
// ⚠️ هذه الطبقة بوابة المنظومة للعالم الخارجي — كل أداة تُعرَّف بـ:
//   1) مخطط Zod للمدخلات (Function Calling — النماذج تستدعيها بأمان)
//   2) دالة تنفيذ نقية تستقبل accessToken جاهزاً (لا تعرف شيئاً عن التخزين)
//   3) مواصفة spec (JSON Schema) تُضاف لسجل الأدوات في index.ts
// القاعدة الحاكمة: التوكنات لا تلمس الواجهة أبداً — تُدار في lib/tools/tokens.ts (سيرفر فقط).

export type ProviderId = 'google' | 'canva'

/** حزمة رموز مزود — تُخزن مشفرة AES-256-GCM في خزنة السيرفر فقط */
export type TokenBundle = {
  access_token: string
  refresh_token: string | null
  /** ISO timestamp — ينتهي بعده صلاحية الـaccess token */
  expires_at: string
  scope: string | null
  updated_at: string
}

/** نتيجة موحدة لكل أداة — النموذج يرى نسخة مختصرة منها (بلا تفاصيل حساسة) */
export type ToolResult<T> = { ok: true; data: T } | { ok: false; error: string }

/** سياق التنفيذ — الرمز الجاهز يحلها طبقة الخزنة قبل استدعاء أي أداة */
export type ToolContext = {
  accessToken: string
  /** منفذ اختياري للحد من الاستدعاءات في الدورة الواحدة */
  maxCalls?: number
}

/** مواصفة أداة للـ Function Calling — تُحوَّل لصيغة OpenAI/Anthropic tools في البوابة */
export type ToolSpec = {
  /** اسم فريد بصيغة snake_case — النموذج يستدعيه بهذا الاسم */
  name: string
  /** وصف عربي + إنجليزي موجز يرشد النموذج متى يستدعي الأداة */
  description: string
  /** JSON Schema لمعاملات الاستدعاء (مولدة من مخطط Zod) */
  parameters: Record<string, unknown>
}
