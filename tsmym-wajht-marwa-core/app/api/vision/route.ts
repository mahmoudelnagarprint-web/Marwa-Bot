// app/api/vision/route.ts — مركز القيادة التقنية لفيجن ⚙️ (2026-10-20)
// Mini-OS: منصة إطلاق البرامج + مدير العمليات + محرر الأكواد + التيرمينال الحي
// الخطوط الحمراء: pos_data.db قراءة فقط. سجل التطبيقات في active_workspaces فيجن.
import { NextRequest, NextResponse } from 'next/server'
import { execFile, execFileSync, spawn } from 'child_process'
import fs from 'fs'
import path from 'path'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

const WORKSPACE_ROOT =
  process.env.WORKSPACE_ROOT?.replace(/\\system_engine$/, '') ||
  'G:\\ai\\Naggar Print POS Agent\\workspaces'
const VISION_WS = path.join(WORKSPACE_ROOT, 'vision_coder')
const REGISTRY_FILE = path.join(VISION_WS, 'active_workspaces', 'apps_registry.json')
const PYTHON = process.env.PYTHON_EXE || 'G:\\ai\\Naggar Print POS Agent\\.venv\\Scripts\\python.exe'
const HW_DAEMON = path.join(WORKSPACE_ROOT, 'sasa_devices', 'system_engine', 'sasa_hardware_link.py')
const WORKSPACE_DIR = path.dirname(WORKSPACE_ROOT)

export type AppEntry = { id: string; name: string; exe: string; desc: string; args?: string[]; added_at?: string; match?: string }
export type ProcRow = { key: string; name: string; pid: number | null; running: boolean; kind: 'daemon' | 'app' }

/* سجل التطبيقات — JSON في active_workspaces فيجن */
function readRegistry(): AppEntry[] {
  try {
    return JSON.parse(fs.readFileSync(REGISTRY_FILE, 'utf8')) as AppEntry[]
  } catch {
    return []
  }
}

function writeRegistry(list: AppEntry[]): void {
  fs.mkdirSync(path.dirname(REGISTRY_FILE), { recursive: true })
  fs.writeFileSync(REGISTRY_FILE, JSON.stringify(list, null, 2), 'utf8')
}

/* مدير العمليات — عبر PowerShell Get-CimInstance (wmic أزيل من ويندوز 11 الحديث) */
type DEntry = { name: string; pid: number }
function listWinProcesses(): DEntry[] {
  try {
    const out = execFileSync(
      'powershell',
      ['-NoProfile', '-Command', "Get-CimInstance Win32_Process | Select-Object ProcessId, CommandLine | ConvertTo-Csv -NoTypeInformation"],
      { encoding: 'utf8', timeout: 20_000, windowsHide: true },
    )
    return out
      .split(/\r?\n/)
      .filter(Boolean)
      .map((line) => {
        // CSV: "ProcessId","CommandLine" — أو معجون بينهما
        const m = line.match(/^"(\d+)"\s*,\s*"(.*)"$/)
        return m ? { name: m[2], pid: Number(m[1]) } : null
      })
      .filter((x): x is DEntry => x !== null)
  } catch {
    return []
  }
}

// إشعار مقياس تشغيل الدايمون/التطبيق: match بحسب كلمة مفتاحية في commandline
function findPid(matchFn: (name: string, cmd: string) => boolean): { pid: number | null; cmd: string } | null {
  const procs = listWinProcesses()
  for (const { name, pid } of procs) {
    const cmd = name.replace(/""/g, '"')
    if (pid <= 4) continue
    if (matchFn(cmd.toLowerCase(), cmd)) return { pid, cmd }
  }
  return null
}

function refreshProcesses(): ProcRow[] {
  const rows: ProcRow[] = []
  const daemons: { key: string; name: string; script: string }[] = [
    { key: 'router_daemon', name: 'router_daemon (محرّك الأوامر)', script: 'router_daemon.py' },
    { key: 'sasa_hardware', name: 'sasa_hardware_link (دايمون العتاد)', script: 'sasa_hardware_link.py' },
  ]
  const registered = readRegistry()
  const procs = listWinProcesses()
  void procs // tasklist AABB fallback: عملية لم تُصب في wmic (Windows 11 home الحديث) — محفوظ للتشخيص
  for (const d of daemons) {
    const hit = findPid((c) => c.includes(d.script))
    rows.push({ key: d.key, name: d.name, pid: hit?.pid ?? null, running: hit !== null, kind: 'daemon' })
  }
  for (const a of registered) {
    // المطابقة على العملية الحية للبرنامج نفسه:
    // • app.match explicit (الحقل像 الجديد) — أدق طريقة: substring في commandline
    // • .py — اسم الملف
    // • .bat — نعجز عن تتبع ابن cmd (commandline بلا مسار) → نعرض Stopped وهذه ملاحظة معروفة
    const isPython = /\.py$/i.test(a.exe)
    const pat = (a.match ?? (isPython ? path.win32.basename(a.exe) : '')).toLowerCase()
    const hit = pat ? findPid((_c, raw) => !/pwsh|powershell|deepseek|explorer|cmd\.exe/.test(raw.toLowerCase()) && raw.toLowerCase().includes(pat)) : null
    rows.push({ key: `app:${a.id}`, name: a.name, pid: hit?.pid ?? null, running: hit !== null, kind: 'app' })
  }
  return rows
}

