// lib/agents.ts — هوية الوكلاء العشرة الثابتة (مطابقة لميثاق MARWA CORE)
// المرحلة 1: غرفة مروة كاملة — الباقي Placeholders بانتظار ربط محركاتهم.

export type AgentId =
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

export type Agent = {
  id: AgentId
  name: string
  title: string
  glyph: string
  /** الحالة التشغيلية للواجهة: full = غرفة مكتملة • placeholder = بانتظار ربط المحرك */
  phase: 'full' | 'placeholder'
}

export const AGENTS: Agent[] = [
  { id: 'marwa', name: 'مروة', title: 'المنسق العام وقائدة منظومة مروة كور', glyph: 'م', phase: 'full' },
  { id: 'koko', name: 'كوكو', title: 'مسؤول التسويق والعروض والمحتوى', glyph: 'ك', phase: 'placeholder' },
  { id: 'afkar', name: 'أفكار', title: 'رائدة الأفكار الإبداعية والابتكار', glyph: 'أ', phase: 'placeholder' },
  { id: 'salma', name: 'سلمى', title: 'مسؤولة خدمة العملاء والمبيعات والـ CRM', glyph: 'س', phase: 'placeholder' },
  { id: 'bebo', name: 'بيبو', title: 'مدير خط الإنتاج والتصنيع والخامات (CAM)', glyph: 'ب', phase: 'placeholder' },
  { id: 'fares', name: 'فارس', title: 'المدير المالي والخزينة والتحصيل', glyph: 'ف', phase: 'placeholder' },
  { id: 'sasa', name: 'صاصا', title: 'مسؤول العتاد والماكينات وصيانة الأجهزة', glyph: 'ص', phase: 'placeholder' },
  { id: 'hakim', name: 'حكيم', title: 'المستشار المالي والتشخيصي ومسؤول التسعير', glyph: 'ح', phase: 'placeholder' },
  { id: 'vision', name: 'فيجن', title: 'كبير مهندسي البرمجيات والذكاء الاصطناعي', glyph: 'ف', phase: 'placeholder' },
  { id: 'rased', name: 'راصد', title: 'حارس المنظومة والمراقبة الذاتية', glyph: 'ر', phase: 'placeholder' },
]

export const agentById = (id: AgentId): Agent => AGENTS.find((a) => a.id === id) ?? AGENTS[0]
