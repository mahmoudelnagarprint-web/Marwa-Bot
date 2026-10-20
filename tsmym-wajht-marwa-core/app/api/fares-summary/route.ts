// app/api/fares-summary/route.ts — الأرقام الحية الرسمية لفارس (MARWA CORE task-2)
//
// الخط الأحمر (الميثاق + أمر المالك): القاعدة الحية G:\ai\Elnagar POS\pos_data.db
// تُقرأ بوضع قراءة فقط إلزامي — node:sqlite مع readOnly:true ثم file-URI ?mode=ro
// كطبقة تحقق إضافية. لا يوجد أي INSERT/UPDATE/COMMIT في هذا الملف إطلاقاً.
//
// التعريفات الملزمة (FARES_CFO_STATE.md §6 + §9):
//   الآجل   = مجموع أرصدة العملاء الموجبة فقط
//   المعلق  = الآجل + قيمة كل طلبات قيد التجهيز
//   دخل النافذة = مجموع حركات Income من accounting_start_date (جدول settings)
//   الخزنة  = رصيد افتتاحي معتمد (§9) + دخل النافذة − مصروفات النافذة
//
// الأولوية: يجرب أولاً API الورشة 127.0.0.1:7777 (تعليمات المالك) — وهو لا يوفر
// نافذة أكتوبر ولا الافتتاحي، لذا الأرقام الرسمية لفارس تُحسب من القاعدة مباشرة،
// وتُمرر حالة وصول الـ7777 كحقل مساعد فقط.

import { DatabaseSync } from 'node:sqlite'
import { FARES_BASELINE, type FaresSummary } from '@/lib/live'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

const DB_PATH = 'G:\\ai\\Elnagar POS\\pos_data.db'
const WORKSHOP_API = 'http://127.0.0.1:7777/api/dashboard-summary'
/** رصيد افتتاحي 5,625 — معتمد بأمر المالك، موثق §9 (مشتق من أرشفة ما قبل 2026-10-01) */
const OPENING_BALANCE = 5625
const OPENING_SOURCE = 'رصيد افتتاحي معتمد بأمر المالك — FARES_CFO_STATE §9 (2026-10-19)'

type WorkshopProbe = {
  reachable: boolean
  error?: string
  orders_total?: number
}

async function probeWorkshopApi(): Promise<WorkshopProbe> {
  try {
    const res = await fetch(WORKSHOP_API, {
      cache: 'no-store',
      signal: AbortSignal.timeout(2000),
    })
    if (!res.ok) return { reachable: false, error: `HTTP ${res.status}` }
    const json = (await res.json()) as {
      success?: boolean
      dashboard_summary?: { orders_total?: number }
    }
    if (!json?.success) return { reachable: false, error: 'success:false' }
    return { reachable: true, orders_total: json.dashboard_summary?.orders_total }
  } catch (e) {
    return { reachable: false, error: e instanceof Error ? e.message : String(e) }
  }
}

/** فتح القاعدة بقراءة فقط مزدوجة: readOnly:true + URI mode=ro */
function openReadOnly(): DatabaseSync {
  const uri = `file:${DB_PATH.replace(/\\/g, '/')}?mode=ro`
  try {
    return new DatabaseSync(uri, { readOnly: true })
  } catch {
    // بعض إصدارات node:sqlite لا تفعّل SQLITE_OPEN_URI — readOnly:true وحده
    // يمنع أي كتابة على مستوى محرك SQLite (SQLITE_OPEN_READONLY).
    return new DatabaseSync(DB_PATH, { readOnly: true })
  }
}

export async function GET() {
  const notes: string[] = []
  const workshop = await probeWorkshopApi()

  let db: DatabaseSync
  try {
    db = openReadOnly()
  } catch (e) {
    return Response.json(
      {
        success: false,
        error: `تعذر فتح القاعدة الحية بوضع قراءة فقط: ${e instanceof Error ? e.message : String(e)}`,
      },
      { status: 500 },
    )
  }

  try {
    // نافذة المحاسبة الرسمية — من settings، لا تُرمّز ثابتة أبداً
    const startRow = db
      .prepare("SELECT value FROM settings WHERE key = 'accounting_start_date' LIMIT 1")
      .get() as { value?: string } | undefined
    const windowStart = startRow?.value ?? '2026-10-01'
    if (!startRow?.value) {
      notes.push('مفتاح accounting_start_date غير موجود في settings — استُخدم 2026-10-01 (افتراضي §9)')
    }

    const income = db
      .prepare(
        "SELECT IFNULL(SUM(amount),0) AS v FROM transactions WHERE type='Income' AND date >= ?",
      )
      .get(windowStart) as { v: number }
    const expenses = db
      .prepare(
        "SELECT IFNULL(SUM(amount),0) AS v FROM transactions WHERE type='Expense' AND date >= ?",
      )
      .get(windowStart) as { v: number }

    const receivablesRow = db
      .prepare(
        'SELECT IFNULL(SUM(balance),0) AS total, COUNT(*) AS cnt FROM clients WHERE balance > 0',
      )
      .get() as { total: number; cnt: number }
    const receivablesDetail = db
      .prepare(
        'SELECT id, TRIM(name) AS name, balance FROM clients WHERE balance > 0 ORDER BY balance DESC LIMIT 12',
      )
      .all() as { id: number; name: string; balance: number }[]

    const underPrep = db
      .prepare(
        "SELECT COUNT(*) AS cnt, IFNULL(SUM(total_amount),0) AS val FROM orders WHERE status IN ('Under Preparation','pending','processing','تحت التجهيز')",
      )
      .get() as { cnt: number; val: number }

    const lastMovement = db
      .prepare('SELECT id, date, type, amount FROM transactions ORDER BY id DESC LIMIT 1')
      .get() as { id: number; date: string; type: string; amount: number } | undefined

    const incomeWindow = income?.v ?? 0
    const expensesWindow = expenses?.v ?? 0
    const receivables = receivablesRow?.total ?? 0

    const summary: FaresSummary = {
      generated_at: new Date().toISOString(),
      window_start: windowStart,
      opening_balance: OPENING_BALANCE,
      opening_balance_source: OPENING_SOURCE,
      income_window: incomeWindow,
      expenses_window: expensesWindow,
      cash_on_hand: OPENING_BALANCE + incomeWindow - expensesWindow,
      receivables,
      receivables_detail: receivablesDetail,
      debt_clients_count: receivablesRow?.cnt ?? 0,
      under_preparation: { count: underPrep?.cnt ?? 0, value: underPrep?.val ?? 0 },
      pending_total: receivables + (underPrep?.val ?? 0),
      last_movement: lastMovement ?? null,
      source: workshop.reachable
        ? 'pos-db-ro (read-only) + workshop-api 7777 متصل'
        : 'pos-db-ro (read-only) — workshop-api 7777 غير متصل',
      workshop_api: workshop,
      notes,
      baseline: FARES_BASELINE,
    }

    return Response.json(summary, { headers: { 'Cache-Control': 'no-store' } })
  } catch (e) {
    return Response.json(
      {
        success: false,
        error: `فشل حساب الأرقام الحية: ${e instanceof Error ? e.message : String(e)}`,
      },
      { status: 500 },
    )
  } finally {
    try {
      db.close()
    } catch {
      /* تجاهل — الإغلاق لا يكتب شيئاً */
    }
  }
}
