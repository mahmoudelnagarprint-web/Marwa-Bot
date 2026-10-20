// lib/marwa-data.ts — الهوية الثابتة للوكلاء فقط (MARWA CORE)
// ⚠️ مُطهَّر بأمر المالك (2026-10-20 — task-2 فيجن): كل البيانات الوهمية
// (stats/news/reports/suggestions/complaints/replies/رسائل افتتاحية بأرقام
// متخيلة) حُذفت. كل رقم مالي يأتي حيًّا من lib/live.ts + app/api/fares-summary
// (القاعدة الحية بوضع قراءة فقط) وموسوم «محسوب من البرنامج».
// الأسماء والأدوار والصور ثابتة — لا يُخترع وكيل جديد (ميثاق §1).

export type AgentId = 'salma' | 'fares' | 'bebo' | 'koko' | 'sasa' | 'hakim' | 'afkar' | 'rased' | 'vision'

export type Tone = {
  text: string
  softBg: string
  border: string
  dot: string
  ring: string
  gradient: string
  activeBg: string
}

export const tones: Record<string, Tone> = {
  rose: {
    text: 'text-rose-300',
    softBg: 'bg-rose-400/10',
    border: 'border-rose-400/20',
    dot: 'bg-rose-400',
    ring: 'ring-rose-400/30',
    gradient: 'from-rose-400/[0.09]',
    activeBg: 'bg-rose-400/[0.16]',
  },
  sky: {
    text: 'text-sky-300',
    softBg: 'bg-sky-400/10',
    border: 'border-sky-400/20',
    dot: 'bg-sky-400',
    ring: 'ring-sky-400/30',
    gradient: 'from-sky-400/[0.09]',
    activeBg: 'bg-sky-400/[0.16]',
  },
  amber: {
    text: 'text-amber-300',
    softBg: 'bg-amber-400/10',
    border: 'border-amber-400/20',
    dot: 'bg-amber-400',
    ring: 'ring-amber-400/30',
    gradient: 'from-amber-400/[0.08]',
    activeBg: 'bg-amber-400/[0.16]',
  },
  emerald: {
    text: 'text-emerald-300',
    softBg: 'bg-emerald-400/10',
    border: 'border-emerald-400/20',
    dot: 'bg-emerald-400',
    ring: 'ring-emerald-400/30',
    gradient: 'from-emerald-400/[0.08]',
    activeBg: 'bg-emerald-400/[0.16]',
  },
  violet: {
    text: 'text-violet-300',
    softBg: 'bg-violet-400/10',
    border: 'border-violet-400/20',
    dot: 'bg-violet-400',
    ring: 'ring-violet-400/30',
    gradient: 'from-violet-400/[0.09]',
    activeBg: 'bg-violet-400/[0.16]',
  },
  indigo: {
    text: 'text-indigo-300',
    softBg: 'bg-indigo-400/10',
    border: 'border-indigo-400/20',
    dot: 'bg-indigo-400',
    ring: 'ring-indigo-400/30',
    gradient: 'from-indigo-400/[0.09]',
    activeBg: 'bg-indigo-400/[0.16]',
  },
  teal: {
    text: 'text-teal-300',
    softBg: 'bg-teal-400/10',
    border: 'border-teal-400/20',
    dot: 'bg-teal-400',
    ring: 'ring-teal-400/30',
    gradient: 'from-teal-400/[0.09]',
    activeBg: 'bg-teal-400/[0.16]',
  },
  orange: {
    text: 'text-orange-300',
    softBg: 'bg-orange-400/10',
    border: 'border-orange-400/20',
    dot: 'bg-orange-400',
    ring: 'ring-orange-400/30',
    gradient: 'from-orange-400/[0.09]',
    activeBg: 'bg-orange-400/[0.16]',
  },
  fuchsia: {
    text: 'text-fuchsia-300',
    softBg: 'bg-fuchsia-400/10',
    border: 'border-fuchsia-400/20',
    dot: 'bg-fuchsia-400',
    ring: 'ring-fuchsia-400/30',
    gradient: 'from-fuchsia-400/[0.09]',
    activeBg: 'bg-fuchsia-400/[0.16]',
  },
}

export type Agent = {
  id: AgentId
  name: string
  code: string
  role: string
  image: string
  tone: Tone
  status: 'online' | 'busy' | 'idle'
  tagline: string
  keywords: string[]
  stats: { label: string; value: string; delta: string; positive: boolean }[]
  news: { text: string; time: string }[]
  reports: { title: string; date: string; summary: string }[]
  suggestions: { title: string; impact: string }[]
  complaints: { title: string; severity: 'عالي' | 'متوسط' | 'منخفض' }[]
  replies: string[]
  unread: number
}

