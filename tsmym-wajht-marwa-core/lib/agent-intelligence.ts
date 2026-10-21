// lib/agent-intelligence.ts — العقل المركزي وهندسة ذكاء وكلاء مروة كور
// بأمر المالك: التزام صارم بتخصص كل وكيل، حقن البيانات الحية من الـ POS ومجلدات العمل، وتنفيذ أوامر السلاش.
import fs from 'fs'
import path from 'path'
import { execFile } from 'child_process'
import { DatabaseSync } from 'node:sqlite'

export function getRepoRoot(): string {
  if (process.env.REPO_ROOT) return process.env.REPO_ROOT
  if (process.env.WORKSPACE_ROOT) {
    return process.env.WORKSPACE_ROOT.replace(/[\\/]workspaces[\\/]system_engine$/, '').replace(/[\\/]workspaces$/, '')
  }
  const cwd = process.cwd()
  if (path.basename(cwd) === 'tsmym-wajht-marwa-core') {
    return path.resolve(cwd, '..')
  }
  if (fs.existsSync(path.join(cwd, 'workspaces'))) {
    return cwd
  }
  if (fs.existsSync(path.join(cwd, '..', 'workspaces'))) {
    return path.resolve(cwd, '..')
  }
  return 'G:\\ai\\Naggar Print POS Agent'
}

export type AgentKey =
  | 'marwa'
  | 'salma'
  | 'bebo'
  | 'sasa'
  | 'hakim'
  | 'vision'
  | 'koko'
  | 'afkar'
  | 'fares'
  | 'rased'

export const AGENT_MAP: Record<string, { ws: string; name: string; title: string }> = {
  marwa: { ws: 'marwa_maestro', name: 'مروة', title: 'المنسق العام وقائدة منظومة مروة كور' },
  salma: { ws: 'salma_crm', name: 'سلمى', title: 'مسؤولة خدمة العملاء والمبيعات والـ CRM' },
  bebo: { ws: 'bebo_production', name: 'بيبو', title: 'مدير خط الإنتاج والتصنيع والخامات (CAM Manager)' },
  sasa: { ws: 'sasa_devices', name: 'مصطفى (صاصا)', title: 'مسؤول العتاد والماكينات وصيانة الأجهزة' },
  hakim: { ws: 'hakim_advisor', name: 'حكيم', title: 'المستشار المالي والتشخيصي ومسؤول التسعير المعتمد' },
  vision: { ws: 'vision_coder', name: 'فيجن', title: 'كبير مهندسي البرمجيات والذكاء الاصطناعي' },
  koko: { ws: 'koko_marketing', name: 'كوكو', title: 'مسؤول التسويق والعروض وباقات المنتجات' },
  afkar: { ws: 'afkar_ideas', name: 'أفكار', title: 'رائدة الأفكار الإبداعية وتطوير منتجات الورشة' },
  fares: { ws: 'fares_cfo', name: 'فارس', title: 'المدير المالي والخزينة والتحصيل' },
  rased: { ws: 'rased_sentinel', name: 'راصد', title: 'حارس المنظومة والمراقبة الذاتية' },
}

export function resolveAgentKey(raw: unknown): AgentKey {
  if (typeof raw !== 'string') return 'marwa'
  const clean = raw.toLowerCase().trim()
  if (clean in AGENT_MAP) return clean as AgentKey
  const found = Object.entries(AGENT_MAP).find(([, v]) => v.ws === clean || v.name.toLowerCase() === clean)
  return (found?.[0] as AgentKey) ?? 'marwa'
}

function getPosDbPath(): string {
  if (process.env.NB2_POS_DB_PATH) return process.env.NB2_POS_DB_PATH
  return ['G:', 'ai', 'Elnagar POS', 'pos_data.db'].join(path.sep)
}

/** تنفيذ استعلام SQL آمن للقراءة فقط (SELECT فقط) على قاعدة بيانات الـ POS */
export function executePosQuery(sql: string): { ok: boolean; data?: unknown[]; error?: string; count?: number } {
  const trimmed = sql.trim().replace(/;+$/, '')
  if (!/^SELECT\s+/i.test(trimmed)) {
    return { ok: false, error: 'مرفوض: يُسمح فقط باستعلامات القراءة SELECT لحماية قاعدة البيانات.' }
  }
  if (/\b(?:INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|PRAGMA\s+writable|ATTACH|DETACH)\b/i.test(trimmed)) {
    return { ok: false, error: 'مرفوض: استعلام يحتوي على عمليات تعديل غير مسموح بها.' }
  }

  const dbPath = getPosDbPath()
  if (!fs.existsSync(dbPath)) {
    return { ok: false, error: 'قاعدة بيانات الـ POS غير متصلة محلياً.' }
  }

  let db: DatabaseSync | null = null
  try {
    db = new DatabaseSync(dbPath, { readOnly: true })
    const safeSql = /\bLIMIT\s+\d+/i.test(trimmed) ? trimmed : `${trimmed} LIMIT 30`
    const rows = db.prepare(safeSql).all()
    return { ok: true, data: rows, count: rows.length }
  } catch (err: unknown) {
    return { ok: false, error: err instanceof Error ? err.message : String(err) }
  } finally {
    if (db) {
      try { db.close() } catch { /* نتجاهل */ }
    }
  }
}

