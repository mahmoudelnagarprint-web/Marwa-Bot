// app/api/ocr/route.ts — استخراج النص من الصور عبر indra-ocr (OCR محلي على CPU)
// MARWA CORE task-5 (أمر المالك 2026-10-24): بدل نماذج الرؤية المكلفة —
// الصورة تُحفظ في مجلد مؤقت، ويُستدعى CLI الخاص بالمكتبة عبر execFile،
// ويُلتقط المخرَج (Markdown) ثم تُحذف الصورة المؤقتة فوراً في كل الأحوال.
// ⚠️ قراءة فقط: لا كتابة على أي قاعدة أعمال — الملف المؤقت في OS temp وحده.

import { NextRequest, NextResponse } from 'next/server'
import { execFile } from 'child_process'
import { promises as fs } from 'fs'
import os from 'os'
import path from 'path'
import crypto from 'crypto'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'
export const maxDuration = 300

/** مسار CLI المكتبة — قابل للتغيير بمتغير البيئة INDRA_OCR_CMD */
function resolveCli(): string {
  if (process.env.INDRA_OCR_CMD) return process.env.INDRA_OCR_CMD
  // الافتراضي: البيئة الافتراضية داخل المشروع (.ocr-venv — تُنشأ بأمر المالك)
  return path.join(process.cwd(), '.ocr-venv', 'Scripts', 'indra-ocr.exe')
}

const ALLOWED_TYPES = new Set([
  'image/png',
  'image/jpeg',
  'image/webp',
  'image/bmp',
  'image/tiff',
])
const MAX_FILE_BYTES = 15 * 1024 * 1024 // 15MB
const TIMEOUT_MS = Number(process.env.INDRA_OCR_TIMEOUT_MS ?? 240_000)

export async function POST(req: NextRequest) {
  const t0 = Date.now()
  let tempPath: string | null = null

  try {
    const form = await req.formData()
    const file = form.get('file')
    if (!(file instanceof File)) {
      return NextResponse.json(
        { success: false, error: 'لم يُرفَق أي ملف صورة (الحقل المتوقع: file)' },
        { status: 400 },
      )
    }
    if (file.size === 0 || file.size > MAX_FILE_BYTES) {
      return NextResponse.json(
        { success: false, error: `حجم الصورة غير مناسب (الحد الأقصى ${MAX_FILE_BYTES / (1024 * 1024)}MB)` },
        { status: 400 },
      )
    }
    const mime = file.type || 'image/png'
    if (!ALLOWED_TYPES.has(mime)) {
      return NextResponse.json(
        { success: false, error: `نوع الملف غير مدعوم (${mime}) — المسموح: PNG/JPEG/WebP/BMP/TIFF` },
        { status: 415 },
      )
    }

    // 1) حفظ الصورة في مجلد مؤقت باسم عشوائي آمن
    const ext = mime === 'image/jpeg' ? '.jpg' : mime === 'image/tiff' ? '.tiff' : `.${(mime.split('/')[1] || 'png').replace('jpeg', 'jpg')}`
    tempPath = path.join(os.tmpdir(), `marwa_ocr_${crypto.randomUUID()}${ext}`)
    const bytes = Buffer.from(await file.arrayBuffer())
    await fs.writeFile(tempPath, bytes)

    // 2) استدعاء CLI المكتبة — execFile بلا shell (أمان) + مهلة قصوى
    const cli = resolveCli()
    const text = await new Promise<string>((resolve, reject) => {
      execFile(
        cli,
        [tempPath as string, '--format', 'md'],
        { timeout: TIMEOUT_MS, maxBuffer: 10 * 1024 * 1024, windowsHide: true },
        (err, stdout, stderr) => {
          if (err && !stdout?.trim()) {
            const code = (err as { code?: number | string }).code
            reject(new Error(`فشل OCR (code=${code ?? '?'}): ${(stderr || err.message || '').slice(0, 300)}`))
          } else {
            resolve(stdout || '')
          }
        },
      )
    })

    const trimmed = text.trim()
    if (!trimmed) {
      return NextResponse.json(
        { success: false, error: 'لم يُعثر على نص واضح في الصورة — جرّب صورة أوضح أو أقرب', ms: Date.now() - t0 },
        { status: 422 },
      )
    }

    return NextResponse.json(
      {
        success: true,
        text: trimmed,
        chars: trimmed.length,
        ms: Date.now() - t0,
        engine: 'indra-ocr (local CPU)',
      },
      { headers: { 'Cache-Control': 'no-store' } },
    )
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e)
    return NextResponse.json({ success: false, error: msg, ms: Date.now() - t0 }, { status: 500 })
  } finally {
    // 3) حذف الصورة المؤقتة فوراً في كل الأحوال
    if (tempPath) {
      try {
        await fs.unlink(tempPath)
      } catch {
        /* تجاهل — ملف مؤقت في OS temp */
      }
    }
  }
}
