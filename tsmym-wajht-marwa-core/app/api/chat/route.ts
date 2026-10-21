// app/api/chat/route.ts — الشات الحي عبر بوابة الذكاء الاصطناعي (Zero-Downtime)
// بأمر المالك 2026-10-21: مروة والوكلاء يتحدثوا من المتصفح مباشرة مع قراءة
// السياق الحي (صندوق الوارد + POS) — والفشل بين المزودين يُدار داخل البوابة.
import { NextRequest, NextResponse } from 'next/server'
import { DatabaseSync } from 'node:sqlite'
import fs from 'fs'
import { chatWithFailover, type ChatMsg } from '@/lib/ai-gateway'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

const ROOT = 'G:\\ai\\Naggar Print POS Agent'
const POS_DB = process.env.NB2_POS_DB_PATH || 'G:\\ai\\Elnagar POS\\pos_data.db'

const AGENT_WS: Record<string, string> = {
  marwa: 'marwa_maestro',
  salma: 'salma_crm',
  fares: 'fares_cfo',
  bebo: 'bebo_production',
  sasa: 'sasa_devices',
  vision: 'vision_coder',
  koko: 'koko_marketing',
  hakim: 'hakim_advisor',
  afkar: 'afkar_ideas',
  rased: 'rased_sentinel',
}

/** سياق حي مختصر: صندوق وارد الوكلاء + حالة الإنتاج + العتاد + آخر POS (قراءة فقط) */
function buildLiveContext(): string {
  const parts: string[] = []
  try {
    const board = JSON.parse(fs.readFileSync(`${ROOT}\\workspaces\\bebo_production\\active_workspaces\\board_state.json`, 'utf8')) as Record<string, string>
    const rows = Object.entries(board).slice(0, 8).map(([id, st]) => `#${id}=${st}`)
    if (rows.length) parts.push(`طابور الإنتاج (بيبو): ${rows.join('، ')}`)
  } catch { /* لا ملف — نتجاهل */ }
  try {
    const hw = JSON.parse(fs.readFileSync(`${ROOT}\\workspaces\\sasa_devices\\active_workspaces\\hardware_state.json`, 'utf8')) as Record<string, unknown>
    const machines = Object.entries(hw)
      .filter(([, v]) => v && typeof v === 'object')
      .slice(0, 5)
      .map(([k, v]) => `${k}=${String((v as Record<string, unknown>).status ?? '؟')}`)
    if (machines.length) parts.push(`العتاد (صاصا): ${machines.join('، ')}`)
  } catch { /* نتجاهل */ }
  try {
    const db = new DatabaseSync(POS_DB, { readOnly: true })
    const orders = db.prepare('SELECT id, client_id, status, total_amount FROM orders ORDER BY id DESC LIMIT 5').all() as { id: number; client_id: number; status: string; total_amount: number }[]
    db.close()
    if (orders.length) {
      parts.push(`آخر طلبات POS: ${orders.map((o) => `#${o.id} ${o.status} (${Math.round(o.total_amount)}ج)`).join('، ')}`)
    }
  } catch { /* قاعدة غير متاحة — نتجاهل */ }
  try {
    const inboxes = ['bebo_production', 'salma_crm', 'koko_marketing', 'hakim_advisor']
    const counts: string[] = []
    for (const ws of inboxes) {
      const dir = `${ROOT}\\workspaces\\${ws}\\inbox_tasks`
      if (fs.existsSync(dir)) counts.push(`${ws.split('_')[0]}:${fs.readdirSync(dir).filter((f) => f.endsWith('.md')).length}`)
    }
    if (counts.length) parts.push(`صناديق الوارد: ${counts.join('، ')}`)
  } catch { /* نتجاهل */ }
  return parts.join('\n')
}

export async function POST(req: NextRequest) {
  let body: { agent?: unknown; messages?: unknown }
  try {
    body = (await req.json()) as { agent?: unknown; messages?: unknown }
  } catch {
    return NextResponse.json({ ok: false, reason: 'جسم الطلب غير صالح' }, { status: 400 })
  }
  const agent = typeof body.agent === 'string' && AGENT_WS[body.agent] ? AGENT_WS[body.agent] : 'marwa_maestro'
  const rawMsgs = Array.isArray(body.messages) ? body.messages : []
  const messages: ChatMsg[] = rawMsgs
    .filter((m): m is { role: string; content: string } =>
      typeof m === 'object' && m !== null && typeof (m as { content?: unknown }).content === 'string')
    .map((m): ChatMsg => ({
      role: m.role === 'assistant' ? 'assistant' : m.role === 'system' ? 'system' : 'user',
      content: (m.content || '').slice(0, 4000),
    }))
    .slice(-16)
  if (messages.length === 0) {
    return NextResponse.json({ ok: false, reason: 'لا رسائل' }, { status: 400 })
  }

  const agentName = Object.entries(AGENT_WS).find(([, ws]) => ws === agent)?.[0] ?? 'marwa'
  const system: ChatMsg = {
    role: 'system',
    content:
      `أنت «${agentName}» — وكيل في منظومة مروة كور لورشة النجار برنت. تجيب بالعامية المصرية باختصار ` +
      `ووضوح (3-6 جمل كحد أقصى) وتعمل بقرارات من البيانات الحية فقط — لا تخترع أرقاماً. ` +
      `السياق الحي من الورشة:\n${buildLiveContext()}`,
  }

  const result = await chatWithFailover(agent, [system, ...messages])
  return NextResponse.json(result)
}
