'use client'

// components/marwa/fares-dashboard.tsx — غرفة فارس CFO (وزير المالية ومدير الإمداد)
// المحطة التاسعة والأخيرة: الخزنة الحية، تقفيل الشيفت، المخزن التفاعلي، رادار المديونيات، وحاسبة صافي الربح.

import { useCallback, useEffect, useState } from 'react'
import {
  AlertTriangle,
  Banknote,
  CheckCircle2,
  Clock,
  Coins,
  Copy,
  DollarSign,
  ExternalLink,
  FileCheck,
  FileText,
  Lock,
  MessageSquare,
  Package,
  PackageMinus,
  RefreshCw,
  Send,
  ShieldAlert,
  Sparkles,
  TrendingDown,
  TrendingUp,
  Wallet,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

type FaresData = {
  vault: {
    cash_on_hand: number
    opening_balance: number
    today_revenue: number
    window_income: number
    window_expenses: number
    total_receivables: number
    under_prep_count: number
    under_prep_value: number
    last_movement: { id: number; date: string; type: string; amount: number; category: string } | null
  }
  debtors: { id: number; name: string; phone: string | null; balance: number; type: string }[]
  inventory: {
    items: {
      id: string
      code: string
      name: string
      category: string
      quantity: number
      unit: string
      min_stock: number
      unit_cost: number
      critical: boolean
      is_low: boolean
      used_for: string
    }[]
    critical_count: number
    updated_at: string
  }
  shifts: { filename: string; date: string; title: string }[]
}

const formatEGP = (n: number) => `${Math.round(n).toLocaleString('en-EG')} ج.م`

export function FaresDashboard() {
  const [data, setData] = useState<FaresData | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [flash, setFlash] = useState<string | null>(null)

  // تقفيل الشيفت
  const [closeModalOpen, setCloseModalOpen] = useState(false)
  const [closing, setClosing] = useState(false)
  const [shiftReport, setShiftReport] = useState<string | null>(null)

  // تذكير بالدفع لواتساب
  const [reminderModal, setReminderModal] = useState<{
    open: boolean
    client: string
    balance: number
    phone: string
    message: string
    waLink: string
  } | null>(null)
  const [generatingReminder, setGeneratingReminder] = useState(false)

  // حاسبة صافي الربح الفعلي
  const [calcSelling, setCalcSelling] = useState<number>(450)
  const [calcMaterial, setCalcMaterial] = useState<number>(180)
  const [calcMachine, setCalcMachine] = useState<number>(60)

  const loadData = useCallback(async () => {
    setRefreshing(true)
    try {
      const res = await fetch('/api/fares', { cache: 'no-store' })
      const j = (await res.json()) as FaresData
      if (res.ok) setData(j)
    } catch {
      setFlash('⚠️ تعذر الاتصال بمحرك فارس المالي')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    void loadData()
    const timer = setInterval(() => void loadData(), 45_000)
    return () => clearInterval(timer)
  }, [loadData])

  // تنفيذ تقفيل الشيفت
  async function handleCloseShift() {
    if (!data) return
    setClosing(true)
    try {
      const res = await fetch('/api/fares', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: 'close_shift',
          today_revenue: data.vault.today_revenue,
          cash_on_hand: data.vault.cash_on_hand,
          receivables: data.vault.total_receivables,
          expenses: data.vault.window_expenses,
        }),
      })
      const j = (await res.json()) as { ok?: boolean; message?: string; report?: string; file?: string }
      if (j.ok) {
        setShiftReport(j.report ?? null)
        setFlash(`✅ تم تقفيل الشيفت وتوليد التقرير: ${j.file}`)
        await loadData()
      } else {
        setFlash(`⚠️ فشل التقفيل: ${j.message}`)
      }
    } catch {
      setFlash('⚠️ حدث خطأ أثناء تقفيل الشيفت')
    } finally {
      setClosing(false)
      setCloseModalOpen(false)
    }
  }

  // توليد تذكير بالدفع
  async function handleGenerateReminder(client: { name: string; balance: number; phone: string | null }) {
    setGeneratingReminder(true)
    try {
      const res = await fetch('/api/fares', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: 'generate_whatsapp_reminder',
          client_name: client.name,
          balance: client.balance,
          phone: client.phone || '01000433420',
        }),
      })
      const j = (await res.json()) as { ok?: boolean; message: string; wa_link: string }
      if (j.ok) {
        setReminderModal({
          open: true,
          client: client.name,
          balance: client.balance,
          phone: client.phone || '01000433420',
          message: j.message,
          waLink: j.wa_link,
        })
      }
    } catch {
      setFlash('⚠️ تعذر توليد رسالة التذكير')
    } finally {
      setGeneratingReminder(false)
    }
  }

  // إشعار كوكو بوقف الإعلانات
  async function handleNotifyKoko(materialName: string) {
    try {
      const res = await fetch('/api/fares', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'notify_koko', material_name: materialName }),
      })
      const j = (await res.json()) as { ok?: boolean; message?: string }
      if (j.ok) {
        setFlash(`📢 تم إرسال أمر السلاش لكوكو بنجاح لإيقاف إعلانات «${materialName}»`)
      }
    } catch {
      setFlash('⚠️ تعذر إرسال الإشعار')
    }
  }

  // سحب خامات تجريبي
  async function handleConsume(matId: string) {
    try {
      const res = await fetch('/api/fares', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'consume_material', material_id: matId, qty: 1 }),
      })
      const j = (await res.json()) as { ok?: boolean; message?: string }
      if (j.ok) {
        setFlash(j.message ?? 'تم الخصم')
        await loadData()
      }
    } catch {
      setFlash('⚠️ تعذر تسجيل السحب')
    }
  }

  // حسابات صافي الربح الفعلي
  const totalCost = calcMaterial + calcMachine
  const netProfit = calcSelling - totalCost
  const profitMargin = calcSelling > 0 ? (netProfit / calcSelling) * 100 : 0

  if (loading && !data) {
    return (
      <div className="flex h-64 flex-col items-center justify-center gap-3 text-muted-foreground">
        <RefreshCw className="size-6 animate-spin text-primary" />
        <p className="text-sm">جارٍ قراءة الخزنة الحية والمخزون من الـ POS...</p>
      </div>
    )
  }

  const v = data?.vault

  return (
    <div className="space-y-6 p-4">
      {/* الترويسة الرئيسية */}
      <div className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-border bg-card/60 p-4 shadow-sm backdrop-blur">
        <div>
          <div className="flex items-center gap-2">
            <span className="flex size-7 items-center justify-center rounded-lg bg-emerald-500/10 text-emerald-400 font-bold">
              🛡️
            </span>
            <h2 className="text-lg font-bold text-foreground">غرفة فارس CFO — الخزنة المركزية وإدارة الإمداد</h2>
            <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[11px] font-medium text-emerald-400">
              قراءة حية (Live POS)
            </span>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            الربط المالي والمخزني المباشر بين الخزنة النقدية، طابور بيبو، ومستحقات العملاء.
          </p>
        </div>

        <div className="flex items-center gap-2">
          {flash && (
            <span className="animate-in fade-in rounded-lg bg-primary/10 px-3 py-1 text-xs text-primary font-medium">
              {flash}
            </span>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={() => void loadData()}
            disabled={refreshing}
            className="gap-1.5 text-xs"
          >
            <RefreshCw className={cn('size-3.5', refreshing && 'animate-spin')} />
            تحديث لحظي
          </Button>

          <Button
            variant="default"
            size="sm"
            onClick={() => setCloseModalOpen(true)}
            className="gap-1.5 bg-emerald-600 text-xs font-semibold hover:bg-emerald-700 text-white shadow"
          >
            <Lock className="size-3.5" />
            تقفيل الشيفت 🔐
          </Button>
        </div>
      </div>

      {/* 1️⃣ الخزنة الحية والأرقام المركزية */}
      <div>
        <div className="mb-3 flex items-center justify-between">
          <h3 className="flex items-center gap-2 text-sm font-semibold text-foreground">
            <Wallet className="size-4 text-emerald-400" />
            الخزنة النقدية المركزية
          </h3>
          <span className="text-[11px] text-muted-foreground">
            محسوب من البرنامج • رصيد افتتاحي 5,625 ج
          </span>
        </div>

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {/* كارت النقدية الحالية بالخزنة */}
          <div className="rounded-xl border border-emerald-500/30 bg-emerald-950/20 p-4 shadow-sm">
            <p className="flex items-center justify-between text-xs text-emerald-400 font-medium">
              <span>النقدية بالخزنة (Cash on Hand)</span>
              <Coins className="size-4" />
            </p>
            <p className="mt-2 text-2xl font-black text-emerald-300 tabular-nums">
              {formatEGP(v?.cash_on_hand ?? 0)}
            </p>
            <p className="mt-1 text-[11px] text-emerald-400/70">
              = رصيد افتتاحي + إيرادات − مصروفات
            </p>
          </div>

          {/* كارت إيرادات الوردية */}
          <div className="rounded-xl border border-border bg-card p-4 shadow-sm">
            <p className="flex items-center justify-between text-xs text-muted-foreground font-medium">
              <span>إيرادات الوردية الحالية</span>
              <TrendingUp className="size-4 text-sky-400" />
            </p>
            <p className="mt-2 text-2xl font-bold text-sky-400 tabular-nums">
              {formatEGP(v?.today_revenue ?? 0)}
            </p>
            <p className="mt-1 text-[11px] text-muted-foreground">
              مبيعات نقدية محصلة ومقبوضة
            </p>
          </div>

          {/* كارت الآجل المستحق بالسوق */}
          <div className="rounded-xl border border-amber-500/30 bg-amber-950/20 p-4 shadow-sm">
            <p className="flex items-center justify-between text-xs text-amber-400 font-medium">
              <span>إجمالي الآجل (ديون العملاء)</span>
              <DollarSign className="size-4" />
            </p>
            <p className="mt-2 text-2xl font-black text-amber-300 tabular-nums">
              {formatEGP(v?.total_receivables ?? 0)}
            </p>
            <p className="mt-1 text-[11px] text-amber-400/70">
              أصول ومستحقات معلقة بالسوق
            </p>
          </div>

          {/* كارت الأوردرات قيد التجهيز */}
          <div className="rounded-xl border border-border bg-card p-4 shadow-sm">
            <p className="flex items-center justify-between text-xs text-muted-foreground font-medium">
              <span>قيد التجهيز (عند بيبو)</span>
              <Clock className="size-4 text-purple-400" />
            </p>
            <p className="mt-2 text-2xl font-bold text-purple-400 tabular-nums">
              {v?.under_prep_count ?? 0} طلبات
            </p>
            <p className="mt-1 text-[11px] text-muted-foreground">
              بقيمة {formatEGP(v?.under_prep_value ?? 0)}
            </p>
          </div>
        </div>
      </div>

      {/* تقرير الشيفت المقفول في حال التقفيل اللحظي */}
      {shiftReport && (
        <div className="rounded-xl border border-emerald-500/40 bg-emerald-950/30 p-4 text-sm text-foreground">
          <div className="flex items-center justify-between border-b border-emerald-500/30 pb-2">
            <span className="font-bold text-emerald-400 flex items-center gap-2">
              <FileCheck className="size-4" />
              تم حفظ تقرير تقفيل الشيفت في أرشيف فارس
            </span>
            <Button variant="ghost" size="xs" onClick={() => setShiftReport(null)}>
              إخفاء
            </Button>
          </div>
          <pre className="mt-3 overflow-x-auto whitespace-pre-wrap font-sans text-xs text-emerald-200/90 leading-relaxed">
            {shiftReport}
          </pre>
        </div>
      )}

      {/* صف ثنائي: المخزن التفاعلي + حاسبة صافي الربح */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* 2️⃣ المخزن التفاعلي (Smart Inventory) — عمودين */}
        <div className="space-y-3 lg:col-span-2">
          <div className="flex items-center justify-between">
            <h3 className="flex items-center gap-2 text-sm font-semibold text-foreground">
              <Package className="size-4 text-sky-400" />
              المخزن التفاعلي وإدارة الخامات الأساسية
            </h3>
            {data?.inventory.critical_count ? (
              <span className="flex items-center gap-1 rounded-full border border-rose-500/40 bg-rose-500/10 px-2 py-0.5 text-xs font-semibold text-rose-400 animate-pulse">
                <AlertTriangle className="size-3" />
                {data.inventory.critical_count} خامات عند الحد الحرج
              </span>
            ) : (
              <span className="text-xs text-emerald-400">🟢 المخزون في الحدود الآمنة</span>
            )}
          </div>

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {data?.inventory.items.map((item) => {
              const isLow = item.quantity <= item.min_stock
              const ratio = Math.min(100, (item.quantity / (item.min_stock * 3)) * 100)

              return (
                <div
                  key={item.id}
                  className={cn(
                    'relative rounded-xl border p-3.5 transition-all shadow-sm',
                    isLow
                      ? 'border-rose-500/50 bg-rose-950/20 shadow-rose-950/20'
                      : 'border-border bg-card/60 hover:border-border/80',
                  )}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <span className="inline-block rounded bg-secondary px-1.5 py-0.5 text-[10px] text-muted-foreground">
                        {item.category}
                      </span>
                      <h4 className="mt-1 text-xs font-bold text-foreground">{item.name}</h4>
                    </div>

                    <div className="text-left">
                      <span
                        className={cn(
                          'text-base font-black tabular-nums',
                          isLow ? 'text-rose-400' : 'text-foreground',
                        )}
                      >
                        {item.quantity} {item.unit}
                      </span>
                      <p className="text-[10px] text-muted-foreground">حد أدنى: {item.min_stock}</p>
                    </div>
                  </div>

                  {/* شريط نسبة الرصيد */}
                  <div className="mt-2.5 h-1.5 w-full overflow-hidden rounded-full bg-secondary">
                    <div
                      className={cn('h-full transition-all', isLow ? 'bg-rose-500' : 'bg-sky-500')}
                      style={{ width: `${Math.max(8, ratio)}%` }}
                    />
                  </div>

                  <p className="mt-1.5 truncate text-[10px] text-muted-foreground">
                    التكلفة: {item.unit_cost} ج • الاستخدام: {item.used_for}
                  </p>

                  <div className="mt-3 flex items-center justify-between gap-2 border-t border-border/50 pt-2">
                    <Button
                      variant="ghost"
                      size="xs"
                      onClick={() => void handleConsume(item.id)}
                      className="gap-1 text-[11px] text-muted-foreground hover:text-foreground"
                    >
                      <PackageMinus className="size-3" />
                      سحب 1 {item.unit}
                    </Button>

                    {isLow && (
                      <Button
                        variant="destructive"
                        size="xs"
                        onClick={() => void handleNotifyKoko(item.name)}
                        className="gap-1 bg-rose-600 text-[10px] font-semibold text-white hover:bg-rose-700 shadow"
                      >
                        <ShieldAlert className="size-3" />
                        تنبيه كوكو بالسلاش 📢
                      </Button>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {/* 4️⃣ حاسبة صافي الربح الفعلي (Net Profit Engine) — عمود واحد */}
        <div className="space-y-3">
          <h3 className="flex items-center gap-2 text-sm font-semibold text-foreground">
            <Sparkles className="size-4 text-amber-400" />
            حاسبة صافي الربح الفعلي
          </h3>

          <div className="rounded-xl border border-border bg-card p-4 shadow-sm space-y-4">
            <div>
              <label className="text-xs text-muted-foreground">سعر البيع المقترح للعميل (ج.م)</label>
              <input
                type="number"
                value={calcSelling}
                onChange={(e) => setCalcSelling(Math.max(0, Number(e.target.value)))}
                className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-1.5 text-sm font-bold text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
              />
            </div>

            <div>
              <label className="text-xs text-muted-foreground">تكلفة الخامات من المخزن (ج.م)</label>
              <input
                type="number"
                value={calcMaterial}
                onChange={(e) => setCalcMaterial(Math.max(0, Number(e.target.value)))}
                className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-1.5 text-sm font-bold text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
              />
            </div>

            <div>
              <label className="text-xs text-muted-foreground">تكلفة وقت الماكينات والتشغيل (ج.م)</label>
              <input
                type="number"
                value={calcMachine}
                onChange={(e) => setCalcMachine(Math.max(0, Number(e.target.value)))}
                className="mt-1 w-full rounded-lg border border-border bg-background px-3 py-1.5 text-sm font-bold text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
              />
            </div>

            <div className="rounded-xl border border-border/80 bg-background/60 p-3 space-y-2">
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>التكلفة الإجمالية (COGS):</span>
                <span className="font-semibold text-foreground">{totalCost} ج.م</span>
              </div>
              <div className="flex justify-between text-sm font-bold">
                <span>صافي الربح الفعلي:</span>
                <span className={cn('tabular-nums', netProfit > 0 ? 'text-emerald-400' : 'text-rose-400')}>
                  {netProfit} ج.م
                </span>
              </div>
              <div className="flex justify-between items-center text-xs">
                <span className="text-muted-foreground">نسبة هامش الربح:</span>
                <span
                  className={cn(
                    'rounded px-1.5 py-0.5 font-bold',
                    profitMargin >= 35
                      ? 'bg-emerald-500/10 text-emerald-400'
                      : profitMargin >= 20
                      ? 'bg-amber-500/10 text-amber-400'
                      : 'bg-rose-500/10 text-rose-400',
                  )}
                >
                  {profitMargin.toFixed(1)}%
                  {profitMargin >= 35 ? ' (معتمد من حكيم ✓)' : ' (⚠️ هامش منخفض)'}
                </span>
              </div>
            </div>

            <p className="text-[10px] text-muted-foreground leading-relaxed">
              * قاعدة فارس وحكيم: أي أوردر يقل هامشه عن 35% يتم رفض الخصم عليه فوراً لحماية أرباح المطبعة.
            </p>
          </div>
        </div>
      </div>

      {/* 3️⃣ رادار المديونيات والأصول (Debt Radar) */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="flex items-center gap-2 text-sm font-semibold text-foreground">
            <DollarSign className="size-4 text-amber-400" />
            رادار المديونيات والأصول (Accounts Receivable)
          </h3>
          <span className="text-xs text-muted-foreground">
            {data?.debtors.length ?? 0} عملاء عليهم مبالغ مستحقة
          </span>
        </div>

        <div className="overflow-hidden rounded-xl border border-border bg-card shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full text-right text-xs">
              <thead className="border-b border-border bg-muted/40 text-muted-foreground">
                <tr>
                  <th className="p-3 font-semibold">رقم</th>
                  <th className="p-3 font-semibold">اسم العميل</th>
                  <th className="p-3 font-semibold">النوع</th>
                  <th className="p-3 font-semibold">المبلغ المستحق</th>
                  <th className="p-3 font-semibold">الهاتف</th>
                  <th className="p-3 text-left font-semibold">إجراء التحصيل السريع</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/60">
                {data?.debtors.map((d) => (
                  <tr key={d.id} className="hover:bg-muted/20 transition-colors">
                    <td className="p-3 font-mono text-muted-foreground">#{d.id}</td>
                    <td className="p-3 font-bold text-foreground">{d.name}</td>
                    <td className="p-3">
                      <span className="rounded bg-secondary px-1.5 py-0.5 text-[10px]">
                        {d.type || 'عميل'}
                      </span>
                    </td>
                    <td className="p-3 font-black text-rose-400 tabular-nums">
                      {formatEGP(d.balance)}
                    </td>
                    <td className="p-3 font-mono text-muted-foreground">
                      {d.phone || '01000433420'}
                    </td>
                    <td className="p-3 text-left">
                      <Button
                        variant="outline"
                        size="xs"
                        onClick={() => void handleGenerateReminder(d)}
                        disabled={generatingReminder}
                        className="gap-1 border-amber-500/30 text-amber-400 hover:bg-amber-500/10 font-semibold"
                      >
                        <MessageSquare className="size-3" />
                        إرسال تذكير بالدفع 💸
                      </Button>
                    </td>
                  </tr>
                ))}
                {!data?.debtors.length && (
                  <tr>
                    <td colSpan={6} className="p-6 text-center text-muted-foreground">
                      لا توجد مديونيات مسجلة حالياً — الخزنة مستقرة بالكامل!
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* نافذة تأكيد تقفيل الشيفت */}
      {closeModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="w-full max-w-md rounded-2xl border border-border bg-card p-6 shadow-2xl space-y-4">
            <div className="flex items-center gap-3">
              <span className="flex size-10 items-center justify-center rounded-xl bg-emerald-500/10 text-emerald-400 text-lg">
                🔐
              </span>
              <div>
                <h3 className="text-base font-bold text-foreground">تأكيد تقفيل شيفت الوردية</h3>
                <p className="text-xs text-muted-foreground">سيتم اعتماد الحسابات وتوليد تقرير الأرشيف</p>
              </div>
            </div>

            <div className="rounded-xl border border-border/80 bg-background/60 p-4 space-y-2 text-xs">
              <div className="flex justify-between">
                <span className="text-muted-foreground">إيرادات اليوم النقدية:</span>
                <span className="font-bold text-sky-400">{formatEGP(v?.today_revenue ?? 0)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">النقدية الفعلية بالخزنة:</span>
                <span className="font-bold text-emerald-400">{formatEGP(v?.cash_on_hand ?? 0)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">إجمالي ديون السوق (الآجل):</span>
                <span className="font-bold text-amber-400">{formatEGP(v?.total_receivables ?? 0)}</span>
              </div>
            </div>

            <p className="text-[11px] text-muted-foreground leading-relaxed">
              * سيتم إنشاء ملف رسمي باسم <code className="text-primary">shift_YYYY-MM-DD.md</code> في مجلد أرشيف فارس مع تصفير العداد لليوم التالي.
            </p>

            <div className="flex justify-end gap-2 pt-2">
              <Button variant="outline" size="sm" onClick={() => setCloseModalOpen(false)}>
                إلغاء
              </Button>
              <Button
                variant="default"
                size="sm"
                onClick={() => void handleCloseShift()}
                disabled={closing}
                className="bg-emerald-600 hover:bg-emerald-700 text-white font-bold gap-1.5"
              >
                {closing ? <RefreshCw className="size-3.5 animate-spin" /> : <CheckCircle2 className="size-3.5" />}
                تأكيد الإقفال والأرشفة
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* نافذة معاينة رسالة المطالبة بالدفع لواتساب */}
      {reminderModal && reminderModal.open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="w-full max-w-lg rounded-2xl border border-border bg-card p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="flex size-8 items-center justify-center rounded-lg bg-emerald-500/10 text-emerald-400">
                  💬
                </span>
                <div>
                  <h3 className="text-sm font-bold text-foreground">رسالة مطالبة ذكية — {reminderModal.client}</h3>
                  <p className="text-[11px] text-muted-foreground">المبلغ المستحق: {formatEGP(reminderModal.balance)}</p>
                </div>
              </div>
              <Button variant="ghost" size="xs" onClick={() => setReminderModal(null)}>
                إغلاق
              </Button>
            </div>

            <div className="rounded-xl border border-border bg-background p-3.5 text-xs text-foreground leading-relaxed whitespace-pre-wrap font-sans">
              {reminderModal.message}
            </div>

            <div className="flex items-center justify-between gap-2 pt-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  void navigator.clipboard.writeText(reminderModal.message)
                  setFlash('📋 تم نسخ الرسالة إلى الحافظة')
                }}
                className="gap-1.5 text-xs"
              >
                <Copy className="size-3.5" />
                نسخ الرسالة
              </Button>

              <a
                href={reminderModal.waLink}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3.5 py-2 text-xs font-bold text-white hover:bg-emerald-700 shadow"
              >
                <Send className="size-3.5" />
                إرسال لواتساب العميل الآن
              </a>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