// الهوية فقط — بلا أي بيانات وهمية: المصفوفات تُملأ حيًّا من الطبقة الحية
// (كروت فارس من القاعدة read-only، والمهام من جدول agent_tasks السحابي).
export const agents: Agent[] = [
  {
    id: 'salma',
    name: 'سلمى',
    code: 'CRM',
    role: 'مديرة علاقات العملاء',
    image: '/agents/salma.png',
    tone: tones.rose,
    status: 'online',
    tagline: 'أتابع كل عميل حتى يصبح عميلاً دائماً.',
    keywords: ['عميل', 'عملاء', 'واتساب', 'طلب', 'متابعة', 'سلمى'],
    stats: [],
    news: [],
    reports: [],
    suggestions: [],
    complaints: [],
    replies: [],
    unread: 0,
  },
  {
    id: 'fares',
    name: 'فارس',
    code: 'CFO',
    role: 'وزير المالية ومدير الإمداد',
    image: '/agents/fares.png',
    tone: tones.sky,
    status: 'online',
    tagline: 'كل جنيه محسوب، وكل فاتورة في مكانها.',
    keywords: ['حساب', 'فاتورة', 'تسوية', 'مال', 'تحصيل', 'سعر', 'ربح', 'خزنة', 'آجل', 'دخل', 'فارس'],
    stats: [],
    news: [],
    reports: [],
    suggestions: [],
    complaints: [],
    replies: [],
    unread: 0,
  },
  {
    id: 'bebo',
    name: 'بيبو',
    code: 'CAM',
    role: 'مهندس الإنتاج والمقايسات',
    image: '/agents/bebo.png',
    tone: tones.amber,
    status: 'busy',
    tagline: 'من الملف إلى الماكينة بدون أخطاء.',
    keywords: ['مقايسة', 'طباعة', 'إنتاج', 'ماكينة', 'تسليم', 'ورق', 'بيبو'],
    stats: [],
    news: [],
    reports: [],
    suggestions: [],
    complaints: [],
    replies: [],
    unread: 0,
  },
  {
    id: 'koko',
    name: 'كوكو',
    code: 'Marketing',
    role: 'مسؤولة التسويق والمحتوى',
    image: '/agents/koko.png',
    tone: tones.emerald,
    status: 'online',
    tagline: 'الفكرة الصح في الوقت الصح.',
    keywords: ['حملة', 'إعلان', 'تسويق', 'محتوى', 'بوست', 'عرض', 'كوكو'],
    stats: [],
    news: [],
    reports: [],
    suggestions: [],
    complaints: [],
    replies: [],
    unread: 0,
  },
  {
    id: 'rased',
    name: 'راصد',
    code: 'Sentinel',
    role: 'الحارس والمراقب',
    image: '/agents/rased.png',
    tone: tones.violet,
    status: 'online',
    tagline: 'أرى ما لا يُرى قبل أن يصبح مشكلة.',
    keywords: ['أمان', 'مراقبة', 'تنبيه', 'مزامنة', 'خطأ', 'نسخ', 'راصد'],
    stats: [],
    news: [],
    reports: [],
    suggestions: [],
    complaints: [],
    replies: [],
    unread: 0,
  },
  {
    id: 'vision',
    name: 'فيجن',
    code: 'Dev',
    role: 'مطور المنظومة',
    image: '/agents/vision.png',
    tone: tones.indigo,
    status: 'idle',
    tagline: 'أبني الأدوات التي يعمل بها الجميع.',
    keywords: ['كود', 'تطبيق', 'برمجة', 'أتمتة', 'ربط', 'تكامل', 'فيجن'],
    stats: [],
    news: [],
    reports: [],
    suggestions: [],
    complaints: [],
    replies: [],
    unread: 0,
  },
  {
    id: 'sasa',
    name: 'صاصا',
    code: 'Devices',
    role: 'مراقبة الأجهزة والليزر',
    image: '/agents/sasa.png',
    tone: tones.teal,
    status: 'online',
    tagline: 'الأجهزة تشتغل والليزر لا ينام.',
    keywords: ['ليزر', 'أجهزة', 'تشغيل', 'صيانة', 'قاطع', 'صاصا'],
    stats: [],
    news: [],
    reports: [],
    suggestions: [],
    complaints: [],
    replies: [],
    unread: 0,
  },
  {
    id: 'hakim',
    name: 'حكيم',
    code: 'Advisor',
    role: 'مستشار القرارات',
    image: '/agents/hakim.png',
    tone: tones.orange,
    status: 'online',
    tagline: 'قرار مبني على رقم أثمن من حدس.',
    keywords: ['استشارة', 'قرار', 'تحليل', 'تسعير', 'سوق', 'حكيم'],
    stats: [],
    news: [],
    reports: [],
    suggestions: [],
    complaints: [],
    replies: [],
    unread: 0,
  },
  {
    id: 'afkar',
    name: 'أفكار',
    code: 'Ideas',
    role: 'العصف الذهني',
    image: '/agents/afkar.png',
    tone: tones.fuchsia,
    status: 'online',
    tagline: 'كل فكرة استرشادية قابلة للتنفيذ.',
    keywords: ['فكرة', 'عصف', 'ابتكار', 'منتج جديد', 'أفكار'],
    stats: [],
    news: [],
    reports: [],
    suggestions: [],
    complaints: [],
    replies: [],
    unread: 0,
  },
]

export const agentMap = Object.fromEntries(agents.map((a) => [a.id, a])) as Record<AgentId, Agent>

export const models = [
  { id: 'claude-opus', label: 'Claude Opus 4.5', provider: 'Anthropic' },
  { id: 'gpt-5', label: 'GPT-5', provider: 'OpenAI' },
  { id: 'gemini-pro', label: 'Gemini 2.5 Pro', provider: 'Google' },
  { id: 'llama-local', label: 'Llama محلي', provider: 'LAPTOP' },
]

export type Message = {
  id: string
  author: 'user' | 'marwa' | 'system' | AgentId
  text: string
  time: string
  actions?: { id: string; label: string; done?: boolean }[]
}

export function nowTime() {
  return new Date().toLocaleTimeString('ar-EG', { hour: '2-digit', minute: '2-digit' })
}

// رسالة افتتاحية محايدة — بلا أي أرقام أو أحداث متخيلة.
// كل الأرقام المالية تظهر على كروت «محسوب من البرنامج» في غرفة فارس.
export const initialMainMessages: Message[] = [
  {
    id: 'm1',
    author: 'marwa',
    text: 'صباح الخير محمود. واجهة المنظومة متصلة بالطبقة الحية — كل الأرقام المالية على الكروت موسومة «محسوب من البرنامج» وتُقرأ مباشرة من القاعدة. اسألني عن أي حساب.',
    time: '09:00',
  },
]
