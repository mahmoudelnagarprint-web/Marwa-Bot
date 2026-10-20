// app/api/production/route.ts — لوحة إنتاج بيبو (قلعة الإنتاج) 2026-10-20
// الخط الأحمر: قاعدة الورشة pos_data.db قراءة فقط إلزامياً.
// حالة الكانبان تُخزَّن في workspaces/bebo_production/active_workspaces/board_state.json
// (ملك/workspace OS — ليست قاعدة الورشة). تنبيه سلمى يتم عبر المحرك router_daemon.py.
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
const INBOX_DIR = path.join(BEBO_ROOT, 'inbox_tasks')
const ARCHIVE_DIR = path.join(BEBO_ROOT, 'archive')
const BOARD_FILE = path.join(BEBO_ROOT, 'active_workspaces', 'board_state.json')
const ENGINE = path.join(WORKSPACE_ROOT, 'system_engine', 'router_daemon.py')
const PYTHON = process.env.PYTHON_EXE || 'G:\\ai\\Naggar Print POS Agent\\.venv\\Scripts\\python.exe'
const DB_PATH = 'G:\\ai\\Elnagar POS\\pos_data.db'

export type BoardColumn = 'design' | 'printing' | 'ready'

export type ProductionCard = {
  id: number
  client: string
  status: string
  date: string
  total: number
  items: { name: string; qty: number }[]
  col: BoardColumn
}

export type InboxItem = {
  file: string
  title: string
  detail: string
  created_at: string
  op_id: string | null
}

function readBoardState(): Record<string, BoardColumn> {
  try {
    return JSON.parse(fs.readFileSync(BOARD_FILE, 'utf8')) as Record<string, BoardColumn>
  } catch {
    return {}
  }
}

function defaultCol(status: string): BoardColumn {
  if (status === 'Ready') return 'ready'
  if (status === 'Under Preparation') return 'design'
  return 'design'
}

/** استدعاء المحرك (router_daemon.py parse) — لا ازدواج منطق */
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

const SENDER_MARKERS: Record<string, string> = {
  salma: 'salma', fares: 'fares', bebo: 'bebo', koko: 'koko', sasa: 'sasa',
  hakim: 'hakim', afkar: 'afkar', rased: 'rased', vision: 'vision',
}

/** إشعار المرسل: ابحث عن @mention داخل نص المهمة غير الوكيل المستهدف نفسه */
function detectSender(taskText: string, target = 'bebo'): string | null {
  const mentions = taskText.match(/@(\w+)/g) ?? []
  for (const m of mentions) {
    const id = m.slice(1).toLowerCase()
    if (id in SENDER_MARKERS && id !== target) return id
  }
  return null
}

async function listInbox(): Promise<InboxItem[]> {
  const items: InboxItem[] = []
  let files: string[] = []
  try {
    files = (fs.readdirSync(INBOX_DIR) as string[]).filter((f) => f.endsWith('.md')).sort().reverse()
  } catch {
    return items
  }
  for (const f of files) {
    try {
      const stat = fs.statSync(path.join(INBOX_DIR, f))
      const body = fs.readFileSync(path.join(INBOX_DIR, f), 'utf8')
      const title = /^#\s*مهمة:\s*(.+)$/m.exec(body)?.[1]?.trim() ?? f.replace(/\.md$/, '')
      const opId = /op_id[:\s]+([0-9a-fA-F-]{10,})/.exec(body)?.[1] ?? null
      items.push({
        file: f,
        title,
        detail: body.split('\n').filter((l) => l.startsWith('- **')).slice(0, 4).join(' '),
        created_at: stat.mtime.toISOString(),
        op_id: opId,
      })
    } catch {
      /* ملف غير قابل للقراءة — تجاهل */
    }
  }
  return items
}

