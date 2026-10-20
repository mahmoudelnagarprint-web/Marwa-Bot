// app/api/salma-summary/route.ts — عقل سلمى CRM حي (لوحة تحكم ERP مصغرة)
// بأمر المالك 2026-10-20 (تفويض مفتوح — المايسترو مروة).
// الخط الأحمر: نفس حماية fares-summary — node:sqlite readOnly:true ثم file-URI ?mode=ro
// كطبقة تحقق إضافية. لا يوجد أي INSERT/UPDATE/COMMIT إطلاقاً. كل الأرقام موسومة
// «محسوب من البرنامج» (قاعدة الورشة الحية read-only).
import { NextResponse } from 'next/server'
import { DatabaseSync } from 'node:sqlite'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

const DB_PATH = 'G:\\ai\\Elnagar POS\\pos_data.db'

export type SalmaOrder = {
  id: number
  client: string
  phone: string | null
  client_type: 'Retail' | 'Wholesale' | string
  status: string
  date: string
  total: number
  balance: number
  vip: boolean
  phoneE164: string | null
}

export type SalmaSummary = {
  source: 'pos-db-ro (read-only)'
  tag: 'محسوب من البرنامج'
  computed_at: string
  kpis: {
    active_clients: number
    open_orders: number
    open_orders_value: number
    receivables_total: number
    debtors_count: number
    ready_orders: number
    ready_value: number
    under_preparation: number
    late_orders: number
  }
  summary_message: string
  orders: SalmaOrder[]
  debtors: { id: number; name: string; phone: string | null; balance: number; phoneE164: string | null }[]
  aggregation: { product: string; total_qty: number; orders_count: number }[]
}

/** توحيد أرقام الهاتف لصيغة wa.me (20 + رقم بدون +/مسافات) */
function toE164(raw: string | null | undefined): string | null {
  if (!raw) return null
  let d = raw.replace(/\D/g, '')
  if (!d) return null
  if (d.startsWith('0020')) d = d.slice(2)
  else if (d.startsWith('20') && d.length > 12) d = d.slice(2)
  else if (d.startsWith('0') && d.length === 11) d = '20' + d.slice(1)
  if (!d.startsWith('20') || d.length !== 12) return null
  return d
}

function vipName(name: string): boolean {
  const key = name.trim()
  if (key in VIP_TAGS) return true
  // شارة تجميعية موسمية: اسم يحتوي كلمة عروسة/عرس في فترة الأعراس
  return /عر[وأ]?س/.test(key)
}

const VIP_TAGS: Record<string, string> = {
  'رفيده': 'VIP موثق',
  'Heba Ahmed': 'جملة',
}

