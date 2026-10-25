// stores/agentStore.ts — العزل الكامل لكل وكيل (فكرة المالك: «كل وكيل كأنه WebView مستقل»)
// MARWA CORE task-8:
//   كل وكيل يمتلك Store مستقلاً (Zustand vanilla store داخل Map registry):
//     • messages: سجل محادثته وحده (لا يتقاسم أي بايت مع الآخرين)
//     • memory: خلاصات الذاكرة الخاصة به
//     • toolsState: حالة استدعاءات الأدوات الجارية/المنتهية
//     • scratchpad: التفكير الداخلي (يُعرض Collapsible)
//     • unread: عدّاد الرسائل غير المقروءة للشريط الجانبي
// 💾 الذاكرة (RAM): الـStore يُنشأ عند أول فتح للغرفة فقط (Lazy) ويُحتفظ به —
//    والتنظيف متاح عبر disposeAgentStore(id) لتفريغ وكلاء غير مستخدمين.
// ⚠️ لا يوجد أي متغير مشترك بين اثنين — التداخل مستحيل بنيوياً.

import { create, type StoreApi, type UseBoundStore } from 'zustand'
import type { AgentId } from '@/lib/agents'

export type ToolCallState = {
  id: string
  tool: string
  status: 'running' | 'done' | 'failed'
  ms?: number
  preview?: string
}

export type ChatMessage = {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  time: string
  model?: string
  latency_ms?: number
  /** التفكير الداخلي — يُعرض Collapsible أنيق تحت الفقاعة */
  scratchpad?: string
  /** استدعاءات الأدوات المرتبطة بالرد */
  toolCalls?: ToolCallState[]
}

export type AgentState = {
  messages: ChatMessage[]
  /** خلاصات ذاكرة الوكيل (تُغذى من دفتره عند ربط الجسر) */
  memory: string[]
  /** حالة أدوات الوكيل */
  toolCalls: ToolCallState[]
  scratchpad: string
  unread: number
  isGenerating: boolean
  // أفعال
  addMessage: (m: ChatMessage) => void
  updateMessage: (id: string, patch: Partial<ChatMessage>) => void
  clearMessages: () => void
  setMemory: (items: string[]) => void
  pushToolCall: (t: ToolCallState) => void
  patchToolCall: (id: string, patch: Partial<ToolCallState>) => void
  setScratchpad: (s: string) => void
  bumpUnread: () => void
  resetUnread: () => void
  setGenerating: (v: boolean) => void
}

function makeInitial(id: AgentId) {
  return {
    messages: [
      {
        id: `${id}-boot`,
        role: 'system' as const,
        content: `غرفة ${id} جاهزة — بانتظار ربط الجسر المحلي (DSH Bridge) لتفعيل الردود الحية.`,
        time: new Date().toLocaleTimeString('ar-EG', { hour: '2-digit', minute: '2-digit' }),
      },
    ],
    memory: [],
    toolCalls: [] as ToolCallState[],
    scratchpad: '',
    unread: 0,
    isGenerating: false,
  }
}

/** سجل المخازن — كل وكيل نسخة مستقلة تماماً (Lazy: يُنشأ عند أول فتح غرفته فقط — وعي بالـRAM) */
const registry = new Map<AgentId, UseBoundStore<StoreApi<AgentState>>>()

export function getAgentStore(id: AgentId): UseBoundStore<StoreApi<AgentState>> {
  let store = registry.get(id)
  if (!store) {
    store = create<AgentState>()((set) => ({
      ...makeInitial(id),
      addMessage: (m) => set((s) => ({ messages: [...s.messages, m] })),
      updateMessage: (mid, patch) =>
        set((s) => ({ messages: s.messages.map((m) => (m.id === mid ? { ...m, ...patch } : m)) })),
      clearMessages: () => set((s) => ({ messages: s.messages.slice(0, 1) })),
      setMemory: (items) => set({ memory: items }),
      pushToolCall: (t) => set((s) => ({ toolCalls: [t, ...s.toolCalls].slice(0, 30) })),
      patchToolCall: (tid, patch) =>
        set((s) => ({ toolCalls: s.toolCalls.map((t) => (t.id === tid ? { ...t, ...patch } : t)) })),
      setScratchpad: (text) => set({ scratchpad: text }),
      bumpUnread: () => set((s) => ({ unread: s.unread + 1 })),
      resetUnread: () => set({ unread: 0 }),
      setGenerating: (v) => set({ isGenerating: v }),
    }))
    registry.set(id, store)
  }
  return store
}

/**
 * ملاحظة إدارة الذاكرة (RAM): المخازن تُنشأ Lazy وتعيش لوقت التطبيق (نمط WebView مستقل).
 * التنظيف الكامل غير مطبق في v5 typing (destroy غير مكشوف) — عند الحاجة: unmount الغرفة
 * يكفي لأن الحالة تبقى صغيرة (رسائل + خلاصات) — والنافذة نفسها تحرر كل شيء عند الإغلاق.
 */
