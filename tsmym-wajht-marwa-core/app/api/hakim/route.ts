// app/api/hakim/route.ts — حكيم المستشار التنفيذي ⚖️ (2026-10-20)
// الخطوط الحمراء: pos_data.db قراءة فقط. عقود حكيم في active_workspaces الخاصة به.
// رادار الاختناقات يقرأ في صمت من ملفات حالة بيبو/صاصا/سلمى.
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
const HAKIM_WS = path.join(WORKSPACE_ROOT, 'hakim_advisor')
const DOCS_DIR = path.join(HAKIM_WS, 'active_workspaces')
const BOARD_FILE = path.join(WORKSPACE_ROOT, 'bebo_production', 'active_workspaces', 'board_state.json')
const HW_STATE = path.join(WORKSPACE_ROOT, 'sasa_devices', 'active_workspaces', 'hardware_state.json')
const ENGINE = path.join(WORKSPACE_ROOT, 'system_engine', 'router_daemon.py')
const PYTHON = process.env.PYTHON_EXE || 'G:\\ai\\Naggar Print POS Agent\\.venv\\Scripts\\python.exe'
const DB_PATH = 'G:\\ai\\Elnagar POS\\pos_data.db'

export type Bottleneck = { code: string; level: 'red' | 'amber' | 'ok'; message: string }
export type Quotation = { id: string; client: string; items: string; cost: number; margin_pct: number; price: number; created_at: string }

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

/* ---------- 2️⃣ رادار الاختناقات (مهام راصد) — قراءة صامتة من ملفات الحالة ---------- */
function readBoard(): string[] {
  try {
    const j = JSON.parse(fs.readFileSync(BOARD_FILE, 'utf8')) as Record<string, string>
    return Object.entries(j).map(([k, v]) => `${k}:${v}`)
  } catch {
    return []
  }
}

function readHardware(): { epson?: { state?: string; online?: boolean }; laser?: { state?: string }; cutter?: { state?: string } } | null {
  try {
    return JSON.parse(fs.readFileSync(HW_STATE, 'utf8'))
  } catch {
    return null
  }
}

function analyzeBottlenecks(board: string[], hw: ReturnType<typeof readHardware>): Bottleneck[] {
  const b: Bottleneck[] = []
  const printing = board.filter((x) => x.endsWith(':printing')).length
  const design = board.filter((x) => x.endsWith(':design')).length
  const ready = board.filter((x) => x.endsWith(':ready')).length
  const laserState = hw?.laser?.state
  // قاعدة الاختناق للمالك: >5 في طابور بيبو بينما ليزر صاصا فارغ
  if (printing > 5 && laserState === 'idle') {
    b.push({ code: 'production_flood', level: 'red', message: `⚠️ تحذير استراتيجي: اختناق في قسم التجهيز — ${printing} طلبات في طابور بيبو بينما الليزر فارغ عند صاصا. يرجى توجيه بيبو لإعادة توزيع المهام على الليزر فوراً.` })
  } else if (printing > 8) {
    b.push({ code: 'spooler_pressure', level: 'amber', message: `🟠 ضغط على طابور التشغيل — ${printing} طلبات قيد التنفيذ. راقب الإنجاز.` })
  }
  if (design > 6) {
    b.push({ code: 'design_backlog', level: 'amber', message: `🟠 تراكم تصميم — ${design} طلبات في مرحلة التصميم (زينب). اعتبر تدعيم الخط.` })
  }
  if (ready > 20) {
    b.push({ code: 'ready_pile', level: 'amber', message: `🟠 ${ready} طلبات جاهزة بلا تسليم — اربطها بتسليمات سلمى.` })
  }
  if (hw?.epson?.online && hw.epson.state === 'error') {
    b.push({ code: 'epson_fault', level: 'red', message: '🚨 طابعة الإبسون في حالة خطأ (من العتاد الحقيقي) — تدخل فوري في صاصا.' })
  }
  if (b.length === 0) b.push({ code: 'ok', level: 'ok', message: '✅ المنظومة متوازنة — لا اختناقات الحالية' })
  return b
}

/* ---------- 1️⃣ حاسبة التسعير الذكية — خامات + وقت ماكينة → عرض سعر ---------- */
const MACHINE_RATE = { 'ليزر CO2': 60, 'Epson L1800': 45, 'كاتر بلوتر': 40, 'يدوي/تجميع': 25 } // ج.م/ساعة تقديرية