/** تعريف أداة استعلام قاعدة البيانات المتوافقة مع معايير Function Calling */
export const POS_DB_TOOLS = [
  {
    type: 'function',
    function: {
      name: 'query_pos_db',
      description:
        'تنفيذ استعلام SQL للقراءة فقط (SELECT فقط) على قاعدة بيانات الـ POS (pos_data.db). الجداول المتاحة: raw_materials, products, product_recipes, clients, orders, order_items, transactions, daily_shifts, inventory_counts, purchase_invoices, purchase_items.',
      parameters: {
        type: 'object',
        properties: {
          sql: {
            type: 'string',
            description:
              'استعلام SELECT SQL صالح (مثال: SELECT * FROM raw_materials WHERE name LIKE "%أكريليك%" أو SELECT name, price_wholesale, price_retail FROM products LIMIT 10).',
          },
        },
        required: ['sql'],
      },
    },
  },
]

/** استعادة التدريب الأصلي والذاكرة الحية لكل وكيل من ملفات الـ Markdown الرسمية بجذر المستودع */
export function loadAgentTrainingDoc(agentKey: AgentKey): string {
  const root = getRepoRoot()
  const mapping: Record<AgentKey, string[]> = {
    bebo: ['BIBO_MANUFACTURING_STATE.md'],
    salma: ['SALMA_CRM_STATE.md'],
    fares: ['FARES_CFO_STATE.md'],
    koko: ['KOKO_MARKETING_STATE.md'],
    marwa: ['MARWA_HOME_STATE.md', 'MARWA_CORE.md'],
    sasa: ['SASA_WORKSHOP_STATE.md'],
    hakim: [
      path.join('workspaces', 'hakim_advisor', 'active_workspaces', 'Q-20261020-28.md'),
    ],
    vision: ['AGENT.md'],
    rased: ['RASED_SENTINEL_STATE.md'],
    afkar: [
      path.join('workspaces', 'afkar_ideas', 'active_workspaces', 'notes.json'),
    ],
  }

  const files = mapping[agentKey] || []
  const contents: string[] = []

  for (const f of files) {
    try {
      const fullPath = path.isAbsolute(f) ? f : path.join(root, f)
      if (fs.existsSync(fullPath)) {
        const text = fs.readFileSync(fullPath, 'utf8')
        const maxLen = 14_000
        const trimmed = text.length > maxLen ? text.slice(0, maxLen) + '\n\n... [بقية السجل التاريخي متاح بالأرشيف]' : text
        contents.push(`📘 [وثيقة التدريب الأصلية والميثاق المعتمد للوكيل (${path.basename(f)})]:\n${trimmed}`)
      }
    } catch { /* نتجاهل */ }
  }

  return contents.join('\n\n')
}

