// app/api/devices/route.ts — غرفة تحكم صاصا (Master Controller) 2026-10-20
// الخط الأحمر: pos_data.db قراءة فقط. طابور التشغيل يقرأ من board_state.json (مملكة بيبو).
// الرادار (حرارة/حبر/حالة) محاكاة وهمية مؤقتة لحين ربط الحساسات — موسومة بوضوح.
import { NextRequest, NextResponse } from 'next/server'
import { DatabaseSync } from 'node:sqlite'
import { execFile } from 'child_process'
import fs from 'fs'
import path from 'path'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

const WORKSPACE_ROOT =
  process.env.WORKSPACE_ROOT?.replace(/\\system_engine$/, '') ||
  'G:\\ai\\Naggar Print POS Agent\\workspaces'
const BEBO_ROOT = path.join(WORKSPACE_ROOT, 'bebo_production')
const BOARD_FILE = path.join(BEBO_ROOT, 'active_workspaces', 'board_state.json')
const ENGINE = path.join(WORKSPACE_ROOT, 'system_engine', 'router_daemon.py')
const PYTHON = process.env.PYTHON_EXE || 'G:\\ai\\Naggar Print POS Agent\\.venv\\Scripts\\python.exe'
const DB_PATH = 'G:\\ai\\Elnagar POS\\pos_data.db'
const DESIGNS_DIR = process.env.DESIGNS_DIR || 'G:\\ai\\Naggar Print POS Agent\\designs'
const DESIGN_EXTS = new Set(['.dxf', '.cdr', '.psd', '.ai', '.pdf', '.svg', '.plt'])
// العتاد الحقيقي (فيجن 2026-10-20): دايمون Python يكتب hardware_state.json كل 3 ثوانٍ
const HW_STATE = path.join(WORKSPACE_ROOT, 'sasa_devices', 'active_workspaces', 'hardware_state.json')
// المجلدات الساخنة للتوجيه المباشر (راصد + فيجن):
// ليزر CO2 → Laser_HotFolder (LightBurn / RDWorks يسحب فوراً)
// كاتر بلوتر → Cutter_HotFolder (حسب برنامج الكاتر)
const LASER_HOT = path.join(WORKSPACE_ROOT, 'sasa_devices', 'active_workspaces', 'Laser_HotFolder')
const CUTTER_HOT = path.join(WORKSPACE_ROOT, 'sasa_devices', 'active_workspaces', 'Cutter_HotFolder')

export type SpoolTask = {
  id: number
  client: string
  total: number
  items: { name: string; qty: number }[]
  machine: string
}

export type DesignFile = {
  name: string
  rel: string
  size: number
  mtime: string
  ext: string
}

export type MachineTelemetry = {
  id: string
  name: string
  state: 'Idle' | 'Busy'
  metric_label: string
  metric_value: string | number
  metric_unit: string
  simulated: true | false
  hardware_source?: string
}

function runSlash(text: string): Promise<Record<string, unknown>> {
  return new Promise((resolve, reject) => {
    execFile(
      PYTHON,
      [ENGINE, 'parse', text],
      { timeout: 30_000, encoding: 'utf8', cwd: path.dirname(WORKSPACE_ROOT) },
      (err, stdout) => (err ? reject(err) : resolve(JSON.parse(stdout) as Record<string, unknown>)),
    )
  })
}

/** ماكينة مقترحة من أصناف الطلب — نفس منطق كشف بيبو */
function machineFor(items: { name: string; qty: number }[]): string {
  const all = items.map((i) => i.name).join(' ')
  if (/ليزر|خشب|درع|طارة|لوحة|تابلوه/i.test(all)) return 'ليزر CO2'
  if (/قلم|ستيكر|كاتر|لوجو|logo/i.test(all)) return 'كاتر بلوتر'
  return 'Epson L1800'
}

/** قراءة العتاد الحقيقي من دايمون Python (نقطة تحقق 2026-10-20) — يهتم مع المحاكاة فقط في غيابه */
type HardwareState = {
  updated_at?: string
  epson?: { state?: string; online?: boolean; jobs?: number }
  cutter?: { state?: string; online?: boolean; port?: string }
  laser?: { state?: string; online?: boolean; port?: string }
}

function readHardware(): HardwareState | null {
  try {
    return JSON.parse(fs.readFileSync(HW_STATE, 'utf8')) as HardwareState
  } catch {
    return null
  }
}

