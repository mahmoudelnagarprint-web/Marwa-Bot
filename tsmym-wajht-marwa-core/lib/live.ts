// lib/live.ts — طبقة البيانات الحية (MARWA CORE — task-2 فيجن)
// جميع الأرقام المالية تأتي من app/api/fares-summary (Route Handler) الذي يقرأ
// القاعدة الحية G:\ai\Elnagar POS\pos_data.db بوضع قراءة فقط إلزامي (readOnly
// + file URI mode=ro) — ممنوع منعاً باتاً أي كتابة على القاعدة (خط أحمر من الميثاق).
//
// خط الأساس 1,755 / 790 / 7,380 معتمد بأمر المالك (FARES_CFO_STATE.md §9 — 2026-10-19).
// الأرقام المعروضة دائماً = الحي المحسوب، وخط الأساس يظهر فقط كمقارنة فرق.

export const LIVE_TAG = 'محسوب من البرنامج'

export type Baseline = {
  /** دخل أكتوبر 1,755 ج — خط الأساس المعتمد بأمر المالك §9 (نافذة 2026-10-01) */
  income: number
  /** الآجل الحقيقي 790 ج (أرصدة موجبة فقط) — §9 */
  receivables: number
  /** الخزنة 7,380 = 5,625 افتتاحي + 1,755 — §9 */
  cash: number
}

export type ReceivableItem = {
  id: number
  name: string
  balance: number
}

export type FaresSummary = {
  generated_at: string
  /** نافذة المحاسبة الرسمية — مفتاح accounting_start_date من جدول settings */
  window_start: string
  /** رصيد افتتاحي معتمد بأمر المالك (§9) — ليس رقماً وهمياً بل خط أساس موثق */
  opening_balance: number
  opening_balance_source: string
  /** مجموع حركات Income من بداية النافذة */
  income_window: number
  /** مجموع حركات Expense من بداية النافذة */
  expenses_window: number
  /** الخزنة = افتتاحي + دخل − مصروف */
  cash_on_hand: number
  /** الآجل = مجموع أرصدة العملاء الموجبة فقط (تعريف فارس الملزم) */
  receivables: number
  receivables_detail: ReceivableItem[]
  debt_clients_count: number
  /** قيد التجهيز (المعلق التشغيلي): عدد وقيمة الطلبات غير المسلَّمة */
  under_preparation: { count: number; value: number }
  /** المعلق بالتعريف المعتمد = الآجل + قيمة طلبات قيد التجهيز */
  pending_total: number
  /** آخر حركة مالية بالقاعدة (id + التاريخ) */
  last_movement: { id: number; date: string; type: string; amount: number } | null
  /** مصدر الأرقام: القاعدة الحية read-only و/أو API الورشة 7777 */
  source: string
  workshop_api: { reachable: boolean; error?: string; orders_total?: number }
  notes: string[]
  baseline: Baseline
}

export type FaresSummaryResponse =
  | { ok: true; summary: FaresSummary }
  | { success: false; error: string }

export const FARES_BASELINE: Baseline = {
  income: 1755,
  receivables: 790,
  cash: 7380,
}

/** تنسيق جنيه مصري 2,305.00 */
export function formatEGP(n: number): string {
  return n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

/** طابع زمني بتوقيت القاهرة */
export function formatCairoTime(iso?: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  return new Intl.DateTimeFormat('ar-EG', {
    timeZone: 'Africa/Cairo',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    day: '2-digit',
    month: '2-digit',
  }).format(d)
}

/** جلب الملخص المالي الحي لفارس من الطبقة الحية */
export async function fetchFaresSummary(): Promise<FaresSummary> {
  const res = await fetch('/api/fares-summary', { cache: 'no-store' })
  if (!res.ok) {
    throw new Error(`fares-summary HTTP ${res.status}`)
  }
  const json = (await res.json()) as FaresSummary
  return json
}