/** قراءة ذكية وآمنة وغير مقيدة من كافة جداول قاعدة بيانات الـ POS */
export function queryPosData(queryText: string, agentKey: AgentKey): string {
  const dbPath = getPosDbPath()
  if (!fs.existsSync(dbPath)) return 'قاعدة بيانات الـ POS غير متصلة محلياً.'

  const parts: string[] = []
  let db: DatabaseSync | null = null
  try {
    db = new DatabaseSync(dbPath, { readOnly: true })
    const q = queryText.toLowerCase()

    // 1. خامات التصنيع والألواح والأسعار (raw_materials)
    if (/خام|خامات|أكريليك|اكريليك|خشب|mdf|لوح|ألواح|متر|مج|مجات|سعر الخامه|سبلميشن|فينيل|جلوسي|شاسيه|ليزر/i.test(q) || agentKey === 'bebo' || agentKey === 'hakim') {
      try {
        const materials = db.prepare(`
          SELECT code, name, category, sheet_price, price_per_cm2, unit 
          FROM raw_materials 
          LIMIT 12
        `).all() as { code: string; name: string; category: string; sheet_price: number; price_per_cm2: number; unit: string }[]
        if (materials.length) {
          parts.push(`قائمة خامات الورشة المعتمدة وأسعار المتر (raw_materials):\n` +
            materials.map((m) => `  * ${m.name} [${m.code}]: سعر اللوح/الوحدة ${m.sheet_price} ج.م (سم² = ${m.price_per_cm2} ج)`).join('\n'))
        }
      } catch { /* نتجاهل */ }
    }

    // 2. قائمة المنتجات وأسعار الجملة والقطاعي (products)
    if (/منتج|منتجات|سعر|أسعار|تسعير|بصمة|بوكس|تابلوه|طقم|مبخرة|درع|ساعة|ميدالية|فوتو|كام/i.test(q) || agentKey === 'hakim' || agentKey === 'salma') {
      try {
        const prods = db.prepare(`
          SELECT id, name, category, price_wholesale, price_retail, material_type, manufacturing_cost 
          FROM products 
          ORDER BY id ASC 
          LIMIT 12
        `).all() as { id: number; name: string; category: string; price_wholesale: number; price_retail: number; material_type: string; manufacturing_cost: number }[]
        if (prods.length) {
          parts.push(`قوائم أسعار المنتجات المعتمدة (products):\n` +
            prods.map((p) => `  * #${p.id} ${p.name} (${p.material_type || 'عام'}): جملة ${p.price_wholesale}ج • قطاعي ${p.price_retail}ج ${p.manufacturing_cost ? `(تكلفة تصنيع ${p.manufacturing_cost}ج)` : ''}`).join('\n'))
        }
      } catch { /* نتجاهل */ }
    }

    // 3. وصفات التصنيع ومكونات الـ BOM (product_recipes)
    if (/وصفة|تصنيع|تشغيل|bom|مكونات|هالك|recipe/i.test(q) || agentKey === 'bebo') {
      try {
        const recipes = db.prepare(`
          SELECT pr.product_id, p.name as product_name, pr.material_code, pr.operation_type, pr.length_cm, pr.width_cm, pr.waste_pct, pr.notes
          FROM product_recipes pr
          LEFT JOIN products p ON pr.product_id = p.id
          LIMIT 6
        `).all() as { product_id: number; product_name?: string; material_code: string; operation_type: string; length_cm: number; width_cm: number; waste_pct: number; notes?: string }[]
        if (recipes.length) {
          parts.push(`وصفات تشغيل المنتجات (product_recipes / BOM):\n` +
            recipes.map((r) => `  * ${r.product_name || `#${r.product_id}`}: خامة ${r.material_code} (${r.operation_type}) مقاس ${r.length_cm}×${r.width_cm} سم (هالك ${r.waste_pct}%) ${r.notes ? `[${r.notes}]` : ''}`).join('\n'))
        }
      } catch { /* نتجاهل */ }
    }

    // 4. البحث عن عميل بالاسم أو الهاتف إذا تضمن السؤال اسماً
    const cleanedTerms = queryText
      .replace(/[؟?.,!:]/g, ' ')
      .split(/\s+/)
      .filter((w) => w.length >= 3 && !['حساب', 'مديونية', 'عميل', 'فلوس', 'رصيد', 'أوردر', 'طلب', 'كام', 'كام؟', 'عايز', 'استعلام'].includes(w))

    let matchedClient = false
    for (const term of cleanedTerms.slice(0, 3)) {
      try {
        const clients = db
          .prepare('SELECT id, name, phone, type, balance, notes FROM clients WHERE name LIKE ? LIMIT 3')
          .all(`%${term}%`) as { id: number; name: string; phone: string; type: string; balance: number; notes: string }[]

        if (clients.length > 0) {
          matchedClient = true
          for (const c of clients) {
            const debtStatus = c.balance > 0 ? `مديون بـ ${c.balance} ج.م` : c.balance < 0 ? `دائن بـ ${Math.abs(c.balance)} ج.م` : 'خالص (0 ج.م)'
            parts.push(`بيانات العميل المطابق [${c.name.trim()}]: رقم #${c.id} • النوع: ${c.type} • الرصيد: ${debtStatus} ${c.notes ? `• ملاحظات: ${c.notes}` : ''}`)

            const clientOrders = db
              .prepare('SELECT id, total_amount, status, date FROM orders WHERE client_id = ? ORDER BY id DESC LIMIT 3')
              .all(c.id) as { id: number; total_amount: number; status: string; date: string }[]
            if (clientOrders.length) {
              parts.push(`آخر طلبات العميل #${c.id}: ${clientOrders.map((o) => `أوردر #${o.id} (${o.status} - ${o.total_amount}ج بتاريخ ${o.date || '—'})`).join('، ')}`)
            }
          }
          break
        }
      } catch { /* نتجاهل */ }
    }

    // 5. ملخص المديونيات العامة
    if (['salma', 'fares', 'hakim', 'marwa'].includes(agentKey) && (!matchedClient || queryText.includes('مديون') || queryText.includes('ديون') || queryText.includes('حسابات'))) {
      try {
        const topDebtors = db
          .prepare('SELECT id, name, balance, type FROM clients WHERE balance > 0 ORDER BY balance DESC LIMIT 5')
          .all() as { id: number; name: string; balance: number; type: string }[]
        if (topDebtors.length) {
          parts.push(`أبرز المديونيات الحالية (عملاء مدينون): ${topDebtors.map((d) => `${d.name.trim()} (#${d.id}): ${d.balance}ج`).join(' | ')}`)
        }
      } catch { /* نتجاهل */ }
    }

    // 6. موقف الخزنة النقدية الحية لفارس ومروة
    if (['fares', 'marwa', 'hakim'].includes(agentKey) || /خزنة|الخزنة|كاش|إيراد|شيفت|رصيد الخزنة/i.test(queryText)) {
      try {
        const startRow = db.prepare("SELECT value FROM settings WHERE key = 'accounting_start_date' LIMIT 1").get() as { value?: string } | undefined
        const windowStart = startRow?.value ?? '2026-10-01'
        const income = (db.prepare("SELECT IFNULL(SUM(amount), 0) AS v FROM transactions WHERE type='Income' AND date >= ?").get(windowStart) as { v: number })?.v ?? 0
        const expenses = (db.prepare("SELECT IFNULL(SUM(amount), 0) AS v FROM transactions WHERE type='Expense' AND date >= ?").get(windowStart) as { v: number })?.v ?? 0
        const cashOnHand = 5625 + income - expenses
        parts.push(`موقف الخزنة النقدية الحية (Live Vault):\n  * النقدية الحالية بالخزنة (Cash on Hand): ${cashOnHand.toLocaleString('en-EG')} ج.م (شامل الافتتاحي 5,625ج)\n  * إجمالي إيرادات نافذة المحاسبة: ${income.toLocaleString('en-EG')} ج.م\n  * إجمالي المصروفات: ${expenses.toLocaleString('en-EG')} ج.م`)
      } catch { /* نتجاهل */ }
    }

    // 7. آخر طلبات مسجلة
    try {
      const orders = db
        .prepare('SELECT o.id, o.client_id, o.status, o.total_amount, c.name as client_name FROM orders o LEFT JOIN clients c ON o.client_id = c.id ORDER BY o.id DESC LIMIT 5')
        .all() as { id: number; client_id: number; status: string; total_amount: number; client_name?: string }[]
      if (orders.length) {
        parts.push(`آخر طلبات مسجلة بالـ POS: ${orders.map((o) => `#${o.id} للعميل ${o.client_name ? o.client_name.trim() : `(#${o.client_id})`} - ${o.status} (${Math.round(o.total_amount)}ج)`).join('، ')}`)
      }
    } catch { /* نتجاهل */ }
  } catch {
    /* خطأ قراءة القاعدة */
  } finally {
    if (db) {
      try { db.close() } catch { /* نتجاهل */ }
    }
  }

  return parts.join('\n\n')
}

/** قراءة حالة غرف الوكلاء وبياناتهم الحية من ملفات العمل */
export function buildAgentWorkspaceContext(agentKey: AgentKey, userQuery: string): string {
  const root = getRepoRoot()
  const parts: string[] = []

  // 1. حالة بيبو والإنتاج
  try {
    const boardPath = path.join(root, 'workspaces', 'bebo_production', 'active_workspaces', 'board_state.json')
    if (fs.existsSync(boardPath)) {
      const board = JSON.parse(fs.readFileSync(boardPath, 'utf8')) as Record<string, string>
      const rows = Object.entries(board).map(([id, st]) => `#${id}: ${st}`)
      if (rows.length) parts.push(`طابور الإنتاج في لوحة بيبو (board_state.json): ${rows.join('، ')}`)
    }
  } catch { /* لا ملف */ }

  // 2. حالة العتاد والأجهزة لصاصا
  try {
    const hwPath = path.join(root, 'workspaces', 'sasa_devices', 'active_workspaces', 'hardware_state.json')
    if (fs.existsSync(hwPath)) {
      const hw = JSON.parse(fs.readFileSync(hwPath, 'utf8')) as {
        epson?: { state?: string; online?: boolean; jobs?: number; total_pages_in_queue?: number }
        cutter?: { state?: string; online?: boolean; note?: string; port?: string }
        laser?: { state?: string; online?: boolean; note?: string }
        updated_at?: string
      }
      const hwLines: string[] = []
      if (hw.epson) {
        hwLines.push(`طابعة Epson L1800: ${hw.epson.online ? 'متصلة (Online)' : 'أوفلاين'} - الحالة: ${hw.epson.state ?? 'idle'} - مهام في الطابور: ${hw.epson.jobs ?? 0}`)
      }
      if (hw.cutter) {
        hwLines.push(`كاتر بلوتر COM3: ${hw.cutter.online ? 'متصل' : 'غير متصل'} (${hw.cutter.note || hw.cutter.state})`)
      }
      if (hw.laser) {
        hwLines.push(`ماكينة الليزر: ${hw.laser.state || 'متاحة عبر مجلد Laser_HotFolder'}`)
      }
      if (hwLines.length) parts.push(`العتاد الحقيقي للورشة (hardware_state.json):\n  * ${hwLines.join('\n  * ')}`)
    }
  } catch { /* نتجاهل */ }

  // 3. حقن خاص بكل وكيل
  if (agentKey === 'salma') {
    try {
      const salmaStatePath = path.join(root, 'SALMA_CRM_STATE.md')
      if (fs.existsSync(salmaStatePath)) {
        parts.push(`دستور سلمى CRM: سلمى لا تُسعّر أبداً — كل تسعير يصدر من بيبو عبر أمر (/task @bebo). الرصيد الموجب في الـ POS = العميل مديون للمطبعة. أي دفعة تُسجل فوراً.`)
      }
      const chatsDir = path.join(root, 'workspaces', 'salma_crm', 'chats')
      if (fs.existsSync(chatsDir)) {
        const files = fs.readdirSync(chatsDir).filter((f) => f.endsWith('.md')).slice(-2)
        for (const f of files) {
          const content = fs.readFileSync(path.join(chatsDir, f), 'utf8')
          parts.push(`سجل استدعاء أخير لسلمى (${f}):\n${content.trim().slice(0, 300)}`)
        }
      }
    } catch { /* نتجاهل */ }
  }

  if (agentKey === 'bebo') {
    try {
      parts.push(`قواعد بيبو للتصنيع: تفكيك المجسمات 3D إلى 2D مسطح (قاعدة + سقف + جوانب) • إضافة نسبة هالك 10% • تجميع القص بالألوان (الفواتح أولاً ثم الغوامق ثم الحفر) • خامات: MDF وأكريليك ذهبي 737.7 ج/م² وورق جلوسي ولامنيشن • إذا اكتمل أوردر يبلغ سلمى بأمر (/summon @salma أوردر جاهز).`)
    } catch { /* نتجاهل */ }
  }

  if (agentKey === 'hakim') {
    try {
      const qPath = path.join(root, 'workspaces', 'hakim_advisor', 'active_workspaces', 'Q-20261020-28.md')
      if (fs.existsSync(qPath)) {
        const qContent = fs.readFileSync(qPath, 'utf8').slice(0, 350)
        parts.push(`آخر عرض سعر معتمد بحوزة حكيم (Q-20261020-28):\n${qContent}`)
      }
    } catch { /* نتجاهل */ }
  }

  if (agentKey === 'afkar') {
    try {
      const notesPath = path.join(root, 'workspaces', 'afkar_ideas', 'active_workspaces', 'notes.json')
      if (fs.existsSync(notesPath)) {
        const notes = fs.readFileSync(notesPath, 'utf8')
        parts.push(`نوتات الأفكار الإبداعية الحالية (notes.json): ${notes.slice(0, 250)}`)
      }
    } catch { /* نتجاهل */ }
  }

  if (agentKey === 'fares') {
    try {
      const invPath = path.join(root, 'workspaces', 'fares_cfo', 'active_workspaces', 'inventory.json')
      if (fs.existsSync(invPath)) {
        const inv = JSON.parse(fs.readFileSync(invPath, 'utf8')) as { items: { name: string; quantity: number; unit: string; min_stock: number }[] }
        const low = inv.items.filter((i) => i.quantity <= i.min_stock).map((i) => `${i.name}: ${i.quantity} ${i.unit} (⚠️ حرج)`)
        parts.push(`موقف مخزن فارس للخامات:\n  * خامات حرجة عند/تحت الحد الأدنى: ${low.length ? low.join('، ') : 'جميع الخامات في الحدود الآمنة'}\n  * إجمالي الأصناف المخزنية المدارة: ${inv.items.length}`)
      }
      const sDir = path.join(root, 'workspaces', 'fares_cfo', 'archive', 'shifts')
      if (fs.existsSync(sDir)) {
        const shifts = fs.readdirSync(sDir).filter((f) => f.endsWith('.md')).slice(-2)
        if (shifts.length) parts.push(`تقارير تقفيل الشيفت السابقة بأرشيف فارس: ${shifts.join('، ')}`)
      }
    } catch { /* نتجاهل */ }
  }

  // 4. مهام الـ Inbox لكل وكيل
  try {
    const ws = AGENT_MAP[agentKey]?.ws || 'marwa_maestro'
    const inboxDir = path.join(root, 'workspaces', ws, 'inbox_tasks')
    if (fs.existsSync(inboxDir)) {
      const taskFiles = fs.readdirSync(inboxDir).filter((f) => f.endsWith('.md')).slice(-3)
      if (taskFiles.length) {
        parts.push(`المهام المعلقة في صندوق واردك (${ws}/inbox_tasks):\n  * ${taskFiles.join('\n  * ')}`)
      }
    }
  } catch { /* نتجاهل */ }

  return parts.join('\n\n')
}

/** بناء الـ System Prompt المخصص والديناميكي لكل وكيل مع حقن تدريبه الأصلي والأدوات الحية */
export function buildAgentSystemPrompt(agentKey: AgentKey, userQuery: string): string {
  const info = AGENT_MAP[agentKey] || AGENT_MAP.marwa
  const trainingDoc = loadAgentTrainingDoc(agentKey)
  const livePos = queryPosData(userQuery, agentKey)
  const liveWs = buildAgentWorkspaceContext(agentKey, userQuery)

  let roleInstructions = ''
  switch (agentKey) {
    case 'marwa':
      roleInstructions =
        `أنت «مروة المايسترو» — المنسق العام والقائدة التشغيلية لمنظومة مطبعة النجار برنت.
- تديرين الفريق الثماني (سلمى، بيبو، صاصا، حكيم، فيجن، كوكو، أفكار، فارس).
- أسلوبك: ذكي، حاسم، سريع، عملي، بالعامية المصرية الراقية للورش والمطابع.
- صلاحياتك التنفيذية: عندما يطلب منك المالك استعجال أوردر، أو إسناد مهمة، أو متابعة شغل، تقومين فوراً بالرد وصياغة أمر سلاش صريح ومباشر ضمن ردك بصيغة:
  /task @bebo استعجال أوردر 328 وتجهيزه للتسليم اليوم
  أو /task @sasa فحص كاتر البلوتر وتشغيل ماكينة الليزر
  أو /summon @salma متابعة حساب ومديونية العميل فلان
  أو /status @bebo
  ليقوم محرك النظام الخلفي (router_daemon) بالتقاط الأمر وتنفيذه فورياً. لا تكتفي بالكلام فقط عند طلب إجراء!`
      break

    case 'salma':
      roleInstructions =
        `أنت «سلمى» — مسؤولة خدمة العملاء والمبيعات وإدارة الـ CRM لمطبعة النجار برنت.
- أسلوبك: بشوشة، ودودة، في غاية الدقة والأمانة، وتتحدثين بالعامية المصرية الودودة.
- القواعد الذهبية الملزمة:
  1. ❌ سلمى لا تُسعِّر أبداً — أي استفسار تسعير تحيلينه لبيبو عبر أمر: /task @bebo تسعير منتج كذا للعميل كذا
  2. 💰 في الحسابات والأرصدة: الرصيد الموجب في الـ POS = مديونية على العميل لصالحنا. الرصيد السالب = دائن للمطبعة. اقرئي الأرقام من بيانات الـ POS المرفقة بدقة ولا تخترعي أي رقم أو اسم.
  3. 📞 الحفاظ على بيانات العملاء وتوثيق الدفعات والأوردرات فوراً.`
      break

    case 'bebo':
      roleInstructions =
        `أنت «بيبو» — مدير خط الإنتاج والتصنيع والخامات (CAM Manager) ومصمم الورشة المحترف لمطبعة النجار برنت.
- أسلوبك: صنايعي هندسي دقيق، واثق، يتحدث بلغة الورشة والمقاسات بالمليمتر والسنتيمتر (خشب MDF، أكريليك ذهبي/مرايات 737.7 ج/م²، تفكيك ثلاثي الأبعاد 3D->2D، هالك 10%، Nesting batches).
- طابور الإنتاج: تقرأ حالة الأوردرات من لوحة الإنتاج board_state.json بدقة.
- أوامرك التنفيذية: إذا أردت توجيه أوامر تشغيل لماكينات الليزر أو الكاتر لصاصا، اكتب: /task @sasa تشغيل الليزر لقص باتش كذا. وإذا جهز أوردر بلغ سلمى: /summon @salma أوردر 328 جاهز للتسليم.`
      break

    case 'sasa':
      roleInstructions =
        `أنت «مصطفى (صاصا)» — مسؤول العتاد وصيانة الأجهزة والماكينات وشبكة الورشة.
- أسلوبك: فني صيانة عملي ومباشر وخبير بمنافذ السيريال (COM Ports) والطابعات وأعطال الويندوز.
- اختصاصك: طابعة الإبسون Epson L1800 وحالة Spooler، كاتر البلوتر COM3، وماكينة الليزر ومجلدات Laser_HotFolder و Cutter_HotFolder.
- تحدث بناءً على قراءات العتاد الحقيقية المرفقة فقط.`
      break

    case 'hakim':
      roleInstructions =
        `أنت «حكيم» — المستشار المالي والتشخيصي ومسؤول التسعير المعتمد وتدقيق التكاليف لمطبعة النجار برنت.
- أسلوبك: تحليلي، رزين، دقيق الأرقام، تركز على هوامش الربح وحساب التكاليف الحقيقية وأسعار الخامات.
- مهامك: اعتماد عروض الأسعار الرسمية وتوجيهها لسلمى: /task @salma إرسال عرض سعر رسمي للعميل.`
      break

    case 'vision':
      roleInstructions =
        `أنت «فيجن» — كبير مهندسي البرمجيات والذكاء الاصطناعي وبوابة الأنظمة.
- أسلوبك: مهندس برمجيات محترف ودقيق، خبير ببوابات الـ LLM والنماذج والمزامنة والتكاملات.
- اختصاصك: إدارة أسطول الذكاء الاصطناعي (ai_providers.json)، النماذج السريعة والقوية، وسجلات الأداء.`
      break

    case 'koko':
      roleInstructions =
        `أنت «كوكو» — مسؤول التسويق والعروض والمحتوى الإبداعي لزيادة مبيعات الورشة.
- أسلوبك: حماسي، جذاب، مبدع، تركز على باقات المواسم والمنتجات الأكثر ربحية وعروض الجملة والقطاعي.`
      break

    case 'afkar':
      roleInstructions =
        `أنت «أفكار» — رائدة الأفكار الإبداعية والابتكار وتطوير منتجات الديكور والهدايا المميزة للورشة.
- أسلوبك: عصف ذهني متجدد، تبتكرين أفكار تابلوهات، علب هدايا، مجسمات خشب وأكريليك غير تقليدية لزيادة المبيعات.`
      break

    case 'fares':
      roleInstructions =
        `أنت «فارس» — وزير المالية ومدير الإمداد (CFO & Inventory Manager) لمطبعة النجار برنت.
- أسلوبك: صارم، حذر جداً، دقيق في الأرقام حتى المليم، لا يقبل تهاوناً في الخزينة أو تفريطاً في السيولة النقدية أو تأخير التحصيل.
- قواعدك الصارمة والملزمة:
  1. 💰 الخزنة النقدية اللحظية (Cash on Hand): رصيد الخزنة النقدية الحالية يُحسب بمعادلة معتمدة: (رصيد افتتاحي 5,625 ج + دخل النافذة − المصروفات). تذكر الأرقام بالمليم متى سُئلت عن الخزنة أو النقدية أو إيرادات اليوم بناءً على بيانات الـ POS المرفقة.
  2. 🚫 الرفض القاطع لأي خصومات: ترفض أي تخفيض يطلبه العميل أو تقترحه سلمى إذا كان يقلل هامش الربح عن 35% المعتمد من حكيم. صافي الربح الفعلي = (سعر البيع) − (تكلفة الخامات من المخزن + تكلفة وقت ماكينات صاصا).
  3. 📦 رقابة المخزون والربط مع بيبو: تراقب سحب الخامات لبيبو، وإذا قل رصيد أي خامة (خشب، أكريليك، أحبار، فينيل) عن الحد الأدنى، تصدر تحذيراً أحمر فورياً وتقترح أمر سلاش: /task @koko إيقاف إعلانات وترويج المنتجات المعتمدة على هذه الخامة لحين التوريد.
  4. 💸 رادار المديونيات: تطالب بالتحصيل الفوري للآجل المعلق عند استلام أي أوردر، وتجهز رسائل المطالبة المهذبة للواتساب.`
      break

    default:
      roleInstructions = `أنت «${info.name}» — ${info.title} في منظومة مروة كور لورشة النجار برنت. تجيب بالعامية المصرية باختصار ووضوح وبناءً على البيانات الحية فقط.`
  }

  const dbToolSection =
    `🛠️ أداة استعلام قاعدة بيانات الورشة المتاحة لك (Dynamic POS Tool):` +
    `\nلديك وصول مباشر لاستكشاف وقراءة أي جدول في قاعدة بيانات الـ POS (pos_data.db) عبر استدعاء الأداة [query_pos_db] بأي استعلام SELECT تحتاجه، أو بكتابة الأمر صراحة في ردك بصيغة: [SQL: SELECT ... FROM ...] ليقوم محرك النظام بتنفيذه وإعادتك بالبيانات الحية!` +
    `\nالجداول المتاحة بالقاعدة:` +
    `\n• raw_materials: أسعار الألواح والمتر وخامات التصنيع (خشب MDF، أكريليك ذهبي/شفاف، سبلميشن، مجات، ورق، شاسيهات).` +
    `\n• products: المنتجات الجاهزة وأسعار الجملة والقطاعي وتكاليف التصنيع.` +
    `\n• product_recipes: وصفات التصنيع (BOM) ونسب الهالك والأبعاد لكل منتج.` +
    `\n• clients: حسابات ومديونيات العملاء.` +
    `\n• orders & order_items: تفاصيل وحالات كافة الطلبات السابقة والحالية.` +
    `\n• transactions: إيرادات ومصروفات الخزينة.` +
    `\n• daily_shifts: سجل تقفيل الورديات والأرباح.`

  return (
    `${trainingDoc ? `${trainingDoc}\n\n---\n\n` : ''}` +
    `${roleInstructions}\n\n` +
    `${dbToolSection}\n\n` +
    `⚡ نظام أدوات السلاش المتاح لك:\n` +
    `أنت لست مجرد نص! يمكنك تنفيذ أدوات النظام في أي لحظة بكتابة أوامر السلاش الصريحة في سطر مستقل:\n` +
    `- /task @<agent> <تفاصيل المهمة> (لإنشاء مهمة رسمية في صندوق وارد الوكيل)\n` +
    `- /summon @<agent> <سبب الاستدعاء> (لاستدعاء الوكيل وفتح محادثة معه)\n` +
    `- /status @<agent> (لفحص حالة مهام الوكيل ومجلداته)\n\n` +
    `📊 البيانات المستخرجة الآن من الورشة والـ POS:\n` +
    (livePos ? `--- بيانات الـ POS المحلية المسترجعة ذكياً ---\n${livePos}\n\n` : '') +
    (liveWs ? `--- بيانات غرف العمل والعتاد النشطة ---\n${liveWs}\n\n` : '') +
    `قاعدة صارمة: استند لتدريبك الأصلي والأرقام المعتمدة بالقاعدة دون اختلاق.`
  )
}

/** فحص استجابة الوكيل وتنفيذ أي أمر سلاش أصدره آلياً عبر router_daemon */
export async function executeSlashCommandsInText(text: string): Promise<{ executed: boolean; log: string[] }> {
  const slashRegex = /^\s*(\/(?:task|summon|status)\s+@\w+[\s\S]*?)$/gm
  const matches: string[] = []
  let m: RegExpExecArray | null
  while ((m = slashRegex.exec(text)) !== null) {
    const cmd = m[1].trim()
    if (cmd) matches.push(cmd)
  }

  if (matches.length === 0) return { executed: false, log: [] }

  const root = getRepoRoot()
  const engine = path.join(root, 'workspaces', 'system_engine', 'router_daemon.py')
  const python = process.env.PYTHON_EXE || path.join(root, '.venv', 'Scripts', 'python.exe')
  const logs: string[] = []

  for (const cmd of matches) {
    try {
      // 1. تسجيل الأمر في pending_slash.txt للدايمون
      const pendingFile = path.join(root, 'workspaces', 'system_engine', 'pending_slash.txt')
      try {
        fs.appendFileSync(pendingFile, `${cmd}\n`, 'utf8')
      } catch { /* نتجاهل */ }

      // 2. التنفيذ المباشر عبر router_daemon.py parse
      const out = await new Promise<string>((resolve, reject) => {
        execFile(
          python,
          [engine, 'parse', cmd],
          { timeout: 15_000, encoding: 'utf8', cwd: root },
          (err, stdout) => (err ? reject(err) : resolve(stdout)),
        )
      })
      const parsed = JSON.parse(out) as { ok?: boolean; cmd?: string; agent?: string; file?: string; push?: string; message?: string }
      if (parsed.ok) {
        logs.push(`تم تنفيذ أمر السلاش [${cmd.split(' ').slice(0, 2).join(' ')}] وتوجيه المهمة إلى @${parsed.agent ?? 'الوكيل'} (الملف: ${path.basename(parsed.file || '')})`)
      } else {
        logs.push(`محاولة تنفيذ ${cmd.split(' ')[0]}: ${parsed.message || 'رُفض'}`)
      }
    } catch (err) {
      logs.push(`فشل تشغيل محرك السلاش: ${err instanceof Error ? err.message.slice(0, 100) : String(err)}`)
    }
  }

  return { executed: true, log: logs }
}

/** حفظ سجل المحادثة لكل وكيل بشكل مستقل في مجلد chats التابع لغرفته */
export function logAgentChatTurn(agentKey: AgentKey, userMsg: string, assistantReply: string): void {
  try {
    const root = getRepoRoot()
    const ws = AGENT_MAP[agentKey]?.ws || 'marwa_maestro'
    const chatsDir = path.join(root, 'workspaces', ws, 'chats')
    fs.mkdirSync(chatsDir, { recursive: true })
    const today = new Date().toISOString().slice(0, 10)
    const logFile = path.join(chatsDir, `session_${today}.jsonl`)
    const record = {
      timestamp: new Date().toISOString(),
      agent: agentKey,
      user: userMsg,
      assistant: assistantReply,
    }
    fs.appendFileSync(logFile, JSON.stringify(record) + '\n', 'utf8')
  } catch {
    /* لا نوقف الشات في حال تعذر الكتابة */
  }
}
