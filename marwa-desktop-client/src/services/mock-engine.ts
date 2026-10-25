// services/mock-engine.ts — وضع العرض المحلي (صادق وموسوم MOCK)
// يُستخدم فقط عندما لا يوجد جسر DSH — ليُعرض تصميم الواجهة كاملاً
// بحالات تحميل حقيقية وأشرطة «بانتظار الجسر» — بلا أي ادعاء ببيانات حية.

import type { DshEvent } from './dsh-ipc'

export type MockStats = {
  cash_on_hand: number
  income_window: number
  receivables: number
  under_preparation: { count: number; value: number }
  /** مصدر القيم — يظهر في شارة الكرت */
  source: 'mock'
}

export const MOCK_STATS: MockStats[] = [
  { cash_on_hand: 7930, income_window: 2305, receivables: 310, under_preparation: { count: 1, value: 310 }, source: 'mock' },
  { cash_on_hand: 7930, income_window: 2305, receivables: 310, under_preparation: { count: 1, value: 310 }, source: 'mock' },
  { cash_on_hand: 7930, income_window: 2305, receivables: 310, under_preparation: { count: 1, value: 310 }, source: 'mock' },
]

/** محاكاة بث إحصاءات — للعرض فقط */
export function emitMockStats(emit: (e: DshEvent) => void): () => void {
  const timer = setInterval(() => {
    emit({ type: 'stats', payload: { ...MOCK_STATS[0], mock: true } })
  }, 15_000)
  emit({ type: 'stats', payload: { ...MOCK_STATS[0], mock: true } })
  return () => clearInterval(timer)
}