/** رادار: العتاد الحقيقي أولاً (hardware_state.json)، والمحاكاة احتياط — دائماً موسومة بمصدر الحقيقة */
function telemetry(board: SpoolTask[]): MachineTelemetry[] {
  const busyLaser = board.some((t) => t.machine === 'ليزر CO2')
  const busyEpson = board.some((t) => t.machine === 'Epson L1800')
  const busyCutter = board.some((t) => t.machine === 'كاتر بلوتر')
  const soon = Date.now()
  const wob = (seed: number, span: number) => ((Math.sin(soon / 30_000 + seed) + 1) / 2) * span
  const hw = readHardware()
  const fromHw = (status: string | undefined, online: boolean | undefined, fallback: 'Idle' | 'Busy'): 'Idle' | 'Busy' => {
    if (!online) return 'Idle' // ماكينة غير متصلة → تعامل كخامل (ولا تزعج الرسم)
    if (status === 'busy' || status === 'printing') return 'Busy'
    if (status === 'idle') return 'Idle'
    return fallback
  }
  if (hw) {
    return [
      { id: 'laser', name: 'ليزر CO2', state: fromHw(hw.laser?.state, true, busyLaser ? 'Busy' : 'Idle'), metric_label: 'حالة الإتصال', metric_value: hw.laser?.state === 'idle' ? 'متصلة' : 'غير مربوطة', metric_unit: '', simulated: false, hardware_source: `دايمون العتاد ${hw.updated_at ?? ''}` },
      { id: 'epson', name: 'Epson L1800', state: fromHw(hw.epson?.state, hw.epson?.online, busyEpson ? 'Busy' : 'Idle'), metric_label: 'مهام الطباعة', metric_value: hw.epson?.jobs ?? 0, metric_unit: 'مهمة', simulated: false, hardware_source: `win32print @ ${hw.updated_at ?? ''}` },
      { id: 'cutter', name: 'كاتر بلوتر', state: fromHw(hw.cutter?.state, hw.cutter?.online, busyCutter ? 'Busy' : 'Idle'), metric_label: 'المنفذ', metric_value: hw.cutter?.port ?? '-', metric_unit: '', simulated: false, hardware_source: `pyserial @ ${hw.updated_at ?? ''}` },
    ]
  }
  return [
    {
      id: 'laser', name: 'ليزر CO2', state: busyLaser ? 'Busy' : 'Idle',
      metric_label: 'حرارة المياه', metric_value: Math.round((28 + wob(1, 9)) * 10) / 10, metric_unit: '°م', simulated: true,
    },
    {
      id: 'epson', name: 'Epson L1800', state: busyEpson ? 'Busy' : 'Idle',
      metric_label: 'مستوى الحبر', metric_value: Math.round(62 + wob(2, 30)), metric_unit: '%', simulated: true,
    },
    {
      id: 'cutter', name: 'كاتر بلوتر', state: busyCutter ? 'Busy' : 'Idle',
      metric_label: 'حالة الاستعداد', metric_value: Math.round(80 + wob(3, 20)), metric_unit: '%', simulated: true,
    },
  ]
}

interface DirEntry {
  name: string
  isDirectory(): boolean
  isFile(): boolean
}

function walkDesigns(dir: string, rel: string, out: DesignFile[], depth: number): void {
  if (depth > 3 || out.length >= 80) return
  let entries: DirEntry[] = []
  try {
    entries = fs.readdirSync(dir, { withFileTypes: true }) as unknown as DirEntry[]
  } catch {
    return
  }
  for (const e of entries) {
    const relPath = rel ? `${rel}/${e.name}` : e.name
    const abs = path.join(dir, e.name)
    if (e.isDirectory()) walkDesigns(abs, relPath, out, depth + 1)
    else if (e.isFile() && DESIGN_EXTS.has(path.extname(e.name).toLowerCase())) {
      try {
        const st = fs.statSync(abs)
        out.push({ name: e.name, rel: relPath, size: st.size, mtime: st.mtime.toISOString(), ext: path.extname(e.name).slice(1).toUpperCase() })
      } catch {
        /* تجاهل */
      }
    }
  }
}