/* تشغيل/إيقاف — subprocess حقيقي على الويندوز */
function startEntry(key: string): { ok: boolean; note: string } {
  if (key === 'router_daemon') {
    spawn(PYTHON, ['-X', 'utf8', path.join(WORKSPACE_ROOT, 'system_engine', 'router_daemon.py'), 'sweep'], {
      detached: true,
      stdio: 'ignore',
      windowsHide: true,
    }).unref()
    return { ok: true, note: 'router_daemon بدأ (sweep)' }
  }
  if (key === 'sasa_hardware') {
    spawn(PYTHON, ['-X', 'utf8', HW_DAEMON], { detached: true, stdio: 'ignore', windowsHide: true }).unref()
    return { ok: true, note: 'sasa_hardware_link بدأ (حلقة كل 3 ثوانٍ)' }
  }
  const id = key.replace(/^app:/, '')
  const app = readRegistry().find((a) => a.id === id)
  if (!app) return { ok: false, note: 'برنامج غير مسجل' }
  const args = app.args ?? []
  try {
    if (/\.py$/i.test(app.exe)) {
      spawn(PYTHON, ['-X', 'utf8', app.exe, ...args], { detached: true, stdio: 'ignore', windowsHide: true }).unref()
    } else if (/\.js$/i.test(app.exe)) {
      // سكربت Node مباشر: spawn detached مع cwd مجلد السكربت — شغالة وواقفة بعد انتهاء الطلب
      spawn(process.execPath, [app.exe, ...args], { detached: true, cwd: path.win32.dirname(app.exe), stdio: 'ignore', windowsHide: true }).unref()
    } else if (/\.bat$/i.test(app.exe) || /\.cmd$/i.test(app.exe)) {
      // Node يرفض spawn .bat مباشرة (EINVAL) — القاذف: PowerShell Start-Process خارج جوبة السيرفر
      execFileSync('powershell', ['-NoProfile', '-Command',
        `Start-Process cmd -ArgumentList '/c','${app.exe.replace(/'/g, "''")}' -WindowStyle Hidden`,
      ], { timeout: 15_000, windowsHide: true })
    } else {
      spawn(app.exe, args, { detached: true, stdio: 'ignore', windowsHide: true }).unref()
    }
    return { ok: true, note: `${app.name} بدأ فعلاً على الويندوز` }
  } catch (e) {
    return { ok: false, note: `فشل التشغيل: ${e instanceof Error ? e.message.slice(0, 80) : String(e)}` }
  }
}

function stopPid(pid: number): { ok: boolean; note: string } {
  try {
    execFileSync('taskkill', ['/PID', String(pid), '/T', '/F'], { encoding: 'utf8', timeout: 10_000, windowsHide: true })
    return { ok: true, note: `عملية ${pid} أُوقفت (مع ابنائها)` }
  } catch (e) {
    return { ok: false, note: `فشل الإيقاف: ${e instanceof Error ? e.message.slice(0, 80) : String(e)}` }
  }
}

/* محرر الأكواد — .env.local و JSON في workspaces، قائمة ملفات مسموحة (حراسة عمودية) */
const EDITABLE_HINTS = ['.env.local', 'apps_registry.json', 'board_state.json', 'hardware_state.json', 'crm_state.json']
function listEditable(): { path: string; name: string }[] {
  const out: { path: string; name: string }[] = []
  const envLocal = path.join(WORKSPACE_DIR, 'tsmym-wajht-marwa-core', '.env.local')
  if (fs.existsSync(envLocal)) out.push({ path: envLocal, name: '.env.local' })
  for (const wsDir of ['vision_coder', 'sasa_devices', 'bebo_production', 'hakim_advisor', 'koko_marketing']) {
    const dir = path.join(WORKSPACE_ROOT, wsDir, 'active_workspaces')
    try {
      for (const f of fs.readdirSync(dir)) {
        if (/\.json$/i.test(f) && EDITABLE_HINTS.some((h) => f.includes(h))) {
          out.push({ path: path.join(dir, f), name: `${wsDir}/${f}` })
        }
      }
    } catch { /* المجلد غير موجود */ }
  }
  return out
}