function makeQuotation(client: string, items: string, materials_cost: number, machine: keyof typeof MACHINE_RATE, hours: number, margin_pct = 30): Quotation {
  const machine_cost = MACHINE_RATE[machine] * hours
  const cost = materials_cost + machine_cost
  const price = Math.round(cost * (1 + margin_pct / 100))
  const id = `Q-${new Date().toISOString().slice(0, 10).replace(/-/g, '')}-${Math.floor(Math.random() * 90 + 10)}`
  const q: Quotation = { id, client, items, cost, margin_pct, price, created_at: new Date().toISOString() }
  // أرشفة في active_workspaces الخاصة بحكيم
  try {
    fs.mkdirSync(DOCS_DIR, { recursive: true })
    fs.writeFileSync(
      path.join(DOCS_DIR, `${id}.md`),
      `# عرض سعر رسمي ${id}\n\n- **العميل**: ${client}\n- **البنود**: ${items}\n- **الماكينة**: ${machine} × ${hours} ساعة\n- **كلفة الخامات**: ${materials_cost} ج.م\n- **كلفة الماكينة**: ${machine_cost} ج.م\n- **إجمالي التكلفة**: ${cost} ج.م (محسوب من البرنامج)\n- **هامش الربح**: ${margin_pct}%\n- **السعر النهائي**: ${price} ج.م\n- **التاريخ**: ${q.created_at}\n\n> رقم البزنس الرسمي: 01000433420 — الورشة: البرج التلي (النجار برنت)\n`,
      'utf8',
    )
  } catch { /* الفشل في الأرشفة لا يعطل الرد */ }
  return q
}

/* ---------- 4️⃣ المحاكي الاستراتيجي — أرقام من مبيعات سلمى (POS قراءة فقط) ---------- */
function simulateWhatIf(discount_pct = 15, uplift_factor = 1.35, horizon_days = 30): Record<string, number | string> {
  try {
    const db = new DatabaseSync(DB_PATH, { readOnly: true })
    const row = db.prepare(
      "SELECT COUNT(*) n, COALESCE(SUM(total_amount),0) rev FROM orders WHERE date >= datetime('now', ?)",
    ).get(`-${horizon_days} days`) as { n: number; rev: number }
    db.close()
    const n = Number(row?.n ?? 0), rev = Number(row?.rev ?? 0)
    const avg = n ? rev / n : 0
    const new_n = Math.round(n * uplift_factor)
    const new_price = avg * (1 - discount_pct / 100)
    const old_rev = rev, new_rev = Math.round(new_n * new_price)
    return {
      horizon_days, orders_now: n, revenue_now: old_rev, avg_ticket: Math.round(avg * 10) / 10,
      assumed_uplift: uplift_factor, discount_pct,
      projected_orders: new_n, projected_ticket: Math.round(new_price * 10) / 10,
      projected_revenue: new_rev,
      delta_revenue: new_rev - old_rev,
      verdict: new_rev > old_rev ? `📈 الخفض ${discount_pct}% مع رفع حجم ${Math.round((uplift_factor - 1) * 100)}% يرفع العائد ≈ ${new_rev - old_rev} ج.م/شهر (محسوب من البرنامج — ${horizon_days} يوم)` : '📉 الخفض لا يغطي نفسه بهذا الافتراض — راجع الافتراضات',
    }
  } catch {
    return { verdict: 'تعذر حساب سيناريو — قاعدة قراءة فقط غير متاحة' }
  }
}

/* ---------- 3️⃣ صانع العقود — قوالب جاهزة ---------- */
type TemplateKey = 'receipt' | 'supply' | 'return_policy'
const TEMPLATES: Record<TemplateKey, { title: string; render: (client: string, note?: string) => string }> = {
  receipt: {
    title: 'إيصال استلام',
    render: (c, note) => `# إيصال استلام\n\n- العميل: ${c}\n- التاريخ: ${new Date().toLocaleString('ar-EG')}\n- المرجع: ${note || '—'}\n\nاستلمت الورشة (النجار برنت) المواد/الملفات المشار إليها، وسيتم تنفيذها بحركة إنتاج مسجلة من قلعة بيبو.\n\nالتوقيع: ______________\n`,
  },
  supply: {
    title: 'عقد توريد',
    render: (c, note) => `# عقد توريد B2B\n\n**الطرف الأول**: ورشة النجار برنت (برج التلي)\n**الطرف الثاني**: ${c}\n\n1. توريد قطع الإنتاج المبينة في بيان التوريد (${note || 'مرفق'}).\n2. ربع شهري مراجعة كميات وأسعار (محسوبة من البرنامج).\n3. التسليم بيدر داخلي أو شحن متفق عليه.\n4. رقم البزنس الرسمي للتنسيق: 01000433420.\n\nالحالتان: وجوب التسلم بضمان المطابقة للتوريد المتفق عليه.\n`,
  },
  return_policy: {
    title: 'سياسة استرجاع',
    render: (c) => `# سياسة الاسترجاع والضمان — ${c}\n\n- الاسترجاع خلال 7 أيام للقطع القياسية غير المستخدمة.\n- القطع المخصصة (اسم العميل/الشعار) غير قابلة للاسترجاع بعد التشغيل.\n- العيوب المصنعية تُصلح مجاناً ضمن ضمان 30 يوماً.\n- اعتماد الاسترجاع من قيادة سلمى CRM مع تسجيل بصندوق (قاعدة POS تُقرأ فقط).\n`,
  },
}