export async function GET() {
  try {
    const db = new DatabaseSync(DB_PATH, { readOnly: true })
    const rows = db.prepare(
      `SELECT o.id, o.total_amount, c.name AS client
       FROM orders o LEFT JOIN clients c ON c.id = o.client_id`,
    ).all() as Record<string, unknown>[]
    const items = db.prepare('SELECT order_id, product_name, qty FROM order_items').all() as Record<string, unknown>[]
    db.close()

    let overrides: Record<string, string> = {}
    try { overrides = JSON.parse(fs.readFileSync(BOARD_FILE, 'utf8')) as Record<string, string> } catch { /* default */ }

    const byOrder = new Map<number, { name: string; qty: number }[]>()
    for (const r of items) {
      const oid = Number(r.order_id)
      const arr = byOrder.get(oid) ?? []
      arr.push({ name: String(r.product_name ?? ''), qty: Number(r.qty ?? 0) })
      byOrder.set(oid, arr)
    }
    const colOf = (id: number, status: string) =>
      overrides[String(id)] ?? (status === 'Ready' ? 'ready' : status === 'Under Preparation' ? 'design' : 'design')
    const statusOf = new Map(rows.map((r) => [Number(r.id), String(r.status ?? '')]))

    // طابور صاصا = عمود printing فقط (يقرأ من لوحة بيبو)
    const spool: SpoolTask[] = rows
      .map((r) => {
        const id = Number(r.id)
        const it = byOrder.get(id) ?? []
        return { id, client: String(r.client ?? 'عميل محذوف'), total: Number(r.total_amount ?? 0), items: it, machine: machineFor(it) }
      })
      .filter((t) => colOf(t.id, statusOf.get(t.id) ?? '') === 'printing')

    const designs: DesignFile[] = []
    walkDesigns(DESIGNS_DIR, '', designs, 0)

    return NextResponse.json({
      source: 'pos-db-ro (read-only) + board_state.json (بيبو) + DESIGNS_DIR',
      tag: 'محسوب من البرنامج',
      spool,
      telemetry: telemetry(spool),
      designs_dir: DESIGNS_DIR,
      designs,
    })
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err)
    return NextResponse.json({ error: `فشل رادار صاصا: ${message.slice(0, 200)}` }, { status: 500 })
  }
}

export async function POST(req: NextRequest) {
  let action = '', orderId = 0, machine = '', maintenance = '', fileRel = ''
  try {
    const body = (await req.json()) as { action?: string; order_id?: number; machine?: string; maintenance?: string; file_rel?: string }
    action = body.action ?? ''
    orderId = Number(body.order_id ?? 0)
    machine = body.machine ?? ''
    maintenance = body.maintenance ?? ''
    fileRel = body.file_rel ?? ''
  } catch {
    return NextResponse.json({ ok: false, message: 'جسم الطلب غير صالح' }, { status: 400 })
  }

  try {
    // ---------- 🚀 إرسال للماكينة: إشعار بيبو + مروة ----------
    // **التوجيه المباشر للملفات (راصد 2026-10-20):** مع file_rel (من متصفح التصميمات) —
    // ليزر CO2 → Laser_HotFolder (LightBurn / RDWorks يسحب فوراً)
    // كاتر بلوتر → Cutter_HotFolder
    if (action === 'launch_machine') {
      if (!orderId || !machine) {
        return NextResponse.json({ ok: false, message: 'معطيات ناقصة' }, { status: 400 })
      }
      // التوجيه المباشر: نسخ ملف التصميم للمجلد الساخن المناسب
      let routed = ''
      if (fileRel) {
        try {
          const src = path.join(DESIGNS_DIR, fileRel)
          const hotdir = machine === 'ليزر CO2' ? LASER_HOT : machine === 'كاتر بلوتر' ? CUTTER_HOT : ''
          if (fs.existsSync(src) && hotdir) {
            fs.mkdirSync(hotdir, { recursive: true })
            const dest = path.join(hotdir, path.basename(src))
            fs.copyFileSync(src, dest)
            routed = hotdir.split('\\').slice(-2).join('/')
          }
        } catch {
          routed = '' // فشل النسخ لا يعطل التنبيه
        }
      }
      const out = await runSlash(`/summon @bebo @marwa الطلب #${orderId} دخل حيز التنفيذ الفعلي على ${machine} — صاصا بدأ التشغيل 🚀 (تسجيل في سجل الورشة)`)
      return NextResponse.json({
        ok: Boolean(out.ok),
        notify: out.ok
          ? `🚀 بيبو ومروة تلقوا تنبيه التشغيل — ${String(out.file ?? '').split('\\').pop()}${routed ? ` • الملف التوجّه إلى ${routed}` : ''}`
          : '⚠️ المحرك رفض التنبيه',
        file: String(out.file ?? ''),
        routed_to: routed || null,
      })
    }

    // ---------- 🔧 صيانة وقائية: تحديث لمروة (سجل الورشة) ----------
    if (action === 'maintenance') {
      if (!machine || !maintenance) {
        return NextResponse.json({ ok: false, message: 'معطيات ناقصة' }, { status: 400 })
      }
      const out = await runSlash(`/summon @marwa 🔧 صيانة وقائية — ${machine}: ${maintenance} (سجّليها في سجل الورشة)`)
      return NextResponse.json({
        ok: Boolean(out.ok),
        notify: out.ok ? `🔧 مروة استلمت التحديث — ${String(out.file ?? '').split('\\').pop()}` : '⚠️ المحرك رفض',
        file: String(out.file ?? ''),
      })
    }

    return NextResponse.json({ ok: false, message: `إجراء غير معروف: ${action}` }, { status: 400 })
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err)
    return NextResponse.json({ ok: false, message: message.slice(0, 200) }, { status: 500 })
  }
}
