// lib/utils.ts — دمج أصناف Tailwind الشرطية (بلا اعتماديات خارجية)
export type ClassValue = string | number | boolean | null | undefined

/** دمج أصناف CSS مع تجاهل القيم الفارغة/الخاطئة */
export function cn(...classes: ClassValue[]): string {
  return classes.filter((c): c is string => typeof c === 'string' && c.length > 0).join(' ')
}

/** تنسيق وقت قصير بالعربي */
export function nowTime(): string {
  return new Date().toLocaleTimeString('ar-EG', { hour: '2-digit', minute: '2-digit' })
}