/* ================= GET ================= */
export async function GET(req: NextRequest) {
  const what = req.nextUrl.searchParams.get('what') ?? 'all'
  try {
    const registry = readRegistry()
    const out: Record<string, unknown> = { apps: registry, registry_file: REGISTRY_FILE }
    if (what === 'apps') return NextResponse.json(out)
    const procs = refreshProcesses()
    if (what === 'procs') return NextResponse.json({ processes: procs })
    if (what === 'files') return NextResponse.json({ files: listEditable() })
    if (what === 'read_file') {
      const p = req.nextUrl.searchParams.get('path') ?? ''
      if (!listEditable().some((f) => path.resolve(f.path) === path.resolve(p))) {
        return NextResponse.json({ error: 'ملف خارج القائمة المسموحة' }, { status: 403 })
      }
      return NextResponse.json({ path: p, content: fs.readFileSync(p, 'utf8').slice(0, 60_000) })
    }
    // all: المستخدمة في التحميل الافتتاحي
    return NextResponse.json({ ...out, processes: procs, files: listEditable() })
  } catch (err) {
    const m = err instanceof Error ? err.message : String(err)
    return NextResponse.json({ error: `مركز فيجن: ${m.slice(0, 200)}` }, { status: 500 })
  }
}

/* ================= POST ================= */
export async function POST(req: NextRequest) {
  let action = '', id = '', name = '', exe = '', desc = '', key = '', pid = 0, filePath = '', content = '', match = ''
  try {
    const body = (await req.json()) as Record<string, unknown>
    action = String(body.action ?? '')
    id = String(body.id ?? '')
    name = String(body.name ?? '')
    exe = String(body.exe ?? '')
    desc = String(body.desc ?? '')
    key = String(body.key ?? '')
    pid = Number(body.pid ?? 0)
    filePath = String(body.path ?? '')
    content = String(body.content ?? '')
    match = String(body.match ?? '')
  } catch {
    return NextResponse.json({ ok: false, message: 'جسم الطلب غير صالح' }, { status: 400 })
  }
  try {
    // 1️⃣ إضافة برنامج جديد
    if (action === 'add_app') {
      if (!name.trim() || !exe.trim()) return NextResponse.json({ ok: false, message: 'اسم ومسار البرنامج مطلوبان' }, { status: 400 })
      const list = readRegistry()
      const entry: AppEntry = {
        id: `app-${Date.now() % 100000}`,
        name: name.trim(),
        exe: exe.trim(),
        desc: desc.trim(),
        args: [],
        match: match.trim() || undefined,
        added_at: new Date().toISOString(),
      }
      list.push(entry)
      writeRegistry(list)
      return NextResponse.json({ ok: true, app: entry, message: `➕ ${entry.name} مسجل في المنصة` })
    }
    // حذف برنامج
    if (action === 'remove_app') {
      const list = readRegistry().filter((a) => a.id !== id)
      writeRegistry(list)
      return NextResponse.json({ ok: true, message: '🗑️ حُذف من السجل' })
    }
    // 1️⃣ تشغيل فعلي
    if (action === 'start' || action === 'restart') {
      if (action === 'restart') {
        const rows = refreshProcesses()
        const hit = rows.find((r) => r.key === key && r.pid)
        if (hit?.pid) void stopPid(hit.pid)
      }
      const r = startEntry(key)
      return NextResponse.json({ ok: r.ok, message: r.note })
    }
    // 2️⃣ إيقاف
    if (action === 'stop') {
      let target = pid
      if (!target && key) {
        const hit = refreshProcesses().find((r) => r.key === key && r.pid)
        target = hit?.pid ?? 0
      }
      if (!target) return NextResponse.json({ ok: true, message: 'العملية غير موجودة أصلاً (Stopped)' })
      const r = stopPid(target)
      return NextResponse.json(r)
    }
    // 3️⃣ حفظ ملف الإعدادات
    if (action === 'save_file') {
      if (!listEditable().some((f) => path.resolve(f.path) === path.resolve(filePath))) {
        return NextResponse.json({ ok: false, message: 'ملف خارج القائمة المسموحة' }, { status: 403 })
      }
      fs.writeFileSync(filePath, content, 'utf8')
      return NextResponse.json({ ok: true, message: `💾 حُفظ ${path.basename(filePath)}` })
    }
    // 5️⃣ إيقاف بأي pid مباشرة (يستخدمه الحرَس الذكي للتطبيقات التي تُخفى خلف cmd)
    if (action === 'stop_any') {
      if (!pid) return NextResponse.json({ ok: false, message: 'pid مطلوب' }, { status: 400 })
      const r = stopPid(pid)
      return NextResponse.json(r)
    }
    return NextResponse.json({ ok: false, message: `إجراء غير معروف: ${action}` }, { status: 400 })
  } catch (err) {
    const m = err instanceof Error ? err.message : String(err)
    return NextResponse.json({ ok: false, message: m.slice(0, 200) }, { status: 500 })
  }
}
