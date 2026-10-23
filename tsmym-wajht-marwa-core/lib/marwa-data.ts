// lib/marwa-data.ts — الهوية الثابتة للوكلاء العشرة المعتمدين (MARWA CORE)
// سجل الوكلاء العشرة المعتمدين بأمر المالك:
// 1. مروة (م): المنسق العام وقائدة منظومة مروة كور
// 2. فارس (ف): المدير المالي والخزينة والتحصيل (حارس الأرقام)
// 3. سلمى (س): خدمة العملاء والمبيعات والـ CRM
// 4. بيبو (ب): مدير خط الإنتاج والخامات
// 5. مصطفى - صاصا (ص): العتاد والماكينات والصيانة
// 6. حكيم (ح): المستشار المالي ومسؤول التسعير
// 7. فيجن (ج): كبير مهندسي البرمجيات والذكاء الاصطناعي
// 8. كوكو (ك): التسويق والعروض وباقات المنتجات
// 9. أفكار (أ): الأفكار الإبداعية وتطوير المنتجات
// 10. راصد (ر): حارس المنظومة والمراقبة الذاتية

export type AgentId =
  | 'marwa'
  | 'fares'
  | 'salma'
  | 'bebo'
  | 'sasa'
  | 'hakim'
  | 'vision'
  | 'koko'
  | 'afkar'
  | 'rased'

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
  gold: {
    text: 'text-amber-300',
    softBg: 'bg-amber-400/10',
    border: 'border-amber-400/30',
    dot: 'bg-amber-400',
    ring: 'ring-amber-400/30',
    gradient: 'from-amber-400/[0.12]',
    activeBg: 'bg-amber-400/[0.20]',
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
  rose: {
    text: 'text-rose-300',
    softBg: 'bg-rose-400/10',
    border: 'border-rose-400/20',
    dot: 'bg-rose-400',
    ring: 'ring-rose-400/30',
    gradient: 'from-rose-400/[0.09]',
    activeBg: 'bg-rose-400/[0.16]',
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
  indigo: {
    text: 'text-indigo-300',
    softBg: 'bg-indigo-400/10',
    border: 'border-indigo-400/20',
    dot: 'bg-indigo-400',
    ring: 'ring-indigo-400/30',
    gradient: 'from-indigo-400/[0.09]',
    activeBg: 'bg-indigo-400/[0.16]',
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
  fuchsia: {
    text: 'text-fuchsia-300',
    softBg: 'bg-fuchsia-400/10',
    border: 'border-fuchsia-400/20',
    dot: 'bg-fuchsia-400',
    ring: 'ring-fuchsia-400/30',
    gradient: 'from-fuchsia-400/[0.09]',
    activeBg: 'bg-fuchsia-400/[0.16]',
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
}

export type Agent = {
  id: AgentId
  name: string
  glyph: string
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

export const agents: Agent[] = [
  {
    id: 'marwa',
    name: 'مروة',
    glyph: 'م',
    code: 'Maestro',
    role: 'المنسق العام وقائدة منظومة مروة كور',
    image: '/agents/marwa.png',
    tone: tones.gold,
    status: 'online',
    tagline: 'توجيه المنظومة وتنسيق قرارات الوكلاء في غرفة القيادة.',
    keywords: ['مروة', 'تنسيق', 'أمر', 'قيادة', 'توجيه', 'تقرير'],
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
    glyph: 'ف',
    code: 'CFO',
    role: 'المدير المالي والخزينة والتحصيل (حارس الأرقام)',
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
    id: 'salma',
    name: 'سلمى',
    glyph: 'س',
    code: 'CRM',
    role: 'خدمة العملاء والمبيعات والـ CRM',
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
    id: 'bebo',
    name: 'بيبو',
    glyph: 'ب',
    code: 'CAM',
    role: 'مدير خط الإنتاج والخامات',
    image: '/agents/bebo.png',
    tone: tones.amber,
    status: 'busy',
    tagline: 'من الملف إلى الماكينة بدون أخطاء.',
    keywords: ['مقايسة', 'طباعة', 'إنتاج', 'ماكينة', 'تسليم', 'ورق', 'خشب', 'أكريليك', 'بيبو'],
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
    glyph: 'ص',
    code: 'Devices',
    role: 'العتاد والماكينات والصيانة',
    image: '/agents/sasa.png',
    tone: tones.teal,
    status: 'online',
    tagline: 'الأجهزة تشتغل والليزر لا ينام.',
    keywords: ['ليزر', 'أجهزة', 'تشغيل', 'صيانة', 'قاطع', 'بلوتر', 'إبسون', 'صاصا', 'مصطفى'],
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
    glyph: 'ح',
    code: 'Advisor',
    role: 'المستشار المالي ومسؤول التسعير',
    image: '/agents/hakim.png',
    tone: tones.orange,
    status: 'online',
    tagline: 'قرار مبني على رقم أثمن من حدس.',
    keywords: ['استشارة', 'قرار', 'تحليل', 'تسعير', 'سوق', 'تكلفة', 'هامش', 'حكيم'],
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
    glyph: 'ج',
    code: 'Dev',
    role: 'كبير مهندسي البرمجيات والذكاء الاصطناعي',
    image: '/agents/vision.png',
    tone: tones.indigo,
    status: 'idle',
    tagline: 'أبني الأدوات والجسور البرمجية لأسطول الوكلاء.',
    keywords: ['كود', 'تطبيق', 'برمجة', 'أتمتة', 'ربط', 'تكامل', 'فيجن', 'سحابة'],
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
    glyph: 'ك',
    code: 'Marketing',
    role: 'التسويق والعروض وباقات المنتجات',
    image: '/agents/koko.png',
    tone: tones.emerald,
    status: 'online',
    tagline: 'الفكرة الصح في الوقت الصح لأعلى عائد.',
    keywords: ['حملة', 'إعلان', 'تسويق', 'محتوى', 'بوست', 'عرض', 'باقات', 'كوكو'],
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
    glyph: 'أ',
    code: 'Ideas',
    role: 'الأفكار الإبداعية وتطوير المنتجات',
    image: '/agents/afkar.png',
    tone: tones.fuchsia,
    status: 'online',
    tagline: 'كل فكرة مبتكرة قابلة للتحويل إلى منتج ربحي.',
    keywords: ['فكرة', 'عصف', 'ابتكار', 'منتج جديد', 'ديكور', 'هدايا', 'أفكار'],
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
    glyph: 'ر',
    code: 'Sentinel',
    role: 'حارس المنظومة والمراقبة الذاتية',
    image: '/agents/rased.png',
    tone: tones.violet,
    status: 'online',
    tagline: 'أرى ما لا يُرى قبل أن يصبح مشكلة تشغيلية.',
    keywords: ['أمان', 'مراقبة', 'تنبيه', 'مزامنة', 'خطأ', 'نسخ', 'راصد'],
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

export type Message = {
  id: string
  author: 'user' | 'marwa' | 'system' | AgentId
  text: string
  time: string
  actions?: { id: string; label: string; done?: boolean }[]
  meta?: { model: string; ms: number }
}

export function nowTime() {
  return new Date().toLocaleTimeString('ar-EG', { hour: '2-digit', minute: '2-digit' })
}

export const initialMainMessages: Message[] = [
  {
    id: 'm1',
    author: 'marwa',
    text: 'صباح الخير يا محمود. غرفة القيادة المركزية متصلة بالطبقة الحية والوكلاء العشرة تحت إشارتك. جميع الأرقام المالية معتمدة ومطابقة لأمرك التشغيلي.',
    time: '09:00',
  },
]
