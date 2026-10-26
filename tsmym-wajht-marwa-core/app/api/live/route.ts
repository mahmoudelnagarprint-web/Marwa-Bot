// app/api/live/route.ts — فحص الاتصال الحقيقي بالطبقة الحية (تطهير 2026-10-25)
// بديل مؤشر النبض المزيف: يفتح القاعدة الحية readOnly ويتأكد أن الملفات موجودة —
// يعيد الحالة الفعلية فقط، بلا أي عدادات متحركة في الواجهة.
import { NextResponse } from 'next/server'
import { DatabaseSync } from 'node:sqlite'
import fs from 'fs'
import path from 'path'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

const DB_PATH = process.env.NB2_POS_DB_PATH || 'G:\\ai\\Elnagar POS\\pos_data.db'
const WORKSPACE_ROOT =
  process.env.WORKSPACE_ROOT?.replace(/\\system_engine$/, '') || 'G:\\ai\\Naggar Print POS Agent\\workspaces'
const HW_STATE = path.join(WORKSPACE_ROOT, 'sasa_devices', 'active_workspaces', 'hardware_state.json')

export async function GET() {
  const t0 = Date.now()
  let dbOk = false
  let dbError: string | null = null
  let db: DatabaseSync | null = null
  try {
    if (!fs.existsSync(DB_PATH)) throw new Error('ملف القاعدة غير موجود')
    db = new DatabaseSync(DB_PATH, { readOnly: true })
    db.prepare('SELECT 1').get()
    dbOk = true
  } catch (e) {
    dbError = e instanceof Error ? e.message : String(e)
  } finally {
    if (db) { try { db.close() } catch { /* تجاهل */ } }
  }

  let hwFresh = false
  let hwUpdatedAt: string | null = null
  try {
    const raw = fs.readFileSync(HW_STATE, 'utf8')
    const hw = JSON.parse(raw) as { updated_at?: string }
    hwUpdatedAt = hw.updated_at ?? null
    hwFresh = hwUpdatedAt ? Date.now() - new Date(hwUpdatedAt).getTime() < 120_000 : false
  } catch { /* لا ملف — الدايمون غير شغال */ }

  return NextResponse.json(
    {
      ok: dbOk,
      db_ok: dbOk,
      db_error: dbError,
      hardware_daemon: { fresh: hwFresh, updated_at: hwUpdatedAt },
      latency_ms: Date.now() - t0,
      ts: new Date().toISOString(),
    },
    { headers: { 'Cache-Control': 'no-store' } },
  )
}
