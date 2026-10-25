// services/dsh-ipc.ts — 🌉 الجسر المحلي بين واجهة Desktop و DeepSeek Harness
// MARWA CORE task-8 (أمر المالك 2026-10-25): قلب الترحيب للعالم الخارجي.
//
// ثلاث وسائل نقل بمبدأ التدرج الآمن (Graceful Degradation):
//   1) 'tauri'     — عند التشغيل داخل Tauri (window.__TAURI_INTERNALS__ موجود)
//                    → invoke() بسرعة البرق عبر Rust IPC (Recursive Tool Calling).
//   2) 'websocket' — عند تشغيل الواجهة في المتصفح والمحرك المحلي يعمل
//                    (ws://127.0.0.1:8765/marwa-core — NDJSON أحداث حية).
//   3) 'mock'      — لا جسر متاح بعد → حالة صادقة موسومة MOCK
//                    (الواجهة تُعرض كاملة بأشرطة تحميل وحالات «بانتظار الجسر»).
//
// القاعدة: هذا الملف هو **البوابة الوحيدة** للاتصال بالمحرك — لا fetch مباشر
// في المكونات، وكل استدعاء يمر عبر call<T>() لتوحيد الأخطاء وإعادة المحاولة.

export type TransportKind = 'tauri' | 'websocket' | 'mock'

export type DshEvent =
  | { type: 'stats'; payload: Record<string, unknown> }
  | { type: 'agent_message'; payload: { agentId: string; role: 'user' | 'assistant' | 'system'; content: string } }
  | { type: 'tool_call'; payload: { agentId: string; tool: string; args: Record<string, unknown> } }
  | { type: 'tool_result'; payload: { agentId: string; tool: string; result: unknown; ms: number } }
  | { type: 'scratchpad'; payload: { agentId: string; thought: string } }
  | { type: 'status'; payload: { transport: TransportKind; connected: boolean } }

type EventListener = (e: DshEvent) => void

const WS_URL = import.meta.env.VITE_DSH_WS_URL || 'ws://127.0.0.1:8765/marwa-core'

class DshIpc {
  private transport: TransportKind = 'mock'
  private listeners = new Set<EventListener>()
  private ws: WebSocket | null = null
  private wsRetryTimer: ReturnType<typeof setTimeout> | null = null
  private requestId = 0
  private pending = new Map<number, { resolve: (v: unknown) => void; reject: (e: Error) => void }>()

  /** الوسيلة الفعلية — تُحدَّد مرة عند الإقلاع */
  get kind(): TransportKind {
    return this.transport
  }

  /** الإقلاع: كشف البيئة ثم فتح القناة المناسبة */
  async boot(): Promise<TransportKind> {
    const w = window as unknown as { __TAURI_INTERNALS__?: unknown }
    if (w.__TAURI_INTERNALS__) {
      this.transport = 'tauri'
      this.emit({ type: 'status', payload: { transport: 'tauri', connected: true } })
      return 'tauri'
    }
    try {
      await this.openWebSocket()
      this.transport = 'websocket'
      this.emit({ type: 'status', payload: { transport: 'websocket', connected: true } })
      return 'websocket'
    } catch {
      this.transport = 'mock'
      this.emit({ type: 'status', payload: { transport: 'mock', connected: false } })
      return 'mock'
    }
  }

  private openWebSocket(): Promise<void> {
    return new Promise((resolve, reject) => {
      try {
        const ws = new WebSocket(WS_URL)
        const failTimer = setTimeout(() => {
          ws.close()
          reject(new Error('websocket timeout'))
        }, 3000)
        ws.onopen = () => {
          clearTimeout(failTimer)
          this.ws = ws
          resolve()
        }
        ws.onerror = () => {
          clearTimeout(failTimer)
          reject(new Error('websocket error'))
        }
        ws.onmessage = (ev) => {
          try {
            const parsed = JSON.parse(ev.data as string) as DshEvent & { __req?: number }
            if (parsed.__req && this.pending.has(parsed.__req)) {
              const p = this.pending.get(parsed.__req)!
              this.pending.delete(parsed.__req)
              p.resolve(parsed.payload)
              return
            }
            this.emit(parsed)
          } catch {
            /* رسالة غير قابلة للتحليل — نتجاهل بصمت */
          }
        }
        ws.onclose = () => {
          this.ws = null
          this.emit({ type: 'status', payload: { transport: this.transport, connected: false } })
          // إعادة محاولة صادقة كل 15 ثانية
          if (this.wsRetryTimer) clearTimeout(this.wsRetryTimer)
          this.wsRetryTimer = setTimeout(() => void this.boot(), 15_000)
        }
      } catch (e) {
        reject(e instanceof Error ? e : new Error(String(e)))
      }
    })
  }

  private emit(e: DshEvent): void {
    this.listeners.forEach((l) => l(e))
  }

  /** الاشتراك في الأحداث الحية (الإحصاءات، الرسائل، استدعاءات الأدوات) */
  subscribe(listener: EventListener): () => void {
    this.listeners.add(listener)
    return () => this.listeners.delete(listener)
  }

  /** استدعاء عام موحد — يمر عبر الوسيلة النشطة (يعمل أيضاً في وضع mock بقيم موسومة) */
  async call<T = unknown>(method: string, payload?: Record<string, unknown>): Promise<T> {
    if (this.transport === 'tauri') {
      const w = window as unknown as { __TAURI_INTERNALS__: { invoke: (cmd: string, args?: unknown) => Promise<unknown> } }
      return (await w.__TAURI_INTERNALS__.invoke(`dsh_${method}`, { payload: payload ?? {} })) as T
    }
    if (this.transport === 'websocket' && this.ws?.readyState === WebSocket.OPEN) {
      const id = ++this.requestId
      return new Promise<T>((resolve, reject) => {
        this.pending.set(id, {
          resolve: resolve as (v: unknown) => void,
          reject: reject as (e: Error) => void,
        })
        this.ws!.send(JSON.stringify({ method, payload: payload ?? {}, __req: id }))
        setTimeout(() => {
          if (this.pending.has(id)) {
            this.pending.delete(id)
            reject(new Error(`انتهت مهلة ${method}`))
          }
        }, 60_000)
      })
    }
    throw new Error(`MOCK: لا جسر متاح لـ${method} — الواجهة في وضع العرض المحلي`)
  }
}

/** المثال الوحيد — تُستورد من كل المكونات */
export const dsh = new DshIpc()
