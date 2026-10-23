import { NextResponse } from 'next/server'
import { executePosQuery } from '@/lib/agent-intelligence'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

function cairoDay(date = new Date()): string {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Africa/Cairo', year: 'numeric', month: '2-digit', day: '2-digit',
  }).formatToParts(date)
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]))
  return `${values.year}-${values.month}-${values.day}`
}

type Finding = {
  agent_id: string
  kind: 'suggestion'
  title: string
  body: string
  severity: 'منخفض'
  status: 'pending'
  decided_by: null
  op_id: string
  payload: { category: string; actions: { type: string; label: string; href: string }[] }
}

/** Read-only pulse. The browser persists returned suggestions through its existing anon client. */
export async function POST() {
  const day = cairoDay()
  const findings: Finding[] = []
  const debts = executePosQuery(
    'SELECT COUNT(*) AS client_count, COALESCE(SUM(balance), 0) AS total_balance FROM clients WHERE balance > 0',
  )
  if (debts.ok) {
    const row = (debts.data?.[0] || {}) as { client_count?: number; total_balance?: number }
    const count = Number(row.client_count || 0)
    const total = Number(row.total_balance || 0)
    if (count > 0 && total > 0) {
      findings.push({
        agent_id: 'fares', kind: 'suggestion',
        title: 'مراجعة أرصدة العملاء القائمة',
        body: `• من قراءة قاعدة البرنامج: يوجد ${count} عميلًا بأرصدة موجبة مجموعها ${total.toLocaleString('ar-EG')} جنيه.\n• ده رصد للأرصدة فقط، مش حكم إنها متأخرة؛ راجع كشف الحساب قبل أي متابعة أو إجراء.`,
        severity: 'منخفض', status: 'pending', decided_by: null,
        op_id: `heartbeat:${day}:client-balances`,
        payload: { category: 'fares', actions: [{ type: 'navigate', label: 'فتح غرفة فارس', href: '/agent/fares' }] },
      })
    }
  }

  const overdue = executePosQuery(
    "SELECT COUNT(*) AS order_count FROM orders WHERE delivery_date IS NOT NULL AND TRIM(delivery_date) <> '' AND date(delivery_date) < date('now','localtime') AND status NOT IN ('Delivered','Cancelled','تم التسليم','ملغي')",
  )
  if (overdue.ok) {
    const row = (overdue.data?.[0] || {}) as { order_count?: number }
    const count = Number(row.order_count || 0)
    if (count > 0) {
      findings.push({
        agent_id: 'salma', kind: 'suggestion',
        title: 'مراجعة طلبات تجاوزت تاريخ التسليم',
        body: `• فحص القراءة فقط رصد ${count} طلبًا تاريخ تسليمه أقدم من اليوم وحالته غير مسلّمة.\n• راجع حالة كل طلب في البرنامج قبل التواصل مع أي عميل.`,
        severity: 'منخفض', status: 'pending', decided_by: null,
        op_id: `heartbeat:${day}:late-orders`,
        payload: { category: 'salma', actions: [{ type: 'navigate', label: 'فتح غرفة سلمى', href: '/agent/salma' }] },
      })
    }
  }

  return NextResponse.json({
    ok: debts.ok || overdue.ok,
    scanned_at: new Date().toISOString(),
    timezone: 'Africa/Cairo',
    findings,
    checks: { balances: debts.ok ? 'ok' : 'unavailable', delivery_dates: overdue.ok ? 'ok' : 'unavailable' },
  }, { headers: { 'Cache-Control': 'no-store' } })
}
