// app/api/slash/route.ts — بوابة أوامر السلاش من الواجهة إلى المحرك (Workspace OS)
// بأمر المالك 2026-10-20. يستدعي workspaces/system_engine/router_daemon.py (لا ازدواج منطق):
//   /task  → ملف في inbox_tasks + push لجدول agent_tasks في Supabase
//   /summon → سجل استدعاء في chats
//   /status → إحصاء active_workspaces + inbox_tasks
import { NextRequest, NextResponse } from 'next/server'
import { execFile } from 'child_process'
import path from 'path'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

const WORKSPACE_ROOT =
  process.env.WORKSPACE_ROOT?.replace(/\\system_engine$/, '') ||
  'G:\\ai\\Naggar Print POS Agent\\workspaces'
const ENGINE = path.join(WORKSPACE_ROOT, 'system_engine', 'router_daemon.py')
const PYTHON = process.env.PYTHON_EXE || 'G:\\ai\\Naggar Print POS Agent\\.venv\\Scripts\\python.exe'

export async function POST(req: NextRequest) {
  let text = ''
  try {
    const body = (await req.json()) as { text?: unknown }
    text = typeof body.text === 'string' ? body.text : ''
  } catch {
    return NextResponse.json({ ok: false, message: 'جسم الطلب غير صالح' }, { status: 400 })
  }
  if (!text.trim().startsWith('/')) {
    return NextResponse.json({ ok: false, executed: false, message: 'ليس أمر سلاش' })
  }
  try {
    const result = await new Promise<string>((resolve, reject) => {
      execFile(
        PYTHON,
        [ENGINE, 'parse', text],
        { timeout: 30_000, encoding: 'utf8', cwd: path.dirname(WORKSPACE_ROOT) },
        (err, stdout) => (err ? reject(err) : resolve(stdout)),
      )
    })
    const parsed = JSON.parse(result) as Record<string, unknown>
    return NextResponse.json(parsed)
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err)
    return NextResponse.json({ ok: false, executed: false, message: `المحرك فشل: ${message.slice(0, 200)}` }, { status: 500 })
  }
}
