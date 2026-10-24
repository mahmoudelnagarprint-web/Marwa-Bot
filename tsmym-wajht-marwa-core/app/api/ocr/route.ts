// app/api/ocr/route.ts — استخراج النص من الصور عبر indra-ocr (OCR محلي على CPU) — v2 (Windows-safe)
// MARWA CORE task-5 (أمر المالك 2026-10-24): بدل نماذج الرؤية المكلفة.
//
// 🆕 v2 — إصلاحات التوافقية مع Windows (بأمر المالك بعد ظهور Python Traceback من الواجهة):
//   1) execFile مع مسار الصورة كـ Argument منفصل (لا shell — لا مشاكل مسافات Windows).
//   2) تمرير env صريح = process.env + PYTHONIOENCODING=utf-8 + PYTHONUTF8=1
//      ← السبب الجذري للتعطل: الطفل بايثون على ويندوز يكتب المخرجات بترميز cp1252
//        عبر الأنابيب، وأي نتيجة OCR عربية تسبب UnicodeEncodeError وتعطل __main__.py.
//   3) تسجيل كامل: stderr كاملاً في Server Console + آخر سطر منه فقط في الـJSON للواجهة.
//   4) احتياطي: إن لم يوجد indra-ocr.exe يُستدعى مفسّر البيئة مباشرة (python -m indra_ocr).
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

const ALLOWED_TYPES = new Set([
  'image/png',
  'image/jpeg',
  'image/webp',
  'image/bmp',
  'image/tiff',
])
const MAX_FILE_BYTES = 15 * 1024 * 1024 // 15MB
const TIMEOUT_MS = Number(process.env.INDRA_OCR_TIMEOUT_MS ?? 240_000)

/** بيئة الطفل: وراثة كاملة + فرض UTF-8 على مدخلات/مخرجات بايثون (إصلاح التعطل على ويندوز) */
function childEnv(): NodeJS.ProcessEnv {
  return {
    ...process.env,
    PYTHONIOENCODING: 'utf-8',
    PYTHONUTF8: '1',
    HF_HUB_DISABLE_SYMLINKS_WARNING: '1',
  }
}

/** مسارات البيئة المحلية داخل المشروع (قابلة للتجاوز بمتغيرات البيئة) */
function venvScripts(): string {
  return process.env.INDRA_OCR_VENV || path.join(process.cwd(), '.ocr-venv', 'Scripts')
}

/** بناء أمر التشغيل: indra-ocr.exe إن وُجد — وإلا python -m indra_ocr (احتياطي أقوى) */
async function resolveCommand(imagePath: string): Promise<{ cmd: string; args: string[] }> {
  if (process.env.INDRA_OCR_CMD) {
    // صيغة الاختيار اليدوي: "المسار" فقط للـexe — والصورة تُضاف تلقائياً كـArgument
    return { cmd: process.env.INDRA_OCR_CMD, args: [imagePath, '--format', 'md'] }
  }
  const scripts = venvScripts()
  const exe = path.join(scripts, 'indra-ocr.exe')
  try {
    await fs.access(exe)
    return { cmd: exe, args: [imagePath, '--format', 'md'] }
  } catch {
    // الـlauncher غير موجود → المفسّر مباشرة عبر وحدة __main__ (نفس الوظيفة)
    return {
      cmd: path.join(scripts, 'python.exe'),
      args: ['-m', 'indra_ocr', imagePath, '--format', 'md'],
    }
  }
}

/** آخر سطر مفيد من stderr — للعرض المفهوم في الواجهة بدل الـTraceback الطويل */
function lastMeaningfulLine(stderr: string): string {
  const lines = (stderr || '')
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter((l) => l.length > 0 && !l.startsWith(' ') && !/it\/s\]$/.test(l))
  return (lines[lines.length - 1] ?? 'خطأ غير معروف').slice(0, 300)
}

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

    // 2) الاستدعاء: execFile — مسار الصورة Argument منفصل + بيئة UTF-8 كاملة
    const { cmd, args } = await resolveCommand(tempPath)
    const text = await new Promise<string>((resolve, reject) => {
      execFile(
        cmd,
        args,
        {
          timeout: TIMEOUT_MS,
          maxBuffer: 10 * 1024 * 1024,
          windowsHide: true,
          env: childEnv(), // ← الإصلاح الجذري: بايثون يكتب UTF-8 لا cp1252
        },
        (err, stdout, stderr) => {
          if (err) {
            // تسجيل كامل للسيرفر — التشخيص الحقيقي يظهر هنا دائماً
            console.error('[api/ocr] فشل indra-ocr:')
            console.error('[api/ocr] cmd:', cmd)
            console.error('[api/ocr] exit code:', (err as { code?: number | string }).code ?? '?')
            console.error('[api/ocr] stderr كامل:\n' + (stderr || '(فارغ)'))
            console.error('[api/ocr] stdout كامل:\n' + (stdout || '(فارغ)'))
          }
          if (err && !stdout?.trim()) {
            const tail = lastMeaningfulLine(stderr || err.message || '')
            reject(new Error(`فشل OCR (exit=${(err as { code?: number | string }).code ?? '?'}): ${tail}`))
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
    console.error('[api/ocr] خطأ نهائي موجه للواجهة:', msg)
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