/* ================= GET ================= */
export async function GET() {
  try {
    const board = readBoard()
    const hw = readHardware()
    const bottlenecks = analyzeBottlenecks(board, hw)
    const quotations: Quotation[] = fs.existsSync(DOCS_DIR)
      ? fs.readdirSync(DOCS_DIR).filter((f) => f.startsWith('Q-') && f.endsWith('.md')).slice(-8).map((f) => {
          const id = f.replace('.md', '')
          const txt = fs.readFileSync(path.join(DOCS_DIR, f), 'utf8')
          const price = Number(txt.match(/السعر النهائي\*\*: (\d+)/)?.[1] ?? 0)
          const client = txt.match(/العميل\*\*: (.+)/)?.[1] ?? ''
          const margin = Number(txt.match(/هامش الربح\*\*: (\d+)/)?.[1] ?? 0)
          return { id, client, items: '—', cost: 0, margin_pct: margin, price, created_at: f }
        })
      : []
    return NextResponse.json({
      bottlenecks,
      board_lines: board.length,
      hardware: hw ? '.live' : 'unavailable',
      quotations,
      templates: Object.entries(TEMPLATES).map(([k, v]) => ({ key: k, title: v.title })),
      business_e164: '+201000433420',
      doc_dir: DOCS_DIR,
    })
  } catch (err) {
    const m = err instanceof Error ? err.message : String(err)
    return NextResponse.json({ error: `فشل غرفة حكيم: ${m.slice(0, 200)}` }, { status: 500 })
  }
}

/* ================= POST ================= */
export async function POST(req: NextRequest) {
  let action = '', client = '', items = '', machine = 'يدوي/تجميع', note = '', template = 'receipt', materials = 0, hours = 1, margin = 30, discount = 15
  try {
    const body = (await req.json()) as Record<string, unknown>
    action = String(body.action ?? '')
    client = String(body.client ?? '')
    items = String(body.items ?? '')
    machine = String(body.machine ?? 'يدوي/تجميع')
    note = String(body.note ?? '')
    template = String(body.template ?? 'receipt')
    materials = Number(body.materials ?? 0)
    hours = Number(body.hours ?? 1)
    margin = Number(body.margin ?? 30)
    discount = Number(body.discount ?? 15)
  } catch {
    return NextResponse.json({ ok: false, message: 'جسم الطلب غير صالح' }, { status: 400 })
  }
  try {
    // 1️⃣ اعتماد وتحويل لسلمى — المحرك يرسل عرض السعر لصندوق وارد سلمى
    if (action === 'make_quotation') {
      if (!client.trim() || !items.trim()) return NextResponse.json({ ok: false, message: 'العميل والبنود مطلوبان' }, { status: 400 })
      const rate = MACHINE_RATE[machine as keyof typeof MACHINE_RATE] ?? 25
      const q = makeQuotation(client, items, materials, (rate ? machine : 'يدوي/تجميع') as keyof typeof MACHINE_RATE, hours, margin)
      // 1️⃣ زر الاعتماد: slash command لصندوق سلمى
      const out = await runSlash(`/summon @salma 📋 عرض سعر رسمي ${q.id} للعميل ${client}: ${items} — السعر النهائي ${q.price} ج.م (هامش ${margin}%) — ارسليه للعميل من غرفة CRM (محسوب من البرنامج)`)
      return NextResponse.json({ ok: Boolean(out.ok), quotation: q, notify: out.ok ? `🚀 عرض السعر ${q.id} أرسل لصندوق وارد سلمى — مروة أُبلغت` : '⚠️ المحرك رفض', file: String(out.file ?? '') })
    }
    // 2️⃣ تحديث إشعارات الاختناق — يقرأ في الصمت وتُرى في GET
    if (action === 'scan_bottlenecks') {
      const bottlenecks = analyzeBottlenecks(readBoard(), readHardware())
      return NextResponse.json({ ok: true, bottlenecks })
    }
    // 3️⃣ توليد وثيقة B2B
    if (action === 'make_document') {
      const t = TEMPLATES[template as TemplateKey]
      if (!t || !client.trim()) return NextResponse.json({ ok: false, message: 'ق/اسم عميل مطلوب' }, { status: 400 })
      fs.mkdirSync(DOCS_DIR, { recursive: true })
      const fileName = `DOC-${template}-${client.replace(/[\\/:*?"<>|]/g, '').slice(0, 24)}-${Date.now() % 100000}.md`
      const filePath = path.join(DOCS_DIR, fileName)
      fs.writeFileSync(filePath, t.render(client, note), 'utf8')
      return NextResponse.json({ ok: true, file: filePath, title: t.title })
    }
    // 4️⃣ محاكي القرارات
    if (action === 'simulate') {
      const r = simulateWhatIf(discount, Number((req.headers.get('x-uplift') ?? '1.35')), Number((req.headers.get('x-horizon') ?? '30')))
      return NextResponse.json({ ok: true, ...r })
    }
    // محاكي عبر body عادي:
    if (action === 'what_if') {
      const r = simulateWhatIf(discount)
      return NextResponse.json({ ok: true, ...r })
    }
    return NextResponse.json({ ok: false, message: `إجراء غير معروف: ${action}` }, { status: 400 })
  } catch (err) {
    const m = err instanceof Error ? err.message : String(err)
    return NextResponse.json({ ok: false, message: m.slice(0, 200) }, { status: 500 })
  }
}
