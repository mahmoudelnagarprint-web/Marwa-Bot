'use client'

// components/marwa/facebook-comments-panel.tsx — تعليقات فيسبوك بانتظار اعتماد رد سلمى
// MARWA CORE task-7: يعرض (المعلق • نص التعليق • المنشور • الرد المقترح من سلمى)
// مع [اعتماد وإرسال] و[تعديل الرد] — يقرأ من facebook_interactions عبر /api/facebook.
// يُركَّب في غرفة سلمى (تبويب مخصص) — بلا أي رموز، منتهي الصلاحية كواجهة عرض فقط.

import { useCallback, useEffect, useState } from 'react'
import { Check, Facebook, Loader2, MessageSquare, Pencil, RefreshCw, X } from 'lucide-react'
import { cn } from '@/lib/utils'

type Interaction = {
  id: string
  page_name: string
  commenter_name: string
  comment_text: string
  post_preview: string | null
  suggested_reply: string | null
  reply_status: 'pending' | 'approved' | 'sent' | 'rejected' | 'skipped'
  replied_at: string | null
  created_at: string
}

const statusLabel: Record<string, string> = {
  pending: 'بانتظار اعتمادك',
  approved: 'معتمد — جارٍ الإرسال',
  sent: 'تم الرد ✓',
  rejected: 'مرفوض',
  skipped: 'متجاهل',
}

const statusChip: Record<string, string> = {
  pending: 'border-amber-400/20 bg-amber-400/10 text-amber-300',
  approved: 'border-sky-400/20 bg-sky-400/10 text-sky-300',
  sent: 'border-emerald-400/20 bg-emerald-400/10 text-emerald-300',
  rejected: 'border-rose-400/20 bg-rose-400/10 text-rose-300',
  skipped: 'border-zinc-400/20 bg-zinc-400/10 text-zinc-300',
}