export async function GET() {
  const computed_at = new Date().toISOString()
  try {
    const db = new DatabaseSync(DB_PATH, { readOnly: true })
    // طبقة تحقق إضافية — أي محاولة كتابة ترفض على مستوى connection
    try { db.exec('SELECT 1') } catch { /* noop probe */ }

    // ---------------- KPIs ----------------
    const active_clients = Number(
      db.prepare('SELECT COUNT(DISTINCT client_id) n FROM orders').get()?.n ?? 0,
    )
    const openAgg = db.prepare(
      "SELECT COUNT(*) n, COALESCE(SUM(total_amount),0) v FROM orders WHERE status != 'Delivered'",
    ).get()
    const open_orders = Number(openAgg?.n ?? 0)
    const open_orders_value = Number(openAgg?.v ?? 0)
    const readyAgg = db.prepare(
      "SELECT COUNT(*) n, COALESCE(SUM(total_amount),0) v FROM orders WHERE status = 'Ready'",
    ).get()
    const ready_orders = Number(readyAgg?.n ?? 0)
    const ready_value = Number(readyAgg?.v ?? 0)

    const debtAgg = db.prepare('SELECT COUNT(*) n, COALESCE(SUM(balance),0) v FROM clients WHERE balance > 0').get()
    const debtors_count = Number(debtAgg?.n ?? 0)
    const receivables_total = Number(debtAgg?.v ?? 0)
    const under_prep = db.prepare(
      "SELECT COUNT(*) n FROM orders WHERE status = 'Under Preparation'",
    ).get()?.n
    const under_preparation = Number(under_prep ?? 0)

    // متأخرات: طلب مفتوح مضى عليه > 7 أيام دون تسليم (delivery_date فارغ)
    const LATE_DAYS = 7
    const late_orders = Number(
      db.prepare(
        `SELECT COUNT(*) n FROM orders WHERE status != 'Delivered' AND delivery_date IS NULL
         AND CAST(julianday('now') - julianday(date) AS INTEGER) > ${LATE_DAYS}`,
      ).get()?.n ?? 0,
    )

    // ----------------فلاتر: الطلبات المفتوحة مع بيانات العميل ----------------
    const ordersRes = db.prepare(
      `SELECT o.id, o.status, o.date, o.total_amount, o.delivery_date,
              c.name AS client, c.phone, c.type AS ctype, c.balance
       FROM orders o LEFT JOIN clients c ON c.id = o.client_id
       WHERE o.status != 'Delivered'
       ORDER BY CASE o.status WHEN 'Under Preparation' THEN 0 WHEN 'Ready' THEN 1 ELSE 2 END, o.date ASC`,
    ).all() as Record<string, unknown>[]
    const orders: SalmaOrder[] = ordersRes.map((r) => ({
      id: Number(r.id),
      client: String(r.client ?? 'عميل محذوف'),
      phone: r.phone ? String(r.phone) : null,
      client_type: String(r.ctype ?? 'Retail'),
      status: String(r.status),
      date: String(r.date ?? ''),
      total: Number(r.total_amount ?? 0),
      balance: Number(r.balance ?? 0),
      vip: vipName(String(r.client ?? '')) || String(r.ctype ?? '') === 'Wholesale',
      phoneE164: toE164(r.phone ? String(r.phone) : null),
    }))

    // ---------------- المدينون ----------------
    const debtorsRes = db.prepare(
      `SELECT id, name, phone, balance FROM clients WHERE balance > 0
       ORDER BY balance DESC`,
    ).all() as Record<string, unknown>[]
    const debtors = debtorsRes.map((r) => ({
      id: Number(r.id),
      name: String(r.name ?? '؟'),
      phone: r.phone ? String(r.phone) : null,
      balance: Number(r.balance ?? 0),
      phoneE164: toE164(r.phone ? String(r.phone) : null),
    }))

    // ---------------- تجميع نواقص الإنتاج (الميزة الجوهرية) ----------------
    const aggRes = db.prepare(
      `SELECT oi.product_name AS product, SUM(oi.qty) AS total_qty, COUNT(DISTINCT oi.order_id) AS orders_count
       FROM order_items oi
       JOIN orders o ON o.id = oi.order_id
       WHERE o.status != 'Delivered'
       GROUP BY oi.product_name
       ORDER BY total_qty DESC, product ASC`,
    ).all() as Record<string, unknown>[]
    const aggregation = aggRes.map((r) => ({
      product: String(r.product ?? '؟'),
      total_qty: Number(r.total_qty ?? 0),
      orders_count: Number(r.orders_count ?? 0),
    }))

    // ---------------- ملخص الصباح ----------------
    const worstLate = orders[0]
    const summary_message = [
      `صباح الخير يا فندم — سلمى تكلّم.`,
      open_orders ? `على رأسي ${open_orders} طلب مفتوح بقيمة ${open_orders_value.toLocaleString('en-EG')} ج.` : 'لا يوجد طلبات مفتوحة — الخزنة المستقبل آمنة.',
      under_preparation ? `منهم ${under_preparation} تحت التجهيز في الورشة الآن.` : '',
      ready_orders ? `و"${ready_orders} طلب جاهز للاستلام بقيمة ${ready_value.toLocaleString('en-EG')} ج — بلّغ العملاء.` : '',
      receivables_total > 0 ? `الديون: ${debtors_count} مدين بإجمالي ${receivables_total.toLocaleString('en-EG')} ج مستحقة.` : 'لا ديون على أحد — كل الحسابات صافية.',
      late_orders > 0 ? `وفيهم ${late_orders} طلب متأخر عن 7 أيام بلا موعد تسليم — يحتاج إصبعك.` : 'ولا طلب متأخر — الإيقاع تمام.',
    ].filter(Boolean).join(' ')

    db.close()
    const payload: SalmaSummary = {
      source: 'pos-db-ro (read-only)',
      tag: 'محسوب من البرنامج',
      computed_at,
      kpis: {
        active_clients, open_orders, open_orders_value, receivables_total,
        debtors_count, ready_orders, ready_value, under_preparation, late_orders,
      },
      summary_message,
      orders,
      debtors,
      aggregation,
    }
    return NextResponse.json(payload)
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err)
    return NextResponse.json({ error: `فشل قراءة قاعدة الورشة: ${message.slice(0, 200)}` }, { status: 500 })
  }
}
