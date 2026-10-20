// app/api/workspace/route.ts — متصفح ملفات Workspace (Read-Only صارم)
// MARWA CORE task-4 (أمر المالك 2026-10-20 — تكليف فيجن).
// يقرأ فقط من process.env.ROOT_WORKSPACE (G:\Marwa-Bot على اللابتوب) عبر fs.readdir.
// ⚠️ الخط الأحمر: لا يوجد أي كتابة في هذا الملف إطلاقاً — قراءة فقط صارمة،
//    وحماية كاملة من path traversal (كل مسار يُحلّ ويُقارن بجذر العمل).
import { NextRequest, NextResponse } from 'next/server'
import { promises as fs } from 'fs'
import path from 'path'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

const ROOT = process.env.ROOT_WORKSPACE || 'G:\\Marwa-Bot'
const MAX_DEPTH = 3

/** مجلدات ثقيلة/غير مفيدة تُستثنى من العرض (قراءة فقط — لا تُحذف ولا تُمس) */
const SKIP_DIRS = new Set([
  'node_modules',
  '.git',
  '.venv',
  '.next',
  '.pnpm-store',
  'backup',
  '_backup_archive',
  'logs',
])

type Entry = {
  name: string
  /** المسار النسبي من جذر العمل — بفاصل / دائماً */
  path: string
  type: 'file' | 'dir'
  size?: number
  mtime?: string
  children?: Entry[]
}

async function listDir(absDir: string, rel: string, depth: number): Promise<Entry[]> {
  const items = await fs.readdir(absDir, { withFileTypes: true })
  const entries: Entry[] = []
  for (const it of items) {
    const relPath = rel ? `${rel}/${it.name}` : it.name
    if (it.isDirectory()) {
      if (depth >= MAX_DEPTH || SKIP_DIRS.has(it.name)) continue
      const childAbs = path.join(absDir, it.name)
      let mtime: string | undefined
      try {
        mtime = (await fs.stat(childAbs)).mtime.toISOString()
      } catch {
        /* مجلد بلا صلاحية قراءة للحالة — يُعرض بدون mtime */
      }
      entries.push({
        name: it.name,
        path: relPath,
        type: 'dir',
        mtime,
        children: await listDir(childAbs, relPath, depth + 1),
      })
    } else {
      const abs = path.join(absDir, it.name)
      let size: number | undefined
      let mtime: string | undefined
      try {
        const st = await fs.stat(abs)
        size = st.size
        mtime = st.mtime.toISOString()
      } catch {
        /* ملف بلا قراءة للحالة — يُعرض بدون حجم */
      }
      entries.push({ name: it.name, path: relPath, type: 'file', size, mtime })
    }
  }
  // مجلدات أولاً ثم ملفات — كل قسم مرتب بالاسم
  entries.sort((a, b) =>
    a.type === b.type
      ? a.name.localeCompare(b.name, 'ar')
      : a.type === 'dir'
        ? -1
        : 1,
  )
  return entries
}

function humanSize(bytes?: number): string | undefined {
  if (bytes === undefined) return undefined
  if (bytes < 1024) return `${bytes} بايت`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} ك.ب`
  return `${(bytes / (1024 * 1024)).toFixed(1)} م.ب`
}

export async function GET(req: NextRequest) {
  const rootResolved = path.resolve(ROOT)
  const relParam = (req.nextUrl.searchParams.get('path') || '').replace(/^\/+/, '')

  // حماية path traversal: الحل ثم المقارنة بجذر العمل
  const target = relParam ? path.resolve(rootResolved, relParam) : rootResolved
  if (target !== rootResolved && !target.startsWith(rootResolved + path.sep)) {
    return NextResponse.json(
      { success: false, error: 'مسار خارج نطاق العمل غير مسموح' },
      { status: 403 },
    )
  }

  try {
    const stat = await fs.stat(target)
    if (!stat.isDirectory()) {
      return NextResponse.json({ success: false, error: 'المسار المطلوب ليس مجلداً' }, { status: 400 })
    }
    const depth = relParam ? relParam.split('/').length : 0
    const entries = await listDir(target, relParam, depth)
    const dirs = entries.filter((e) => e.type === 'dir').length
    const files = entries.filter((e) => e.type === 'file').length

    return NextResponse.json(
      {
        success: true,
        root: rootResolved,
        path: relParam || '',
        skipped: [...SKIP_DIRS],
        counts: { dirs, files },
        entries,
        human_size: entries
          .filter((e) => e.type === 'file')
          .map((e) => ({ path: e.path, size: humanSize(e.size) })),
      },
      { headers: { 'Cache-Control': 'no-store' } },
    )
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e)
    if (msg.includes('ENOENT') || msg.includes('no such file')) {
      return NextResponse.json(
        { success: false, error: 'المجلد غير موجود في مساحة العمل' },
        { status: 404 },
      )
    }
    return NextResponse.json(
      { success: false, error: `تعذر قراءة المجلد: ${msg}` },
      { status: 500 },
    )
  }
}
