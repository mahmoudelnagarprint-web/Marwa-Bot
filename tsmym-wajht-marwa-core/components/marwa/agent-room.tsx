'use client'

import { useEffect, useRef, useState } from 'react'
import {
  ArrowRight,
  Bot,
  CheckCircle2,
  Clock,
  FileText,
  ListTodo,
  Loader2,
  MessageSquare,
  Paperclip,
  Plus,
  Send,
  Square,
  Trash2,
  User,
  X,
  XCircle,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { type Agent } from '@/lib/marwa-data'
import { supabase } from '@/lib/supabase'
import {
  fetchAgentTasks,
  fetchAgentUpdates,
  formatCairoDate,
  insertAgentTask,
  updateAgentTaskStatus,
  updateAgentUpdateStatus,
  type AgentTask,
  type AgentUpdate,
} from '@/lib/agent-tasks'

type TabId = 'chat' | 'tasks' | 'updates'

type ChatMessage = {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  time: string
  model?: string
  latency_ms?: number
}

export function AgentRoom({
  agent,
  onBack,
}: {
  agent: Agent
  onBack: () => void
}) {
  const [tab, setTab] = useState<TabId>('chat')

  // ──────────────────────── 1. تبويب الشات (Live Streaming Chat) ────────────────────────
  const storageKey = `marwa_chat_${agent.id}`
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [isGenerating, setIsGenerating] = useState(false)
  const abortControllerRef = useRef<AbortController | null>(null)
  const chatBottomRef = useRef<HTMLDivElement>(null)

  // 📄 OCR محلي (indra-ocr): صورة مرفقة تُستخرج نصوصها آلياً قبل الإرسال
  const [attachedImage, setAttachedImage] = useState<{ file: File; previewUrl: string } | null>(null)
  const [ocrBusy, setOcrBusy] = useState(false)
  const [ocrError, setOcrError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const addImageFile = (file: File) => {
    if (!file.type.startsWith('image/')) {
      setOcrError('الملف المرفق ليس صورة')
      return
    }
    if (file.size > 15 * 1024 * 1024) {
      setOcrError('الصورة أكبر من 15 ميجابايت — الحد الأقصى 15MB')
      return
    }
    if (attachedImage) URL.revokeObjectURL(attachedImage.previewUrl)
    setOcrError(null)
    setAttachedImage({ file, previewUrl: URL.createObjectURL(file) })
  }

  const removeImage = () => {
    if (attachedImage) URL.revokeObjectURL(attachedImage.previewUrl)
    setAttachedImage(null)
  }

  // تحميل الرسائل من localStorage عند فتح الغرفة
  useEffect(() => {
    try {
      const saved = localStorage.getItem(storageKey)
      if (saved) {
        setMessages(JSON.parse(saved))
      } else {
        const initial: ChatMessage = {
          id: `${agent.id}-welcome`,
          role: 'assistant',
          content: `أهلاً بك يا محمود في غرفة ${agent.name}. ${agent.tagline}`,
          time: new Date().toLocaleTimeString('ar-EG', { hour: '2-digit', minute: '2-digit' }),
        }
        setMessages([initial])
      }
    } catch {
      // تجاهل أخطاء التخزين
    }
  }, [agent.id, storageKey, agent.name, agent.tagline])

  // حفظ الرسائل في localStorage
  useEffect(() => {
    if (messages.length > 0) {
      try {
        localStorage.setItem(storageKey, JSON.stringify(messages))
      } catch {
        // storage full
      }
    }
  }, [messages, storageKey])

  // التمرير التلقائي لآخر رسالة
  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isGenerating])

  // إرسال رسالة الشات مع دعم البث والإيقاف — وإن وُجدت صورة مرفقة: رفع صامت
  // إلى /api/ocr أولاً (indra-ocr محلي) ثم حقن النص المستخرج أسفل رسالة المستخدم.
  const handleSendChat = async () => {
    let text = input.trim()
    if ((!text && !attachedImage) || isGenerating || ocrBusy) return

    // 📄 الرفع الصامت للصورة واستخراج النص قبل الإرسال
    if (attachedImage) {
      setOcrBusy(true)
      setOcrError(null)
      try {
        const fd = new FormData()
        fd.append('file', attachedImage.file)
        const ocrRes = await fetch('/api/ocr', { method: 'POST', body: fd })
        const ocrData = (await ocrRes.json()) as { success?: boolean; text?: string; error?: string }
        if (ocrData?.success && ocrData.text) {
          text = `${text ? text + '\n\n' : ''}---\n📄 *محتوى الصورة المرفقة (تم استخراجه آلياً):*\n${ocrData.text}`
        } else {
          setOcrError(ocrData?.error || 'تعذر استخراج نص الصورة — أزل الصورة أو أعد المحاولة')
          setOcrBusy(false)
          return // إيقاف الإرسال حتى يقرر المستخدم
        }
      } catch (ocrErr) {
        setOcrError(ocrErr instanceof Error ? ocrErr.message : 'فشل رفع الصورة لاستخراج النص')
        setOcrBusy(false)
        return
      }
      setOcrBusy(false)
      removeImage()
    }

    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: text,
      time: new Date().toLocaleTimeString('ar-EG', { hour: '2-digit', minute: '2-digit' }),
    }

    const nextHistory = [...messages, userMsg]
    setMessages(nextHistory)
    setInput('')
    setIsGenerating(true)

    const botMsgId = crypto.randomUUID()
    const tempBotMsg: ChatMessage = {
      id: botMsgId,
      role: 'assistant',
      content: '',
      time: new Date().toLocaleTimeString('ar-EG', { hour: '2-digit', minute: '2-digit' }),
    }

    setMessages((prev) => [...prev, tempBotMsg])

    const abortCtrl = new AbortController()
    abortControllerRef.current = abortCtrl

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        signal: abortCtrl.signal,
        body: JSON.stringify({
          agent: agent.id,
          messages: nextHistory.slice(-8).map((m) => ({
            role: m.role === 'user' ? 'user' : 'assistant',
            content: m.content,
          })),
        }),
      })

      const data = (await res.json()) as {
        ok?: boolean
        text?: string
        reason?: string
        provider?: { model?: string }
        latency_ms?: number
      }

      if (data.ok && data.text) {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === botMsgId
              ? {
                  ...m,
                  content: data.text || '',
                  model: data.provider?.model,
                  latency_ms: data.latency_ms,
                }
              : m,
          ),
        )
      } else {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === botMsgId
              ? {
                  ...m,
                  content: data.reason || 'تعذر الحصول على رد من الوكيل، يرجى المحاولة لاحقاً.',
                }
              : m,
          ),
        )
      }
    } catch (err: unknown) {
      if (err instanceof Error && err.name === 'AbortError') {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === botMsgId
              ? { ...m, content: m.content ? `${m.content} [تم إيقاف التوليد]` : '[تم إيقاف التوليد بطلبك]' }
              : m,
          ),
        )
      } else {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === botMsgId
              ? { ...m, content: 'حدث خطأ في الاتصال بنظام الذكاء الاصطناعي.' }
              : m,
          ),
        )
      }
    } finally {
      setIsGenerating(false)
      abortControllerRef.current = null
    }
  }

  const handleStopGeneration = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }
  }

  const handleClearChat = () => {
    if (window.confirm('هل تريد مسح سجل المحادثة مع هذا الوكيل؟')) {
      const initial: ChatMessage = {
        id: `${agent.id}-welcome`,
        role: 'assistant',
        content: `تم مسح السجل. أهلاً بك مجدداً في غرفة ${agent.name}.`,
        time: new Date().toLocaleTimeString('ar-EG', { hour: '2-digit', minute: '2-digit' }),
      }
      setMessages([initial])
      localStorage.removeItem(storageKey)
    }
  }

  // ──────────────────────── 2. تبويب المهام (Tasks) ────────────────────────
  const [tasks, setTasks] = useState<AgentTask[]>([])
  const [taskStatusFilter, setTaskStatusFilter] = useState<'all' | 'pending' | 'in_progress' | 'done' | 'rejected'>('all')
  const [newTaskTitle, setNewTaskTitle] = useState('')
  const [newTaskDesc, setNewTaskDesc] = useState('')
  const [newTaskPriority, setNewTaskPriority] = useState<'low' | 'normal' | 'high' | 'urgent'>('normal')
  const [isAddingTask, setIsAddingTask] = useState(false)
  const [tasksLoading, setTasksLoading] = useState(false)

  const loadTasks = async () => {
    if (!supabase) return
    setTasksLoading(true)
    const { tasks: items } = await fetchAgentTasks(supabase, agent.id)
    setTasks(items)
    setTasksLoading(false)
  }

  useEffect(() => {
    if (tab === 'tasks') {
      void loadTasks()
    }
  }, [tab, agent.id])

  const handleCreateTask = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newTaskTitle.trim() || !supabase) return
    setIsAddingTask(true)
    const { ok, row } = await insertAgentTask(supabase, {
      agent_id: agent.id,
      title: newTaskTitle,
      description: newTaskDesc,
      priority: newTaskPriority,
    })
    setIsAddingTask(false)
    if (ok && row) {
      setTasks((prev) => [row, ...prev])
      setNewTaskTitle('')
      setNewTaskDesc('')
    }
  }

  const handleUpdateTaskStatus = async (
    taskId: string,
    newStatus: 'pending' | 'in_progress' | 'done' | 'rejected',
  ) => {
    if (!supabase) return
    setTasks((prev) =>
      prev.map((t) => (t.id === taskId ? { ...t, status: newStatus, updated_at: new Date().toISOString() } : t)),
    )
    await updateAgentTaskStatus(supabase, taskId, newStatus)
  }

  const filteredTasks = tasks.filter((t) => {
    if (taskStatusFilter === 'all') return true
    return t.status === taskStatusFilter
  })

  // ──────────────────────── 3. تبويب التحديثات والتقارير (Updates & Reports) ────────────────────────
  const [updates, setUpdates] = useState<AgentUpdate[]>([])
  const [updateKindFilter, setUpdateKindFilter] = useState<'all' | 'complaint' | 'suggestion' | 'alert' | 'report'>('all')
  const [updatesLoading, setUpdatesLoading] = useState(false)
  const [decidingId, setDecidingId] = useState<string | null>(null)

  const loadUpdates = async () => {
    if (!supabase) return
    setUpdatesLoading(true)
    const { items } = await fetchAgentUpdates(supabase, agent.id)
    setUpdates(items)
    setUpdatesLoading(false)
  }

  useEffect(() => {
    if (tab === 'updates') {
      void loadUpdates()
    }
  }, [tab, agent.id])

  const handleUpdateDecision = async (id: string, decision: 'approved' | 'rejected') => {
    if (!supabase) return
    setDecidingId(id)
    const { ok } = await updateAgentUpdateStatus(supabase, id, decision)
    setDecidingId(null)
    if (ok) {
      setUpdates((prev) =>
        prev.map((u) => (u.id === id ? { ...u, status: decision, decided_by: 'mahmoud' } : u)),
      )
    }
  }

  const filteredUpdates = updates.filter((u) => {
    if (updateKindFilter === 'all') return true
    return u.kind === updateKindFilter
  })

  return (
    <div className="flex h-full flex-col overflow-hidden bg-background">
      {/* ترويسة الغرفة: أيقونة الوكيل الكبيرة واسمه ومسماه */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-border bg-card/60 px-4 py-3.5 md:px-6">
        <div className="flex items-center gap-3.5">
          <button
            type="button"
            onClick={onBack}
            className="flex size-9 items-center justify-center rounded-xl border border-border bg-card text-muted-foreground transition-colors hover:border-primary hover:text-foreground"
            title="العودة لنظرة عامة"
          >
            <ArrowRight className="size-4" />
          </button>

          {/* أيقونة الوكيل الكبيرة مع شارة Glyph */}
          <div className="flex size-11 items-center justify-center rounded-xl bg-primary/20 border border-primary/40 font-display text-2xl font-bold text-primary gold-glow">
            {agent.glyph}
          </div>

          <div>
            <div className="flex items-center gap-2">
              <h2 className="font-display text-xl md:text-2xl font-bold text-foreground">
                {agent.name}
              </h2>
              <span className="rounded-full bg-emerald-500/20 px-2 py-0.5 text-[10px] font-semibold text-emerald-400 border border-emerald-500/30">
                متصل الآن
              </span>
            </div>
            <p className="text-xs text-muted-foreground line-clamp-1">{agent.role}</p>
          </div>
        </div>

        {/* أزرار التبويبات الثلاثة الرئيسية */}
        <div className="flex rounded-xl border border-border bg-secondary/60 p-1">
          <button
            type="button"
            onClick={() => setTab('chat')}
            className={cn(
              'flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-semibold transition-all',
              tab === 'chat'
                ? 'bg-primary text-primary-foreground shadow-sm'
                : 'text-muted-foreground hover:text-foreground',
            )}
          >
            <MessageSquare className="size-3.5" />
            <span>الشات الحي</span>
          </button>

          <button
            type="button"
            onClick={() => setTab('tasks')}
            className={cn(
              'flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-semibold transition-all',
              tab === 'tasks'
                ? 'bg-primary text-primary-foreground shadow-sm'
                : 'text-muted-foreground hover:text-foreground',
            )}
          >
            <ListTodo className="size-3.5" />
            <span>المهام</span>
          </button>

          <button
            type="button"
            onClick={() => setTab('updates')}
            className={cn(
              'flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-semibold transition-all',
              tab === 'updates'
                ? 'bg-primary text-primary-foreground shadow-sm'
                : 'text-muted-foreground hover:text-foreground',
            )}
          >
            <FileText className="size-3.5" />
            <span>التحديثات والتقارير</span>
          </button>
        </div>
      </div>

      {/* المحتوى بحسب التبويب */}
      <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
        {/* 1. تبويب الشات (Live Streaming Chat) */}
        {tab === 'chat' && (
          <div className="flex flex-1 flex-col overflow-hidden">
            {/* رأس الشات مع زر المسح */}
            <div className="flex items-center justify-between border-b border-border/60 px-4 py-2 text-xs text-muted-foreground bg-card/30">
              <span className="flex items-center gap-1.5">
                <Bot className="size-3.5 text-primary" />
                <span>محادثة مباشرة مع النموذج الخاص بـ {agent.name} (محفوظة محلياً)</span>
              </span>
              <button
                type="button"
                onClick={handleClearChat}
                className="flex items-center gap-1 text-muted-foreground hover:text-destructive transition-colors"
                title="مسح محادثة الوكيل"
              >
                <Trash2 className="size-3.5" />
                <span>مسح</span>
              </button>
            </div>

            {/* نافذة الرسائل مع خاصية التمرير التلقائي */}
            <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-4 scrollbar-thin">
              {messages.map((msg) => {
                const isUser = msg.role === 'user'

                return (
                  <div
                    key={msg.id}
                    className={cn(
                      'flex items-start gap-3 max-w-[85%] md:max-w-[75%]',
                      isUser ? 'ms-auto flex-row-reverse' : 'me-auto',
                    )}
                  >
                    <div
                      className={cn(
                        'flex size-8 shrink-0 items-center justify-center rounded-lg border font-display text-sm font-bold',
                        isUser
                          ? 'border-primary/40 bg-primary/20 text-primary'
                          : 'border-border bg-card text-foreground',
                      )}
                    >
                      {isUser ? <User className="size-4" /> : agent.glyph}
                    </div>

                    <div
                      className={cn(
                        'rounded-2xl px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap',
                        isUser
                          ? 'bg-primary text-primary-foreground font-medium rounded-ee-sm'
                          : 'bg-card border border-border text-foreground rounded-es-sm shadow-sm',
                      )}
                    >
                      {msg.content}

                      {/* شارة النموذج وزمن الاستجابة للردود */}
                      {!isUser && msg.model && (
                        <div className="mt-2 pt-1 border-t border-border/40 flex items-center justify-between text-[10px] text-muted-foreground">
                          <span className="font-mono">{msg.model}</span>
                          {msg.latency_ms ? <span>{msg.latency_ms}ms</span> : null}
                        </div>
                      )}

                      <span
                        className={cn(
                          'block mt-1 text-[10px] text-end opacity-70 font-mono',
                          isUser ? 'text-primary-foreground/80' : 'text-muted-foreground',
                        )}
                      >
                        {msg.time}
                      </span>
                    </div>
                  </div>
                )
              })}

              {/* مؤشر جاري الكتابة / التوليد */}
              {isGenerating && (
                <div className="flex items-center gap-2 text-xs text-muted-foreground me-auto">
                  <div className="flex size-7 items-center justify-center rounded-lg border border-border bg-card font-display text-xs font-bold text-primary">
                    {agent.glyph}
                  </div>
                  <div className="flex items-center gap-1.5 rounded-full bg-card px-3 py-1.5 border border-border">
                    <Loader2 className="size-3.5 animate-spin text-primary" />
                    <span>{agent.name} يكتب الرد الآن…</span>
                  </div>
                </div>
              )}

              <div ref={chatBottomRef} />
            </div>

            {/* شريط كتابة الرسالة مع Enter للإرسال وزر إيقاف التوليد + إرفاق صورة (OCR محلي indra-ocr) */}
            <div className="border-t border-border bg-card/60 p-3 md:p-4">
              {attachedImage && (
                <div className="mb-2 flex items-center gap-2 rounded-lg border border-border bg-background p-2">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={attachedImage.previewUrl}
                    alt="معاينة الصورة المرفقة"
                    className="size-14 shrink-0 rounded-md border border-border object-cover"
                  />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs text-foreground">{attachedImage.file.name}</p>
                    <p className="text-[10px] text-muted-foreground">
                      {(attachedImage.file.size / 1024).toFixed(0)} ك.ب — يُستخرج نصها آلياً عند الإرسال (OCR محلي)
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={removeImage}
                    className="rounded-md border border-border p-1 text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
                    aria-label="إزالة الصورة"
                  >
                    <X className="size-3.5" />
                  </button>
                </div>
              )}

              {ocrBusy && (
                <p className="mb-2 flex items-center gap-2 text-xs text-muted-foreground" aria-busy="true">
                  <Loader2 className="size-3.5 animate-spin text-primary" />
                  جارٍ استخراج نص الصورة محلياً (OCR)…
                </p>
              )}

              {ocrError && (
                <p className="mb-2 rounded-lg border border-rose-400/20 bg-rose-400/10 px-2 py-1 text-xs text-rose-300">
                  ⚠️ {ocrError}
                </p>
              )}

              <div className="relative flex items-center gap-2">
                <textarea
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onPaste={(e) => {
                    const img = Array.from(e.clipboardData?.files ?? []).find((f) => f.type.startsWith('image/'))
                    if (img) {
                      e.preventDefault()
                      addImageFile(img)
                    }
                  }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault()
                      void handleSendChat()
                    }
                  }}
                  placeholder={`اكتب رسالتك لـ ${agent.name} (Enter للإرسال • الصق صورة ليقرأها الوكيل)…`}
                  rows={1}
                  className="w-full resize-none rounded-xl border border-border bg-background px-4 py-3 pe-32 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary scrollbar-thin"
                />

                <div className="absolute end-2 flex items-center gap-1.5">
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/png,image/jpeg,image/webp,image/bmp,image/tiff"
                    className="hidden"
                    onChange={(e) => {
                      const f = e.target.files?.[0]
                      if (f) addImageFile(f)
                      e.target.value = ''
                    }}
                  />
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={isGenerating || ocrBusy}
                    className="rounded-lg border border-border p-2 text-muted-foreground transition-colors hover:bg-sidebar-accent/60 disabled:opacity-40"
                    aria-label="إرفاق صورة (OCR محلي)"
                    title="إرفاق صورة — يُستخرج نصها آلياً (indra-ocr محلي)"
                  >
                    <Paperclip className="size-4" />
                  </button>
                  {isGenerating ? (
                    <button
                      type="button"
                      onClick={handleStopGeneration}
                      className="flex items-center gap-1 rounded-lg bg-destructive px-3 py-1.5 text-xs font-semibold text-destructive-foreground transition-all hover:bg-destructive/90"
                    >
                      <Square className="size-3 fill-current" />
                      <span>إيقاف</span>
                    </button>
                  ) : (
                    <button
                      type="button"
                      disabled={(!input.trim() && !attachedImage) || ocrBusy}
                      onClick={() => void handleSendChat()}
                      className="flex items-center gap-1 rounded-lg bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground transition-all hover:bg-primary/90 disabled:opacity-40"
                    >
                      <Send className="size-3.5 rotate-180" />
                      <span>إرسال</span>
                    </button>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* 2. تبويب المهام (Tasks) مع Audit Trail (حظر الحذف) */}
        {tab === 'tasks' && (
          <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-6 scrollbar-thin">
            {/* إضافة مهمة جديدة مباشرة للوكيل */}
            <form
              onSubmit={handleCreateTask}
              className="rounded-xl border border-border bg-card p-4 space-y-3"
            >
              <div className="flex items-center justify-between">
                <h3 className="font-display text-sm font-bold text-foreground flex items-center gap-2">
                  <Plus className="size-4 text-primary" />
                  <span>إسناد مهمة جديدة لـ {agent.name}</span>
                </h3>
                <span className="text-[11px] text-muted-foreground">تُسجل فوراً في السحابة</span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                <input
                  type="text"
                  required
                  value={newTaskTitle}
                  onChange={(e) => setNewTaskTitle(e.target.value)}
                  placeholder="عنوان المهمة (مثال: فحص رصيد العميل أحمد)..."
                  className="md:col-span-2 rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none"
                />

                <input
                  type="text"
                  value={newTaskDesc}
                  onChange={(e) => setNewTaskDesc(e.target.value)}
                  placeholder="تفاصيل إضافية (اختياري)..."
                  className="rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none"
                />

                <div className="flex items-center gap-2">
                  <select
                    value={newTaskPriority}
                    onChange={(e) => setNewTaskPriority(e.target.value as typeof newTaskPriority)}
                    className="flex-1 rounded-lg border border-border bg-background px-3 py-2 text-xs text-foreground focus:border-primary focus:outline-none"
                  >
                    <option value="low">أولوية منخفضة</option>
                    <option value="normal">أولوية عادية</option>
                    <option value="high">أولوية عالية</option>
                    <option value="urgent">أولوية عاجلة</option>
                  </select>

                  <button
                    type="submit"
                    disabled={isAddingTask || !newTaskTitle.trim()}
                    className="flex items-center gap-1 rounded-lg bg-primary px-4 py-2 text-xs font-semibold text-primary-foreground hover:bg-primary/90 disabled:opacity-40"
                  >
                    {isAddingTask ? <Loader2 className="size-3.5 animate-spin" /> : <Plus className="size-3.5" />}
                    <span>إسناد</span>
                  </button>
                </div>
              </div>
            </form>

            {/* فلاتر حالات المهام */}
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border/60 pb-3">
              <div className="flex flex-wrap items-center gap-1.5">
                {(['all', 'pending', 'in_progress', 'done', 'rejected'] as const).map((st) => {
                  const labels = {
                    all: 'الكل',
                    pending: 'معلقة',
                    in_progress: 'جارية',
                    done: 'منجزة',
                    rejected: 'مرفوضة',
                  }
                  const count =
                    st === 'all' ? tasks.length : tasks.filter((t) => t.status === st).length

                  return (
                    <button
                      key={st}
                      type="button"
                      onClick={() => setTaskStatusFilter(st)}
                      className={cn(
                        'flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs font-medium transition-colors',
                        taskStatusFilter === st
                          ? 'bg-primary/20 text-primary border border-primary/30 font-semibold'
                          : 'bg-secondary/60 text-muted-foreground hover:text-foreground',
                      )}
                    >
                      <span>{labels[st]}</span>
                      <span className="rounded-full bg-background/60 px-1.5 text-[10px] font-mono">
                        {count}
                      </span>
                    </button>
                  )
                })}
              </div>

              <span className="text-xs text-muted-foreground">حظر الحذف نهائياً (Audit Trail مفعل)</span>
            </div>

            {/* قائمة المهام */}
            {tasksLoading ? (
              <div className="flex items-center justify-center p-8 text-sm text-muted-foreground">
                <Loader2 className="size-4 animate-spin me-2" />
                <span>جاري تحميل المهام…</span>
              </div>
            ) : filteredTasks.length === 0 ? (
              <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border p-8 text-center text-muted-foreground">
                <ListTodo className="size-8 mb-2 opacity-50" />
                <p className="text-sm">لا توجد مهام مطابقة لهذا الفلتر</p>
              </div>
            ) : (
              <div className="space-y-2.5">
                {filteredTasks.map((t) => (
                  <div
                    key={t.id}
                    className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 rounded-xl border border-border bg-card p-3.5 transition-colors hover:border-border/80"
                  >
                    <div className="space-y-1 min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <span
                          className={cn(
                            'rounded px-2 py-0.5 text-[10px] font-semibold',
                            t.status === 'in_progress' && 'bg-primary/20 text-primary border border-primary/30',
                            t.status === 'pending' && 'bg-warning/20 text-warning',
                            t.status === 'done' && 'bg-emerald-500/20 text-emerald-400',
                            t.status === 'rejected' && 'bg-destructive/20 text-destructive',
                          )}
                        >
                          {t.status === 'in_progress' && 'جارية الآن'}
                          {t.status === 'pending' && 'معلقة'}
                          {t.status === 'done' && 'منجزة ✅'}
                          {t.status === 'rejected' && 'مرفوضة ❌'}
                        </span>

                        <span className="rounded bg-secondary px-1.5 py-0.5 text-[10px] text-muted-foreground">
                          أولوية: {t.priority}
                        </span>

                        <span className="text-[11px] text-muted-foreground font-mono flex items-center gap-1">
                          <Clock className="size-3" />
                          <span>{formatCairoDate(t.created_at)}</span>
                        </span>
                      </div>

                      <h4 className="text-sm font-semibold text-foreground">{t.title}</h4>
                      {t.description && (
                        <p className="text-xs text-muted-foreground">{t.description}</p>
                      )}
                    </div>

                    {/* تغيير حالة المهمة بسلاسة (لا حذف نهائياً) */}
                    <div className="flex items-center gap-1.5 shrink-0 self-end sm:self-center">
                      <select
                        value={t.status}
                        onChange={(e) =>
                          void handleUpdateTaskStatus(
                            t.id,
                            e.target.value as 'pending' | 'in_progress' | 'done' | 'rejected',
                          )
                        }
                        className="rounded-lg border border-border bg-background px-2.5 py-1 text-xs text-foreground focus:border-primary focus:outline-none"
                      >
                        <option value="pending">نقل إلى: معلقة</option>
                        <option value="in_progress">نقل إلى: جارية</option>
                        <option value="done">نقل إلى: منجزة</option>
                        <option value="rejected">نقل إلى: مرفوضة</option>
                      </select>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* 3. تبويب التحديثات والتقارير (Updates & Reports) */}
        {tab === 'updates' && (
          <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-4 scrollbar-thin">
            {/* فلاتر النوع */}
            <div className="flex flex-wrap items-center gap-2 border-b border-border/60 pb-3">
              {(['all', 'complaint', 'suggestion', 'alert', 'report'] as const).map((kd) => {
                const labels = {
                  all: 'كافة التحديثات',
                  complaint: 'شكاوى',
                  suggestion: 'مقترحات',
                  alert: 'بلاغات وتنبيهات',
                  report: 'تقارير',
                }
                const count =
                  kd === 'all' ? updates.length : updates.filter((u) => u.kind === kd).length

                return (
                  <button
                    key={kd}
                    type="button"
                    onClick={() => setUpdateKindFilter(kd)}
                    className={cn(
                      'flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs font-medium transition-colors',
                      updateKindFilter === kd
                        ? 'bg-primary/20 text-primary border border-primary/30 font-semibold'
                        : 'bg-secondary/60 text-muted-foreground hover:text-foreground',
                    )}
                  >
                    <span>{labels[kd]}</span>
                    <span className="rounded-full bg-background/60 px-1.5 text-[10px] font-mono">
                      {count}
                    </span>
                  </button>
                )
              })}
            </div>

            {updatesLoading ? (
              <div className="flex items-center justify-center p-8 text-sm text-muted-foreground">
                <Loader2 className="size-4 animate-spin me-2" />
                <span>جاري تحميل التقارير والتحديثات…</span>
              </div>
            ) : filteredUpdates.length === 0 ? (
              <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border p-8 text-center text-muted-foreground">
                <FileText className="size-8 mb-2 opacity-50" />
                <p className="text-sm">لا توجد تحديثات أو تقارير مسجلة بهذا الفلتر</p>
              </div>
            ) : (
              <div className="space-y-3">
                {filteredUpdates.map((item) => {
                  const isDeciding = decidingId === item.id
                  const isPending = item.status === 'pending'

                  return (
                    <div
                      key={item.id}
                      className="rounded-xl border border-border bg-card p-4 space-y-2.5 transition-colors hover:border-border/80"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <span className="rounded bg-secondary px-2 py-0.5 text-xs font-semibold text-foreground">
                            {item.kind}
                          </span>
                          {item.severity && (
                            <span
                              className={cn(
                                'rounded px-2 py-0.5 text-xs font-semibold',
                                item.severity === 'عالي'
                                  ? 'bg-destructive/20 text-destructive border border-destructive/30'
                                  : 'bg-warning/20 text-warning',
                              )}
                            >
                              أهمية: {item.severity}
                            </span>
                          )}
                          <span
                            className={cn(
                              'rounded px-2 py-0.5 text-xs font-semibold',
                              item.status === 'approved' && 'bg-emerald-500/20 text-emerald-400',
                              item.status === 'rejected' && 'bg-destructive/20 text-destructive',
                              item.status === 'pending' && 'bg-warning/20 text-warning',
                            )}
                          >
                            الحالة: {item.status === 'approved' ? 'معتمد ✅' : item.status === 'rejected' ? 'مرفوض ❌' : 'بانتظار قرار المالك ⏳'}
                          </span>
                        </div>

                        <span className="text-xs text-muted-foreground font-mono flex items-center gap-1">
                          <Clock className="size-3" />
                          <span>{formatCairoDate(item.created_at)}</span>
                        </span>
                      </div>

                      <h4 className="text-sm md:text-base font-bold text-foreground">{item.title}</h4>
                      {item.body && (
                        <p className="text-xs md:text-sm text-muted-foreground leading-relaxed whitespace-pre-wrap">
                          {item.body}
                        </p>
                      )}

                      {/* أزرار القرار المباشر إذا كان معلقاً */}
                      {isPending && (
                        <div className="flex items-center gap-2 pt-2 border-t border-border/50">
                          <button
                            type="button"
                            disabled={isDeciding}
                            onClick={() => void handleUpdateDecision(item.id, 'approved')}
                            className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-500/15 px-3 py-1.5 text-xs font-semibold text-emerald-300 border border-emerald-500/30 hover:bg-emerald-500/25 disabled:opacity-50"
                          >
                            {isDeciding ? <Loader2 className="size-3.5 animate-spin" /> : <CheckCircle2 className="size-3.5" />}
                            <span>اعتماد التحديث</span>
                          </button>

                          <button
                            type="button"
                            disabled={isDeciding}
                            onClick={() => void handleUpdateDecision(item.id, 'rejected')}
                            className="inline-flex items-center gap-1.5 rounded-lg bg-destructive/15 px-3 py-1.5 text-xs font-semibold text-destructive border border-destructive/30 hover:bg-destructive/25 disabled:opacity-50"
                          >
                            <XCircle className="size-3.5" />
                            <span>رفض التحديث</span>
                          </button>
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
