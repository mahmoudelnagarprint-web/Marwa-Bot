'use client'

// components/marwa/workspace-files.tsx — تبويب «ملفات الوكيل» (Read-Only)
// MARWA CORE task-4 (أمر المالك 2026-10-20 — تكليف فيجن).
// يعرض شجرة ملفات مساحة العمل (G:\Marwa-Bot) من /api/workspace — قراءة فقط:
// لا فتح ولا تعديل ولا رفع — مجرد عرض + توسيع/طي محلي.
// لكل وكيل «مكتبه»: ملف حالته الرسمي + مجلد مكتبه (إن وُجد) يُبرز فوق الشجرة.

import { useCallback, useEffect, useMemo, useState } from 'react'
import { ChevronDown, ChevronLeft, FileText, Folder, FolderOpen, HardDrive, Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'

type Entry = {
  name: string
  path: string
  type: 'file' | 'dir'
  size?: number
  mtime?: string
  children?: Entry[]
}

/** مكتب كل وكيل: ملف حالته الرسمي + مجلد مكتبه (مطابق لدفاتر الجذر المعتمد) */
const OFFICES: Record<string, { book: string; folder?: string }> = {
  fares: { book: 'FARES_CFO_STATE.md' },
  salma: { book: 'SALMA_CRM_STATE.md', folder: 'agents/salma' },
  bebo: { book: 'BIBO_MANUFACTURING_STATE.md' },
  koko: { book: 'KOKO_MARKETING_STATE.md' },
  rased: { book: 'RASED_SENTINEL_STATE.md' },
  vision: { book: 'AGENT.md', folder: 'Vision-Lab' },
}

type State =
  | { phase: 'loading' }
  | { phase: 'error'; error: string }
  | { phase: 'ready'; entries: Entry[]; counts: { dirs: number; files: number }; skipped: string[] }

function fmtSize(bytes?: number): string {
  if (bytes === undefined) return ''
  if (bytes < 1024) return `${bytes} بايت`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} ك.ب`
  return `${(bytes / (1024 * 1024)).toFixed(1)} م.ب`
}

function fmtTime(iso?: string): string {
  if (!iso) return ''
  try {
    return new Date(iso).toLocaleString('ar-EG', {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return ''
  }
}

export function WorkspaceFiles({ agentId }: { agentId?: string }) {
  const [state, setState] = useState<State>({ phase: 'loading' })
  const [open, setOpen] = useState<Set<string>>(new Set())

  const load = useCallback(async () => {
    try {
      const res = await fetch('/api/workspace', { cache: 'no-store' })
      const data = await res.json()
      if (!data?.success) {
        setState({ phase: 'error', error: data?.error ?? 'خطأ غير معروف' })
        return
      }
      setState({
        phase: 'ready',
        entries: data.entries ?? [],
        counts: data.counts ?? { dirs: 0, files: 0 },
        skipped: data.skipped ?? [],
      })
      // افتح المستوى الأول افتراضياً
      setOpen(new Set((data.entries ?? []).filter((e: Entry) => e.type === 'dir').map((e: Entry) => e.path)))
    } catch (e) {
      setState({ phase: 'error', error: e instanceof Error ? e.message : String(e) })
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const office = useMemo(() => (agentId ? OFFICES[agentId] : undefined), [agentId])

  const allPaths = useMemo(() => {
    const set = new Set<string>()
    const walk = (list: Entry[]) => {
      for (const e of list) {
        set.add(e.path)
        if (e.children) walk(e.children)
      }
    }
    if (state.phase === 'ready') walk(state.entries)
    return set
  }, [state])

  const toggle = (p: string) => {
    setOpen((prev) => {
      const next = new Set(prev)
      if (next.has(p)) next.delete(p)
      else next.add(p)
      return next
    })
  }

  const renderEntry = (e: Entry, depth: number): React.ReactNode => {
    const isOpen = open.has(e.path)
    const isOfficeBook = office?.book === e.name && depth === 0
    const isOfficeFolder = office?.folder === e.path
    return (
      <div key={e.path}>
        <button
          type="button"
          onClick={() => e.type === 'dir' && toggle(e.path)}
          className={cn(
            'flex w-full items-center gap-1.5 rounded px-1.5 py-1 text-start text-xs transition-colors hover:bg-sidebar-accent/60',
            (isOfficeBook || isOfficeFolder) && 'bg-violet-400/10 text-violet-200',
          )}
          style={{ paddingInlineStart: `${depth * 12 + 6}px` }}
          aria-expanded={e.type === 'dir' ? isOpen : undefined}
        >
          {e.type === 'dir' ? (
            isOpen ? (
              <FolderOpen className="size-3.5 shrink-0 text-amber-300/80" aria-hidden="true" />
            ) : (
              <Folder className="size-3.5 shrink-0 text-amber-300/60" aria-hidden="true" />
            )
          ) : (
            <FileText className="size-3.5 shrink-0 text-sky-300/70" aria-hidden="true" />
          )}
          <span className="min-w-0 flex-1 truncate" title={e.path}>
            {e.name}
          </span>
          {e.type === 'file' && e.size !== undefined && (
            <span className="shrink-0 text-[10px] tabular-nums text-muted-foreground">{fmtSize(e.size)}</span>
          )}
          {e.type === 'dir' && (
            <ChevronDown
              className={cn('size-3 shrink-0 text-muted-foreground transition-transform', !isOpen && '-rotate-90')}
              aria-hidden="true"
            />
          )}
        </button>
        {e.type === 'dir' && isOpen && e.children && e.children.length > 0 && (
          <div>{e.children.map((c) => renderEntry(c, depth + 1))}</div>
        )}
      </div>
    )
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col" aria-label="ملفات الوكيل">
      <div className="flex items-center justify-between gap-2 border-b border-border px-3 py-2">
        <p className="flex items-center gap-1.5 text-xs font-medium">
          <HardDrive className="size-3.5 text-muted-foreground" aria-hidden="true" />
          ملفات مساحة العمل
        </p>
        <button
          type="button"
          onClick={() => void load()}
          className="rounded border border-border px-2 py-0.5 text-[10px] text-muted-foreground transition-colors hover:bg-sidebar-accent/60"
        >
          تحديث
        </button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-1.5 scrollbar-thin">
        {state.phase === 'loading' && (
          <p className="flex items-center gap-2 px-2 py-3 text-xs text-muted-foreground" aria-busy="true">
            <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
            جارٍ قراءة شجرة الملفات (قراءة فقط)...
          </p>
        )}

        {state.phase === 'error' && (
          <p className="px-2 py-3 text-xs text-rose-200">تعذر قراءة الملفات: {state.error}</p>
        )}

        {state.phase === 'ready' && (
          <>
            <p className="px-2 py-1.5 text-[10px] text-muted-foreground">
              {state.counts.dirs} مجلد • {state.counts.files} ملف — قراءة فقط، بلا تعديل
            </p>

            {office && (
              <div className="mb-1.5 rounded-lg border border-violet-400/20 bg-violet-400/[0.06] p-2">
                <p className="mb-1 flex items-center gap-1 text-[10px] font-medium text-violet-200">
                  <FolderOpen className="size-3" aria-hidden="true" />
                  مكتب الوكيل المختار
                </p>
                <div className="flex flex-col gap-0.5 text-[11px]">
                  <span className="flex items-center gap-1.5 px-1 py-0.5">
                    <FileText className="size-3 shrink-0 text-violet-300/80" aria-hidden="true" />
                    <span className="truncate">{office.book}</span>
                    <span className={cn('ml-auto shrink-0 text-[9px]', allPaths.has(office.book) ? 'text-emerald-300' : 'text-rose-300')}>
                      {allPaths.has(office.book) ? 'موجود ✓' : 'غير موجود ✗'}
                    </span>
                  </span>
                  {office.folder && (
                    <span className="flex items-center gap-1.5 px-1 py-0.5">
                      <Folder className="size-3 shrink-0 text-violet-300/60" aria-hidden="true" />
                      <span className="truncate" dir="ltr">{office.folder}</span>
                      <span className={cn('ml-auto shrink-0 text-[9px]', allPaths.has(office.folder) ? 'text-emerald-300' : 'text-zinc-400')}>
                        {allPaths.has(office.folder) ? 'موجود ✓' : 'مستقبلي'}
                      </span>
                    </span>
                  )}
                </div>
              </div>
            )}

            {state.entries.length === 0 && (
              <p className="px-2 py-4 text-center text-xs text-muted-foreground">المجلد فارغ أو كل ما فيه مستثنى</p>
            )}
            {state.entries.map((e) => renderEntry(e, 0))}
          </>
        )}
      </div>

      {state.phase === 'ready' && state.skipped.length > 0 && (
        <p className="border-t border-border px-3 py-1.5 text-[9px] leading-relaxed text-muted-foreground">
          مستثنى من العرض (قراءة فقط — لم يُمس شيء): {state.skipped.join('، ')}
        </p>
      )}
    </div>
  )
}
