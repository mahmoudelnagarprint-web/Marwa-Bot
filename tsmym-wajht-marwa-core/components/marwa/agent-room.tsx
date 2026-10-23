'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import {
  ArrowRight,
  Archive,
  Bot,
  Bell,
  CheckCircle2,
  Clock,
  Copy,
  FileText,
  Link2,
  ListTodo,
  Loader2,
  MessageSquare,
  Pencil,
  Plus,
  Send,
  Square,
  Trash2,
  User,
  XCircle,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { type Agent } from '@/lib/marwa-data'
import { supabase } from '@/lib/supabase'
import { ReportActions } from './report-actions'
import { ChatLiveBar, ModelPicker, useLiveChat } from './chat-live'
import {
  fetchAgentTasks,
  fetchAgentUpdates,
  formatCairoDate,
  archiveAgentTask,
  insertTaskCompletionReport,
  insertAgentTask,
  isTableMissingErr,
  makeRoomLog,
  subscribeAgentTasks,
  subscribeAgentUpdates,
  updateAgentTask,
  updateAgentTaskStatus,
  updateAgentUpdateStatus,
  type AgentTask,
  type AgentUpdate,
} from '@/lib/agent-tasks'

type TabId = 'chat' | 'tasks' | 'notifications' | 'updates'

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
  isScanning,
  lastScanAt,
}: {
  agent: Agent
  onBack: () => void
  isScanning: boolean
  lastScanAt: string | null
}) {
  const [tab, setTab] = useState<TabId>('chat')

  /** اختيار النموذج + التبديل الآلي/اليدوي + حالة Active/Standby لهذه الغرفة */
  const live = useLiveChat(agent.id)

  /** طابع كل خطوة في هذه الغرفة — يُظهر للمالك ماذا يحدث بالضبط */
  const log = useMemo(() => makeRoomLog(agent.id), [agent.id])

  // ──────────────────────── 1. تبويب الشات (Live Streaming Chat) ────────────────────────
  const storageKey = `marwa_chat_${agent.id}`
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [editTargetId, setEditTargetId] = useState<string | null>(null)
  const [isGenerating, setIsGenerating] = useState(false)
  const chatBottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

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

  // إرسال رسالة الشات مع دعم البث والإيقاف
  const handleSendChat = async () => {
    const text = input.trim()
    if (!text || isGenerating) return

    const editIndex = editTargetId ? messages.findIndex((message) => message.id === editTargetId) : -1
    const beforeEdit = editIndex >= 0 ? messages.slice(0, editIndex) : messages
    const userMsg: ChatMessage = {
      id: editIndex >= 0 ? messages[editIndex].id : crypto.randomUUID(),
      role: 'user',
      content: text,
      time: new Date().toLocaleTimeString('ar-EG', { hour: '2-digit', minute: '2-digit' }),
    }

    const nextHistory = [...beforeEdit, userMsg]
    setMessages(nextHistory)
    setInput('')
    setEditTargetId(null)
    setIsGenerating(true)

    const botMsgId = crypto.randomUUID()
    const tempBotMsg: ChatMessage = {
      id: botMsgId,
      role: 'assistant',
      content: '',
      time: new Date().toLocaleTimeString('ar-EG', { hour: '2-digit', minute: '2-digit' }),
    }

    setMessages((prev) => [...prev, tempBotMsg])

    try {
      let scheduleResponse: Response | null = null
      let scheduleData: {
        ok?: boolean
        scheduled?: boolean
        error?: string
        task?: { title?: string; agent_id?: string; scheduled_time?: string }
      } | null = null
      try {
        scheduleResponse = await fetch('/api/tasks/schedule', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text }),
        })
        scheduleData = await scheduleResponse.json()
      } catch {
        // مسار الجدولة اختياري؛ إذا تعذّر فحصه نكمل مسار الشات المعتاد.
      }
      if (scheduleData?.scheduled) {
        setMessages((prev) => prev.map((message) => message.id === botMsgId ? {
          ...message,
          content: `• تمام، اتسجلت مهمة «${scheduleData.task?.title || 'المهمة اليومية'}» لـ${scheduleData.task?.agent_id || 'الوكيل'} كل يوم الساعة ${scheduleData.task?.scheduled_time || 'المحددة'} بتوقيت القاهرة.\n• هتظهر في التقارير بعد تشغيل العامل الخلفي.`,
        } : message))
        return
      }
      if (scheduleResponse && !scheduleResponse.ok && scheduleData?.error) throw new Error(scheduleData.error)

      const res = await live.send(
        nextHistory.slice(-8).map((m) => ({
          role: m.role === 'user' ? ('user' as const) : ('assistant' as const),
          content: m.content,
        })),
      )

      if (res.ok && res.text) {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === botMsgId
              ? {
                  ...m,
                  content: res.text || '',
                  model: res.provider?.model,
                  latency_ms: res.latency_ms,
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
                  content: res.reason || 'تعذر الحصول على رد من الوكيل، يرجى المحاولة لاحقاً.',
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
              ? { ...m, content: err instanceof Error ? `تعذر تنفيذ الطلب: ${err.message}` : 'حدث خطأ في الاتصال بنظام الذكاء الاصطناعي.' }
              : m,
          ),
        )
      }
    } finally {
      setIsGenerating(false)
    }
  }

  const handleStopGeneration = () => {
    live.cancel()
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
  const [taskCandidates, setTaskCandidates] = useState<AgentTask[]>([])
  const [taskStatusFilter, setTaskStatusFilter] = useState<'all' | 'pending' | 'in_progress' | 'done' | 'rejected'>('all')
  const [newTaskTitle, setNewTaskTitle] = useState('')
  const [newTaskDesc, setNewTaskDesc] = useState('')
  const [newTaskPriority, setNewTaskPriority] = useState<'low' | 'normal' | 'high' | 'urgent'>('normal')
  const [newTaskDependencyId, setNewTaskDependencyId] = useState('')
  const [newTaskDaily, setNewTaskDaily] = useState(false)
  const [newTaskWeekly, setNewTaskWeekly] = useState(false)
  const [newTaskTime, setNewTaskTime] = useState('18:00')
  const [newTaskDay, setNewTaskDay] = useState(0)
  const [editingTaskId, setEditingTaskId] = useState<string | null>(null)
  const [editingDraft, setEditingDraft] = useState({ title: '', description: '', priority: 'normal' as 'low' | 'normal' | 'high' | 'urgent', dependency_id: '', daily: false, weekly: false, time: '18:00', day: 0 })
  const [isAddingTask, setIsAddingTask] = useState(false)
  const [tasksLoading, setTasksLoading] = useState(false)
  const [tasksError, setTasksError] = useState<string | null>(null)

  const loadTasks = async () => {
    if (!supabase) {
      log('المهام', 'تخطّي — Supabase غير مهيأ في .env.local')
      return
    }
    log('المهام', 'بدء القراءة من agent_tasks')
    setTasksLoading(true)
    const [{ tasks: items, error }, { tasks: candidates }] = await Promise.all([
      fetchAgentTasks(supabase, agent.id),
      fetchAgentTasks(supabase),
    ])
    setTaskCandidates(candidates)
    if (error) {
      log('المهام', 'فشل القراءة: ' + error.message)
      setTasksError(isTableMissingErr(error) ? 'جدول agent_tasks غير موجود في Supabase — طبّق الترحيل 006.' : error.message)
    } else {
      setTasksError(null)
      log('المهام', `تم تحميل ${items.length} مهمة`)
    }
    setTasks(items)
    setTasksLoading(false)
  }

  useEffect(() => {
    if (tab === 'tasks' || tab === 'notifications') {
      void loadTasks()
    }
  }, [tab, agent.id])

  // اشتراك حي على مهام هذا الوكيل — أي مهمة جديدة أو تغيير حالة يظهر فوراً
  useEffect(() => {
    if (!supabase) return
    log('Realtime/المهام', 'طلب اشتراك')
    const sub = subscribeAgentTasks(supabase, agent.id, {
      onStatus: (s) => log('Realtime/المهام', 'حالة القناة: ' + s),
      onInsert: (row) => {
        log('Realtime/المهام', 'مهمة جديدة: ' + row.title)
        setTasks((prev) => (prev.some((t) => t.id === row.id) ? prev : [row, ...prev]))
        setTaskCandidates((prev) => (prev.some((t) => t.id === row.id) ? prev : [row, ...prev]))
      },
      onUpdate: (row) => {
        log('Realtime/المهام', `تحديث حالة المهمة → ${row.status}`)
        setTasks((prev) => prev.map((t) => (t.id === row.id ? { ...t, ...row } : t)))
        setTaskCandidates((prev) => prev.map((t) => (t.id === row.id ? { ...t, ...row } : t)))
      },
    })
    return () => {
      log('Realtime/المهام', 'إلغاء الاشتراك')
      sub.unsubscribe()
    }
  }, [agent.id])

  const handleCreateTask = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newTaskTitle.trim() || !supabase) {
      log('إسناد مهمة', 'تخطّي — العنوان فارغ أو Supabase غير مهيأ')
      return
    }
    log('إسناد مهمة', 'إرسال: ' + newTaskTitle.trim())
    setIsAddingTask(true)
    const { ok, error, row } = await insertAgentTask(supabase, {
      agent_id: agent.id,
      title: newTaskTitle,
      description: newTaskDesc,
      priority: newTaskPriority,
      dependency_id: newTaskDependencyId || null,
      schedule_type: newTaskDaily ? 'daily' : newTaskWeekly ? 'weekly' : 'none',
      scheduled_time: newTaskDaily || newTaskWeekly ? newTaskTime : null,
      schedule_day_of_week: newTaskWeekly ? newTaskDay : null,
    })
    setIsAddingTask(false)
    if (ok && row) {
      log('إسناد مهمة', 'تم الحفظ في السحابة ✓ id=' + row.id)
      setTasks((prev) => (prev.some((t) => t.id === row.id) ? prev : [row, ...prev]))
      setNewTaskTitle('')
      setNewTaskDesc('')
      setNewTaskDependencyId('')
      setNewTaskDaily(false)
      setNewTaskWeekly(false)
      setTasksError(null)
    } else {
      log('إسناد مهمة', 'فشل: ' + (error?.message ?? 'سبب غير معروف'))
      setTasksError(error ? (isTableMissingErr(error) ? 'جدول agent_tasks غير موجود في Supabase.' : error.message) : 'تعذر الحفظ')
    }
  }

  const handleSaveTask = async (taskId: string) => {
    if (!supabase || !editingDraft.title.trim()) return
    let cursor = editingDraft.dependency_id
    const visited = new Set<string>()
    while (cursor) {
      if (cursor === taskId || visited.has(cursor)) {
        setTasksError('الاعتمادية هتعمل حلقة بين المهام؛ اختار مهمة سابقة مختلفة.')
        return
      }
      visited.add(cursor)
      cursor = taskCandidates.find((candidate) => candidate.id === cursor)?.dependency_id || ''
    }
    const { ok, error } = await updateAgentTask(supabase, taskId, {
      title: editingDraft.title,
      description: editingDraft.description,
      priority: editingDraft.priority,
      dependency_id: editingDraft.dependency_id || null,
      schedule_type: editingDraft.daily ? 'daily' : editingDraft.weekly ? 'weekly' : 'none',
      scheduled_time: editingDraft.daily || editingDraft.weekly ? editingDraft.time : null,
      schedule_day_of_week: editingDraft.weekly ? editingDraft.day : null,
    })
    if (!ok) {
      setTasksError(error?.message ?? 'تعذر حفظ تعديل المهمة')
      return
    }
    setEditingTaskId(null)
    setTasksError(null)
    void loadTasks()
  }

  const handleArchiveTask = async (taskId: string) => {
    if (!supabase || !window.confirm('أؤرشف المهمة؟ هتختفي من القائمة، لكن سجلها يفضل محفوظ.')) return
    const { ok, error } = await archiveAgentTask(supabase, taskId)
    if (!ok) {
      setTasksError(error?.message ?? 'تعذر أرشفة المهمة')
      return
    }
    setTasks((prev) => prev.filter((task) => task.id !== taskId))
    setTaskCandidates((prev) => prev.filter((task) => task.id !== taskId))
  }

  const handleUpdateTaskStatus = async (
    taskId: string,
    newStatus: 'pending' | 'in_progress' | 'done' | 'rejected',
  ) => {
    if (!supabase) return
    const task = tasks.find((item) => item.id === taskId)
    if (newStatus !== 'pending' && task?.dependency_id) {
      const prerequisite = taskCandidates.find((item) => item.id === task.dependency_id)
      if (!prerequisite || prerequisite.status !== 'done') {
        setTasksError('المهمة مقفولة مؤقتًا لحد ما المهمة المعتمدة عليها تكتمل.')
        return
      }
    }
    log('نقل حالة المهمة', `id=${taskId} → ${newStatus}`)
    setTasks((prev) =>
      prev.map((t) => (t.id === taskId ? { ...t, status: newStatus, updated_at: new Date().toISOString() } : t)),
    )
    const { ok, error } = await updateAgentTaskStatus(supabase, taskId, newStatus)
    log('نقل حالة المهمة', ok ? 'تم التثبيت في السحابة ✓' : 'فشل: ' + (error?.message ?? 'خطأ'))
    if (ok) setTaskCandidates((prev) => prev.map((item) => item.id === taskId ? { ...item, status: newStatus } : item))
    if (ok && newStatus === 'done') {
      if (task) {
        const report = await insertTaskCompletionReport(supabase, task)
        if (!report.ok) setTasksError(report.error?.message ?? 'اتقفلت المهمة لكن تعذر حفظ تقرير الإنجاز')
      }
    }
    if (!ok) void loadTasks()
  }

  const filteredTasks = tasks.filter((t) => {
    if (taskStatusFilter === 'all') return true
    return t.status === taskStatusFilter
  })

  // ──────────────────────── 3. تبويب التحديثات والتقارير (Updates & Reports) ────────────────────────
  const [updates, setUpdates] = useState<AgentUpdate[]>([])
  const [updateKindFilter, setUpdateKindFilter] = useState<'all' | 'complaint' | 'suggestion' | 'alert' | 'report'>('all')
  const [updatesLoading, setUpdatesLoading] = useState(false)
  const [updatesError, setUpdatesError] = useState<string | null>(null)
  const [decidingId, setDecidingId] = useState<string | null>(null)

  const loadUpdates = async () => {
    if (!supabase) {
      log('التحديثات', 'تخطّي — Supabase غير مهيأ في .env.local')
      return
    }
    log('التحديثات', 'بدء القراءة من agent_updates')
    setUpdatesLoading(true)
    const { items, error } = await fetchAgentUpdates(supabase, agent.id)
    if (error) {
      log('التحديثات', 'فشل القراءة: ' + error.message)
      setUpdatesError(isTableMissingErr(error) ? 'جدول agent_updates غير موجود في Supabase — طبّق الترحيل 006.' : error.message)
    } else {
      setUpdatesError(null)
      log('التحديثات', `تم تحميل ${items.length} تحديث`)
    }
    setUpdates(items)
    setUpdatesLoading(false)
  }

  useEffect(() => {
    if (tab === 'updates') {
      void loadUpdates()
    }
  }, [tab, agent.id])

  // اشتراك حي على تحديثات هذا الوكيل — أي اقتراح/شكوى/بلاغ يظهر فوراً
  useEffect(() => {
    if (!supabase) return
    log('Realtime/التحديثات', 'طلب اشتراك')
    const sub = subscribeAgentUpdates(supabase, agent.id, {
      onStatus: (s) => log('Realtime/التحديثات', 'حالة القناة: ' + s),
      onInsert: (row) => {
        log('Realtime/التحديثات', `وصل تحديث جديد (${row.kind}): ` + row.title)
        setUpdates((prev) => (prev.some((u) => u.id === row.id) ? prev : [row, ...prev]))
      },
      onUpdate: (row) => {
        log('Realtime/التحديثات', 'قرار على تحديث → ' + row.status)
        setUpdates((prev) => prev.map((u) => (u.id === row.id ? { ...u, ...row } : u)))
      },
    })
    return () => {
      log('Realtime/التحديثات', 'إلغاء الاشتراك')
      sub.unsubscribe()
    }
  }, [agent.id])

  const handleUpdateDecision = async (id: string, decision: 'approved' | 'rejected') => {
    if (!supabase) return
    log('قرار التحديث', `id=${id} → ${decision}`)
    setDecidingId(id)
    const { ok, error } = await updateAgentUpdateStatus(supabase, id, decision)
    setDecidingId(null)
    if (ok) {
      log('قرار التحديث', 'تم التثبيت في السحابة ✓')
      setUpdates((prev) =>
        prev.map((u) => (u.id === id ? { ...u, status: decision, decided_by: 'mahmoud' } : u)),
      )
    } else {
      log('قرار التحديث', 'فشل: ' + (error?.message ?? 'خطأ'))
      setUpdatesError(error?.message ?? 'تعذر تسجيل القرار')
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
              <span className={cn('rounded-full px-2 py-0.5 text-[10px] font-semibold border', isScanning && (agent.id === 'fares' || agent.id === 'salma') ? 'bg-sky-500/15 text-sky-300 border-sky-500/30' : 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30')}>
                {isScanning && (agent.id === 'fares' || agent.id === 'salma') ? 'Active / Scanning' : 'متصل — الفحص دوري'}
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
            onClick={() => setTab('notifications')}
            className={cn(
              'flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-semibold transition-all',
              tab === 'notifications' ? 'bg-primary text-primary-foreground shadow-sm' : 'text-muted-foreground hover:text-foreground',
            )}
          >
            <Bell className="size-3.5" />
            <span>الإشعارات</span>
            {tasks.filter((task) => task.status === 'pending' || task.status === 'in_progress').length > 0 && (
              <span className="rounded-full bg-background/40 px-1.5 text-[10px]">{tasks.filter((task) => task.status === 'pending' || task.status === 'in_progress').length}</span>
            )}
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
            {/* رأس الشات: اختيار النموذج (آلي/يدوي) + شريط Active/Standby + المؤقت */}
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border/60 bg-card/30 px-3 py-2">
              <span className="flex min-w-0 items-center gap-1.5 text-xs text-muted-foreground">
                <Bot className="size-3.5 shrink-0 text-primary" />
                <span className="truncate">محادثة مباشرة مع {agent.name} (محفوظة محلياً)</span>
              </span>
              <div className="flex min-w-0 flex-wrap items-center gap-2">
                <ModelPicker live={live} />
                <ChatLiveBar live={live} />
                <button
                  type="button"
                  onClick={handleClearChat}
                  className="flex shrink-0 items-center gap-1 rounded-lg px-1.5 py-1 text-xs text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
                  title="مسح محادثة الوكيل"
                >
                  <Trash2 className="size-3.5" />
                  <span>مسح</span>
                </button>
              </div>
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
                      {isUser && (
                        <div className="mt-2 flex items-center justify-end gap-1 border-t border-primary-foreground/15 pt-1.5">
                          <button type="button" onClick={() => void navigator.clipboard.writeText(msg.content).catch(() => undefined)} className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-[10px] text-primary-foreground/75 hover:bg-primary-foreground/10 hover:text-primary-foreground" title="نسخ الرسالة">
                            <Copy className="size-3" /> نسخ
                          </button>
                          <button type="button" onClick={() => { setInput(msg.content); setEditTargetId(msg.id); inputRef.current?.focus() }} className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-[10px] text-primary-foreground/75 hover:bg-primary-foreground/10 hover:text-primary-foreground" title="تعديل وإعادة إرسال">
                            <Pencil className="size-3" /> تعديل
                          </button>
                        </div>
                      )}
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

            {/* شريط كتابة الرسالة مع Enter للإرسال وزر إيقاف التوليد */}
            <div className="border-t border-border bg-card/60 p-3 md:p-4">
              {editTargetId && <div className="mb-2 flex items-center justify-between text-[11px] text-primary"><span>بتعدّل رسالة قديمة؛ الردود اللي بعدها هتتولد من جديد.</span><button type="button" onClick={() => { setEditTargetId(null); setInput('') }} className="rounded p-1 hover:bg-secondary">إلغاء التعديل</button></div>}
              <div className="relative flex items-center gap-2">
                <textarea
                  ref={inputRef}
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault()
                      void handleSendChat()
                    }
                  }}
                  placeholder={`اكتب رسالتك لـ ${agent.name} (اضغط Enter للإرسال)…`}
                  rows={1}
                  className="w-full resize-none rounded-xl border border-border bg-background px-4 py-3 pe-24 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary scrollbar-thin"
                />

                <div className="absolute end-2 flex items-center gap-1.5">
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
                      disabled={!input.trim()}
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

        {tab === 'notifications' && (
          <div className="flex-1 overflow-y-auto p-4 md:p-6 space-y-4 scrollbar-thin">
            <div className="rounded-xl border border-border bg-card p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 className="flex items-center gap-2 text-sm font-bold text-foreground"><Bell className="size-4 text-primary" /> إشعارات {agent.name} المباشرة</h3>
                <span className="text-[11px] text-muted-foreground">Realtime من سجل المهام — {lastScanAt ? `آخر فحص ${formatCairoDate(lastScanAt)}` : 'الفحص الاستباقي ينتظر'}</span>
              </div>
              <p className="mt-1 text-xs text-muted-foreground">تظهر هنا المهام الواردة من المالك أو مروة أو وكيل آخر، ثم تتحدث حالتها فور وصول تغيير من قاعدة المهام.</p>
            </div>
            {tasksLoading ? (
              <div className="flex items-center justify-center p-8 text-sm text-muted-foreground"><Loader2 className="me-2 size-4 animate-spin" />جاري تحميل الإشعارات…</div>
            ) : tasks.length === 0 ? (
              <div className="rounded-xl border border-dashed border-border p-8 text-center text-sm text-muted-foreground">لا توجد مهام واردة لهذا الوكيل حتى الآن.</div>
            ) : (
              <div className="space-y-2">
                {tasks.slice().sort((a, b) => (b.updated_at || b.created_at).localeCompare(a.updated_at || a.created_at)).map((task) => {
                  const sender = task.source === 'marwa' ? 'مروة' : task.source === 'agent' ? `وكيل — ${task.created_by}` : task.created_by === 'mahmoud' ? 'المالك' : task.source === 'ui' ? 'إسناد يدوي' : task.source
                  const state = task.status === 'done' ? 'مكتملة' : task.status === 'in_progress' ? 'جاري العمل' : task.status === 'rejected' ? 'مرفوضة' : 'تم الاستلام'
                  return (
                    <article key={task.id} className="rounded-xl border border-border bg-card p-3.5">
                      <div className="flex flex-wrap items-start justify-between gap-2">
                        <div className="min-w-0">
                          <h4 className="text-sm font-semibold text-foreground">{task.title}</h4>
                          <p className="mt-1 text-[11px] text-muted-foreground">المرسل: {sender} · أُرسلت {formatCairoDate(task.created_at)}</p>
                        </div>
                        <span className={cn('rounded-full px-2 py-1 text-[10px] font-semibold', task.status === 'done' ? 'bg-emerald-500/15 text-emerald-400' : task.status === 'in_progress' ? 'bg-sky-500/15 text-sky-300' : task.status === 'rejected' ? 'bg-destructive/15 text-destructive' : 'bg-amber-500/15 text-amber-300')}>{state}</span>
                      </div>
                      {task.description && <p className="mt-2 whitespace-pre-wrap text-xs leading-relaxed text-muted-foreground">{task.description}</p>}
                      <div className="mt-2 flex items-center gap-1 text-[10px] text-muted-foreground"><Clock className="size-3" />آخر تحديث: {formatCairoDate(task.updated_at || task.created_at)}</div>
                    </article>
                  )
                })}
              </div>
            )}
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

              <div className="grid grid-cols-1 gap-3 border-t border-border/60 pt-3 md:grid-cols-3">
                <label className="flex flex-col gap-1 text-[11px] text-muted-foreground">
                  تعتمد على مهمة
                  <select value={newTaskDependencyId} onChange={(e) => setNewTaskDependencyId(e.target.value)} className="rounded-lg border border-border bg-background px-3 py-2 text-xs text-foreground">
                    <option value="">بدون اعتماد</option>
                    {taskCandidates.filter((candidate) => candidate.status !== 'done' && candidate.status !== 'rejected').map((candidate) => (
                      <option key={candidate.id} value={candidate.id}>{candidate.agent_id} — {candidate.title}</option>
                    ))}
                  </select>
                </label>
                <label className="flex items-center gap-2 rounded-lg border border-border bg-background px-3 py-2 text-xs text-foreground">
                  <input type="checkbox" checked={newTaskDaily} onChange={(e) => { setNewTaskDaily(e.target.checked); if (e.target.checked) setNewTaskWeekly(false) }} />
                  تكرار يومي بتوقيت القاهرة
                </label>
                <label className="flex items-center gap-2 rounded-lg border border-border bg-background px-3 py-2 text-xs text-foreground">
                  <input type="checkbox" checked={newTaskWeekly} onChange={(e) => { setNewTaskWeekly(e.target.checked); if (e.target.checked) setNewTaskDaily(false) }} />
                  تكرار أسبوعي بتوقيت القاهرة
                </label>
                {(newTaskDaily || newTaskWeekly) && <input aria-label="وقت التكرار" type="time" value={newTaskTime} onChange={(e) => setNewTaskTime(e.target.value)} className="rounded-lg border border-border bg-background px-3 py-2 text-xs text-foreground" />}
                {newTaskWeekly && <select aria-label="يوم التكرار الأسبوعي" value={newTaskDay} onChange={(e) => setNewTaskDay(Number(e.target.value))} className="rounded-lg border border-border bg-background px-3 py-2 text-xs text-foreground"><option value={0}>الأحد</option><option value={1}>الاثنين</option><option value={2}>الثلاثاء</option><option value={3}>الأربعاء</option><option value={4}>الخميس</option><option value={5}>الجمعة</option><option value={6}>السبت</option></select>}
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
            {tasksError && (
              <div className="rounded-xl border border-destructive/40 bg-destructive/10 px-3.5 py-2.5 text-xs text-destructive">
                {tasksError}
              </div>
            )}
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
                    className={cn('flex flex-col sm:flex-row sm:items-center justify-between gap-3 rounded-xl border border-border bg-card p-3.5 transition-colors hover:border-border/80', (t.priority === 'high' || t.priority === 'urgent') && t.status !== 'done' && 'border-rose-400/50 bg-rose-400/[0.04] motion-safe:animate-pulse')}
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
                          أولوية: {t.priority === 'urgent' ? 'عاجلة' : t.priority === 'high' ? 'عالية' : t.priority === 'low' ? 'منخفضة' : 'عادية'}
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
                      {t.schedule_type === 'daily' && t.scheduled_time && (
                        <p className="flex items-center gap-1 text-[11px] text-sky-300"><Clock className="size-3" /> يوميًا {t.scheduled_time.slice(0, 5)} بتوقيت القاهرة</p>
                      )}
                      {t.schedule_type === 'weekly' && t.scheduled_time && (
                        <p className="flex items-center gap-1 text-[11px] text-sky-300"><Clock className="size-3" /> أسبوعيًا — {['الأحد','الاثنين','الثلاثاء','الأربعاء','الخميس','الجمعة','السبت'][t.schedule_day_of_week ?? 0]} الساعة {t.scheduled_time.slice(0, 5)} بتوقيت القاهرة</p>
                      )}
                      {t.dependency_id && (() => {
                        const prerequisite = taskCandidates.find((candidate) => candidate.id === t.dependency_id)
                        return <p className={cn('flex items-center gap-1 text-[11px]', prerequisite?.status === 'done' ? 'text-emerald-300' : 'text-amber-300')}><Link2 className="size-3" /> {prerequisite?.status === 'done' ? 'الاعتمادية اكتملت' : `مقفولة حتى اكتمال: ${prerequisite?.title ?? 'المهمة السابقة'}`}</p>
                      })()}
                      {editingTaskId === t.id && (
                        <div className="mt-2 grid gap-2 rounded-lg border border-primary/20 bg-background/70 p-3 md:grid-cols-2">
                          <input value={editingDraft.title} onChange={(e) => setEditingDraft((draft) => ({ ...draft, title: e.target.value }))} className="rounded-md border border-border bg-background px-2.5 py-2 text-xs" aria-label="عنوان المهمة" />
                          <input value={editingDraft.description} onChange={(e) => setEditingDraft((draft) => ({ ...draft, description: e.target.value }))} className="rounded-md border border-border bg-background px-2.5 py-2 text-xs" aria-label="تفاصيل المهمة" placeholder="تفاصيل المهمة" />
                          <select value={editingDraft.priority} onChange={(e) => setEditingDraft((draft) => ({ ...draft, priority: e.target.value as typeof draft.priority }))} className="rounded-md border border-border bg-background px-2.5 py-2 text-xs">
                            <option value="low">منخفضة</option><option value="normal">عادية</option><option value="high">عالية</option><option value="urgent">عاجلة</option>
                          </select>
                          <select value={editingDraft.dependency_id} onChange={(e) => setEditingDraft((draft) => ({ ...draft, dependency_id: e.target.value }))} className="rounded-md border border-border bg-background px-2.5 py-2 text-xs">
                            <option value="">بدون اعتماد</option>
                            {taskCandidates.filter((candidate) => candidate.id !== t.id && candidate.status !== 'done' && candidate.status !== 'rejected').map((candidate) => <option key={candidate.id} value={candidate.id}>{candidate.agent_id} — {candidate.title}</option>)}
                          </select>
                          <label className="flex items-center gap-2 text-xs"><input type="checkbox" checked={editingDraft.daily} onChange={(e) => setEditingDraft((draft) => ({ ...draft, daily: e.target.checked, weekly: e.target.checked ? false : draft.weekly }))} /> تكرار يومي</label>
                          <label className="flex items-center gap-2 text-xs"><input type="checkbox" checked={editingDraft.weekly} onChange={(e) => setEditingDraft((draft) => ({ ...draft, weekly: e.target.checked, daily: e.target.checked ? false : draft.daily }))} /> تكرار أسبوعي</label>
                          {(editingDraft.daily || editingDraft.weekly) && <input type="time" value={editingDraft.time} onChange={(e) => setEditingDraft((draft) => ({ ...draft, time: e.target.value }))} className="rounded-md border border-border bg-background px-2.5 py-2 text-xs" />}
                          {editingDraft.weekly && <select value={editingDraft.day} onChange={(e) => setEditingDraft((draft) => ({ ...draft, day: Number(e.target.value) }))} className="rounded-md border border-border bg-background px-2.5 py-2 text-xs"><option value={0}>الأحد</option><option value={1}>الاثنين</option><option value={2}>الثلاثاء</option><option value={3}>الأربعاء</option><option value={4}>الخميس</option><option value={5}>الجمعة</option><option value={6}>السبت</option></select>}
                          <div className="flex gap-2 md:col-span-2">
                            <button type="button" onClick={() => void handleSaveTask(t.id)} className="rounded-md bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground">حفظ</button>
                            <button type="button" onClick={() => setEditingTaskId(null)} className="rounded-md border border-border px-3 py-1.5 text-xs">إلغاء</button>
                          </div>
                        </div>
                      )}
                    </div>

                    {/* تغيير حالة المهمة بسلاسة (لا حذف نهائياً) */}
                    <div className="flex items-center gap-1.5 shrink-0 self-end sm:self-center">
                      <button
                        type="button"
                        title="تعديل المهمة"
                        onClick={() => {
                          setEditingTaskId(t.id)
                          setEditingDraft({ title: t.title, description: t.description || '', priority: t.priority, dependency_id: t.dependency_id || '', daily: t.schedule_type === 'daily', weekly: t.schedule_type === 'weekly', time: t.scheduled_time?.slice(0, 5) || '18:00', day: t.schedule_day_of_week ?? 0 })
                        }}
                        className="rounded-md border border-border p-1.5 text-muted-foreground hover:text-primary"
                      ><Pencil className="size-3.5" /></button>
                      <button type="button" title="أرشفة المهمة" onClick={() => void handleArchiveTask(t.id)} className="rounded-md border border-border p-1.5 text-muted-foreground hover:text-destructive"><Archive className="size-3.5" /></button>
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

            {updatesError && (
              <div className="rounded-xl border border-destructive/40 bg-destructive/10 px-3.5 py-2.5 text-xs text-destructive">
                {updatesError}
              </div>
            )}
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
                      {item.kind === 'report' && <ReportActions actions={item.payload?.actions} body={item.body || item.title} />}

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