export async function GET() {
  try {
    const db = new DatabaseSync(DB_PATH, { readOnly: true })
    const ordersRes = db.prepare(
      `SELECT o.id, o.status, o.date, o.total_amount, c.name AS client
       FROM orders o LEFT JOIN clients c ON c.id = o.client_id
       WHERE o.status != 'Delivered' ORDER BY o.date ASC`,
    ).all() as Record<string, unknown>[]
    const itemsRes = db.prepare(
      `SELECT oi.order_id, oi.product_name, oi.qty FROM order_items oi
       JOIN orders o ON o.id = oi.order_id WHERE o.status != 'Delivered'`,
    ).all() as Record<string, unknown>[]
    db.close()

    const overrides = readBoardState()
    const byOrder = new Map<number, { name: string; qty: number }[]>()
    for (const r of itemsRes) {
      const oid = Number(r.order_id)
      const arr = byOrder.get(oid) ?? []
      arr.push({ name: String(r.product_name ?? ''), qty: Number(r.qty ?? 0) })
      byOrder.set(oid, arr)
    }
    const board: ProductionCard[] = ordersRes.map((r) => {
      const id = Number(r.id)
      const status = String(r.status ?? '')
      const key = String(id)
      return {
        id,
        client: String(r.client ?? 'عميل محذوف'),
        status,
        date: String(r.date ?? ''),
        total: Number(r.total_amount ?? 0),
        items: byOrder.get(id) ?? [],
        col: overrides[key] ?? defaultCol(status),
      }
    })
    return NextResponse.json({
      source: 'pos-db-ro (read-only) + board_state.json في workspace بيبو',
      tag: 'محسوب من البرنامج',
      board,
      inbox: await listInbox(),
    })
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err)
    return NextResponse.json({ error: `فشل قراءة قاعدة الورشة: ${message.slice(0, 200)}` }, { status: 500 })
  }
}

export async function POST(req: NextRequest) {
  let action = '', orderId = 0, column: BoardColumn | null = null, file = ''
  try {
    const body = (await req.json()) as { action?: string; order_id?: number; column?: string; file?: string }
    action = body.action ?? ''
    orderId = Number(body.order_id ?? 0)
    column =(body.column as BoardColumn) ?? null
    file = body.file ?? ''
  } catch {
    return NextResponse.json({ ok: false, message: 'جسم الطلب غير صالح' }, { status: 400 })
  }

  try {
    // ---------- نقل كارت كانبان ----------
    if (action === 'set_column') {
      if (!orderId || !column || !['design', 'printing', 'ready'].includes(column)) {
        return NextResponse.json({ ok: false, message: 'عمود غير صالح' }, { status: 400 })
      }
      const state = readBoardState()
      state[String(orderId)] = column
      fs.mkdirSync(path.dirname(BOARD_FILE), { recursive: true })
      fs.writeFileSync(BOARD_FILE, JSON.stringify(state, null, 2), 'utf8')
      let notify: string | null = null
      if (column === 'ready') {
        // تنبيه سلمى تلقائياً: استدعاء (summon) عبر المحرك — ملف في chats سلمى
        const out = await runSlash(`/summon @salma طلب #${orderId} جهز في الورشة وهو على قائمة التسليم — بلّغي العميل لاستلامه ☎️`)
        notify = out.ok ? `🔔 سلمى انتبهت (استدعاء) — ${String(out.file ?? '').split('\\').pop()}` : '⚠️ المحرك رفض تنبيه سلمى'
      }
      return NextResponse.json({ ok: true, action, order_id: orderId, column, notify })
    }

    // ---------- ✅ تم التنفيذ في صندوق الوارد ----------
    if (action === 'mark_done') {
      const src = path.join(INBOX_DIR, path.basename(file))
      if (!file || !src.endsWith('.md') || !fs.existsSync(src)) {
        return NextResponse.json({ ok: false, message: 'الملف غير موجود' }, { status: 404 })
      }
      const body = fs.readFileSync(src, 'utf8')
      fs.mkdirSync(ARCHIVE_DIR, { recursive: true })
      const dest = path.join(ARCHIVE_DIR, `${new Date().toISOString().slice(0, 10)}_${path.basename(file)}`)
      fs.renameSync(src, dest)
      const sender = detectSender(body)
      let notify: string | null = null
      if (sender) {
        const out = await runSlash(`/summon @${sender} ✅ تم تنفيذ مهمتك (بيبو): ${path.basename(file).replace(/\.md$/, '').replace(/^[0-9a-fx]{14}-[0-9a-fx]{12}\./, '')}`)
        notify = out.ok ? `🔔 ${sender} أُشير على التنفيذ — ${String(out.file ?? '').split('\\').pop()}` : '⚠️ فشل إشعار المرسل'
      }
      return NextResponse.json({ ok: true, action, archived: dest, notified: sender, notify })
    }

    return NextResponse.json({ ok: false, message: `إجراء غير معروف: ${action}` }, { status: 400 })
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err)
    return NextResponse.json({ ok: false, message: message.slice(0, 200) }, { status: 500 })
  }
}
