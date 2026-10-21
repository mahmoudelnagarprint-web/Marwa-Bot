// app/api/customer-reply/route.ts — صياغة رد ذكي لعميل (شات العملاء في غرفة سلمى)
// بأمر المالك 2026-10-21: يقرأ حالة طلب العميل من لوحة بيبو (board_state.json)
// + POS (قراءة فقط) ويولد رداً عبر بوابة الذكاء الاصطناعي — لا صياغة تخمينية.
import { NextRequest, NextResponse } from 'next/server'
import { DatabaseSync } from 'node:sqlite'
import fs from 'fs'
import { chatWithFailover, type ChatMsg } from '@/lib/ai-gateway'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

const ROOT = 'G:\\ai\\Naggar Print POS Agent'
const POS_DB = 'G:\\ai\\Elnagar POS\\pos_data.db'

export async function POST(req: NextRequest) {
  let body: { client?: unknown; intent?: unknown }
  try {
    body = (await req.json()) as { client?: unknown; intent?: unknown }
  } catch {
    return NextResponse.json({ ok: false, reason: 'جسم الطلب غير صالح' }, { status: 400 })
  }
  const clientName = String(body.client ?? '').trim()
  const intent = String(body.intent ?? '').trim()
  if (!clientName) return NextResponse.json({ ok: false, reason: 'اسم العميل مطلوب' }, { status: 400 })

  // 1) العميل من POS (قراءة فقط — TRIM لمطابقة الأسماء بمسافات زائدة)
  type PosClient = { id: number; name: string; phone: string | null; balance: number }
  type PosOrder = { id: number; status: string; total_amount: number; date: string }
  let clientRow: PosClient | null = null
  let orders: PosOrder[] = []
  try {
    const db = new DatabaseSync(POS_DB, { readOnly: true })
    clientRow = (db
      .prepare('SELECT id, TRIM(name) AS name, NULLIF(phone, \'\') AS phone, balance FROM clients WHERE TRIM(name) = ? LIMIT 1')
      .get(clientName) ?? null) as PosClient | null
    if (clientRow) {
      // نفس منطق لوحة سلمى: رصيد العميل من clients.balance (لا يوجد عمود balance في orders)
      orders = db
        .prepare('SELECT o.id, o.status, o.total_amount, o.date FROM orders o WHERE o.client_id = ? ORDER BY o.id DESC LIMIT 5')
        .all(clientRow.id) as unknown as PosOrder[]
    }
    db.close()
  } catch { /* POS غير متاح — نكمل بما متاح */ }
  if (!clientRow) return NextResponse.json({ ok: false, reason: `العميل «${clientName}» غير موجود في POS` }, { status: 404 })

  // 2) حالة الطلبات من لوحة بيبو (board_state.json)
  let board: Record<string, string> = {}
  try {
    board = JSON.parse(fs.readFileSync(`${ROOT}\\workspaces\\bebo_production\\active_workspaces\\board_state.json`, 'utf8')) as Record<string, string>
  } catch { /* لا لوحة — نتجاهل */ }

  const statusMap: Record<string, string> = {
    design: 'في التصميم', printing: 'جاري الطباعة', ready: 'جاهز للاستلام', delivered: 'تم التسليم',
  }
  const lines = orders.map((o) => {
    const boardSt = board[String(o.id)]
    const st = boardSt ? (statusMap[boardSt] ?? boardSt) : o.status
    return `طلب #${o.id}: ${st} • ${Math.round(o.total_amount)}ج`
  })

  const facts =
    `العميل: ${clientRow.name}\n` +
    `رصيد الحساب: ${Math.round(clientRow.balance)}ج\n` +
    `آخر الطلبات:\n${lines.join('\n') || 'لا طلبات'}\n`

  const system: ChatMsg = {
    role: 'system',
    content:
      'أنت مساعد خدمة عملاء ورشة «النجار برنت» بلسان سلمى. اكتب رسالة واتساب قصيرة (جملتان إلى ثلاث) ' +
      'بالعامية المصرية المهذبة والودودة للعميل، بناءً على الحالة الحقيقية فقط — لا تخترع أي رقم أو وعد. ' +
      'إن كان فيه متأخر اذكره بلطف، وإن كان الطلب جاهزاً ابشر بالاستلام.',
  }
  const user: ChatMsg = {
    role: 'user',
    content:
      `اكتب رسالة واتساب للعميل.\n${intent ? `النية: ${intent}\n` : ''}\n${facts}`,
  }

  const result = await chatWithFailover('salma_crm', [system, user], { maxTokens: 800 })
  if (!result.ok) return NextResponse.json(result, { status: 503 })
  return NextResponse.json({ ...result, phone: clientRow.phone })
}