export function FacebookCommentsPanel({ agentName }: { agentName: string }) {
  const [items, setItems] = useState<Interaction[]>([])
  const [loading, setLoading] = useState(true)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editText, setEditText] = useState('')
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch('/api/facebook/interactions', { cache: 'no-store' })
      const data = await res.json()
      if (!data?.success) {
        setError(data?.error ?? 'خطأ غير معروف')
        return
      }
      setItems(data.interactions ?? [])
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const decide = async (id: string, action: 'approve' | 'reject', editedReply?: string) => {
    setBusyId(id)
    setError(null)
    try {
      const res = await fetch('/api/facebook/interactions/decide', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id, action, editedReply }),
      })
      const data = await res.json()
      if (!data?.success) {
        setError(data?.error ?? 'فشل تنفيذ القرار')
        return
      }
      setEditingId(null)
      void load()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusyId(null)
    }
  }

  const pending = items.filter((i) => i.reply_status === 'pending')
  const decided = items.filter((i) => i.reply_status !== 'pending')

  return (
    <div className="space-y-4" aria-label="تعليقات فيسبوك">
      <div className="flex items-center justify-between">
        <p className="flex items-center gap-1.5 text-sm font-medium">
          <Facebook className="size-4 text-sky-300" aria-hidden="true" />
          تعليقات فيسبوك — ردود {agentName} المقترحة
        </p>
        <button
          type="button"
          onClick={() => void load()}
          className="rounded border border-border px-2 py-0.5 text-[10px] text-muted-foreground hover:bg-sidebar-accent/60"
        >
          <RefreshCw className="inline size-3" /> تحديث
        </button>
      </div>

      {error && (
        <p className="rounded-lg border border-rose-400/20 bg-rose-400/10 px-2 py-1 text-xs text-rose-300">⚠️ {error}</p>
      )}
      {loading && (
        <p className="flex items-center gap-2 py-3 text-xs text-muted-foreground" aria-busy="true">
          <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
          جارٍ قراءة التفاعلات…
        </p>
      )}

      {!loading && pending.length === 0 && decided.length === 0 && (
        <div className="rounded-xl border border-dashed border-border bg-card/40 p-6 text-center">
          <MessageSquare className="mx-auto mb-2 size-7 text-muted-foreground/60" aria-hidden="true" />
          <p className="text-sm font-semibold">لا تعليقات فيسبوك بانتظار الرد الآن</p>
          <p className="mt-1 text-xs text-muted-foreground">
            اضغط «تشغيل دورة الإشراف» من تاب كوكو — يجلب التعليقات ويجهز ردود سلمى تلقائياً.
          </p>
        </div>
      )}

      {[...pending, ...decided].map((item) => {
        const isPending = item.reply_status === 'pending'
        const isEditing = editingId === item.id
        const busy = busyId === item.id
        return (
          <div key={item.id} className="rounded-xl border border-border bg-card p-3.5 space-y-2">
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <p className="flex items-center gap-1.5 text-sm font-semibold text-foreground">
                  <Facebook className="size-3.5 text-sky-300" aria-hidden="true" />
                  {item.commenter_name}
                  <span className="rounded bg-secondary px-1.5 py-0.5 text-[10px] font-normal text-muted-foreground">
                    {item.page_name}
                  </span>
                </p>
                <p className="mt-0.5 text-xs text-muted-foreground">«{item.comment_text}»</p>
                {item.post_preview && (
                  <p className="mt-1 truncate text-[10px] text-muted-foreground/80" title={item.post_preview}>
                    ↳ منشور: {item.post_preview}
                  </p>
                )}
              </div>
              <span className={cn('shrink-0 rounded border px-1.5 py-0.5 text-[10px] font-medium', statusChip[item.reply_status] ?? '')}>
                {statusLabel[item.reply_status] ?? item.reply_status}
              </span>
            </div>

            {/* الرد المقترح — قابل للتعديل */}
            <div className="rounded-lg border border-sky-400/20 bg-sky-400/[0.06] p-2.5">
              <p className="mb-1 text-[10px] font-medium text-sky-300">💬 الرد المقترح من {agentName}:</p>
              {isEditing ? (
                <textarea
                  value={editText}
                  onChange={(e) => setEditText(e.target.value)}
                  rows={3}
                  className="w-full resize-none rounded-md border border-border bg-background px-2 py-1.5 text-xs text-foreground outline-none focus:border-primary"
                  autoFocus
                />
              ) : (
                <p className="whitespace-pre-wrap text-xs leading-relaxed text-foreground">{item.suggested_reply ?? '—'}</p>
              )}
            </div>

            {isPending && (
              <div className="flex items-center gap-2">
                {isEditing ? (
                  <>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void decide(item.id, 'approve', editText)}
                      className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-500/15 px-3 py-1.5 text-xs font-semibold text-emerald-300 border border-emerald-500/30 hover:bg-emerald-500/25 disabled:opacity-50"
                    >
                      {busy ? <Loader2 className="size-3.5 animate-spin" /> : <Check className="size-3.5" />}
                      اعتماد المعدّل وإرسال
                    </button>
                    <button
                      type="button"
                      onClick={() => setEditingId(null)}
                      className="rounded-lg border border-border px-3 py-1.5 text-xs text-muted-foreground hover:bg-sidebar-accent/60"
                    >
                      إلغاء التعديل
                    </button>
                  </>
                ) : (
                  <>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void decide(item.id, 'approve')}
                      className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-500/15 px-3 py-1.5 text-xs font-semibold text-emerald-300 border border-emerald-500/30 hover:bg-emerald-500/25 disabled:opacity-50"
                    >
                      {busy ? <Loader2 className="size-3.5 animate-spin" /> : <Check className="size-3.5" />}
                      اعتماد وإرسال
                    </button>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => {
                        setEditingId(item.id)
                        setEditText(item.suggested_reply ?? '')
                      }}
                      className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-xs font-semibold text-foreground hover:bg-sidebar-accent/60 disabled:opacity-50"
                    >
                      <Pencil className="size-3.5" />
                      تعديل الرد
                    </button>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void decide(item.id, 'reject')}
                      className="inline-flex items-center gap-1.5 rounded-lg border border-rose-400/20 px-2.5 py-1.5 text-xs text-rose-300 hover:bg-rose-400/10 disabled:opacity-50"
                      title="رفض — يُحفظ للتعلم بلا حذف"
                    >
                      <X className="size-3.5" />
                      رفض
                    </button>
                  </>
                )}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
