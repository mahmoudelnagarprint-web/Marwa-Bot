'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import dynamic from 'next/dynamic'
import { CircleStop, FileCode2, Play, Plus, RefreshCw, RotateCw, Square, Terminal, Trash2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

const MonacoEditor = dynamic(() => import('@monaco-editor/react').then((m) => m.default), {
  ssr: false,
  loading: () => <p className="p-2 text-[10px] text-muted-foreground">⏳ Monaco المحرر بيتحمل…</p>,
})

type AppEntry = { id: string; name: string; exe: string; desc: string; match?: string; added_at?: string }
type ProcRow = { key: string; name: string; pid: number | null; running: boolean; kind: 'daemon' | 'app' }
type FileEntry = { path: string; name: string }

export function VisionDashboard() {
  const [apps, setApps] = useState<AppEntry[]>([])
  const [procs, setProcs] = useState<ProcRow[]>([])
  const [files, setFiles] = useState<FileEntry[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [flash, setFlash] = useState<string | null>(null)
  const [termLines, setTermLines] = useState<string[]>(['⏳ التيرمينال الحي — جاهز…'])
  const termRef = useRef<HTMLDivElement>(null)

  // 1️⃣ نموذج إضافة برنامج — المنصة Template فاضي: البرامج من الفورم فقط
  const [appName, setAppName] = useState('')
  const [appExe, setAppExe] = useState('')
  const [appDesc, setAppDesc] = useState('')
  const [appMatch, setAppMatch] = useState('')
  const [showAdd, setShowAdd] = useState(false)

  // 3️⃣ المحرر
  const [editPath, setEditPath] = useState('')
  const [editContent, setEditContent] = useState('')
  const [editDirty, setEditDirty] = useState(false)

  const term = useCallback((line: string) => {
    setTermLines((prev) => [...prev.slice(-200), `${new Date().toLocaleTimeString('ar-EG')} — ${line}`])
  }, [])

  useEffect(() => { termRef.current?.scrollTo({ top: 999999 }) }, [termLines])

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true)
    setError(null)
    try {
      const [r1, r2, r3] = await Promise.all([
        fetch('/api/vision?what=apps', { cache: 'no-store' }),
        fetch('/api/vision?what=procs', { cache: 'no-store' }),
        fetch('/api/vision?what=files', { cache: 'no-store' }),
      ])
      const j1 = await r1.json(), j2 = await r2.json(), j3 = await r3.json()
      if (j1.error) throw new Error(j1.error)
      setApps((prev) => {
        // نبض التيرمينال: أي تغيّر في الصفوف يُطبع بسطر جاري
        if (j1.apps?.length !== prev.length) term(`📋 المنصة: ${j1.apps.length} برنامج${j1.apps.length === 1 ? '' : 'ات'} مسجلة`)
        return j1.apps ?? []
      })
      setProcs((prev) => {
        for (const p of (j2.processes ?? []) as ProcRow[]) {
          const before = prev.find((x) => x.key === p.key)
          if (before && before.running !== p.running) {
            term(p.running ? `🟢 ${p.name} اشتغل (PID ${p.pid})` : `🔴 ${p.name} وقف`)
          }
        }
        return j2.processes ?? []
      })
      setFiles(j3.files ?? [])
    } catch (e) {
      setError(e instanceof Error ? e.message : 'فشل التحميل')
    } finally {
      setLoading(false)
    }
  }, [term])

  useEffect(() => { void load() }, [load])
  // نبض مدير العمليات كل 15 ثانية (المصنع حي لا Dead)
  useEffect(() => {
    const t = setInterval(() => { void load(true) }, 15_000)
    return () => clearInterval(t)
  }, [load])

  async function post(payload: Record<string, unknown>, label: string) {
    setBusy(true)
    try {
      term(`▶ ${label}…`)
      const r = await fetch('/api/vision', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
      const j = (await r.json()) as { ok?: boolean; message?: string; app?: AppEntry }
      term(j.ok ? `✔ ${j.message ?? 'تم'}` : `✘ ${j.message ?? 'فشل'}`)
      setFlash(j.message ?? null)
      await load(true)
    } catch (e) {
      term(`✘ خطأ: ${e instanceof Error ? e.message : String(e)}`)
    } finally {
      setBusy(false)
    }
  }

  async function openFile(p: string) {
    term(`📂 فتح ${p.split('\\').pop()}…`)
    try {
      const r = await fetch(`/api/vision?what=read_file&path=${encodeURIComponent(p)}`, { cache: 'no-store' })
      const j = (await r.json()) as { content?: string; error?: string }
      if (j.error) { term(`✘ ${j.error}`); return }
      setEditPath(p)
      setEditContent(j.content ?? '')
      setEditDirty(false)
      term(`✔ ${p.split('\\').pop()} مفتوح (${(j.content ?? '').length.toLocaleString('ar-EG')} حرف)`)
    } catch { term('✘ فشل قراءة الملف') }
  }

  async function saveFile() {
    if (!editPath) return
    await post({ action: 'save_file', path: editPath, content: editContent }, `💾 حفظ ${editPath.split('\\').pop()}`)
    setEditDirty(false)
  }

  if (loading) return <div className="flex items-center gap-2 p-4 text-sm text-muted-foreground"><RefreshCw className="size-4 animate-spin" /> فيجن يجهز Mini-OS…</div>
  if (error) return <div className="p-4 text-sm text-rose-300">⚠️ {error}</div>

  return (
    <div className="flex h-full flex-col gap-3 p-3">

      {flash && <p className="rounded-lg bg-emerald-400/10 px-3 py-2 text-xs text-emerald-300" role="status">{flash}</p>}

      {/* 1️⃣ منصة إطلاق البرامج */}
      <div className="rounded-xl border border-border p-3">
        <div className="mb-2 flex items-center justify-between">
          <p className="text-sm font-medium">🚀 منصة إطلاق البرامج</p>
          <Button variant="outline" size="sm" className="h-7 px-2 text-[11px] text-emerald-200" onClick={() => setShowAdd((v) => !v)}>
            <Plus className="size-3" /> إضافة برنامج
          </Button>
        </div>
        {showAdd && (
          <div className="mb-3 grid grid-cols-1 gap-1.5 rounded-lg border border-border bg-card p-2 md:grid-cols-3">
            <input value={appName} onChange={(e) => setAppName(e.target.value)} placeholder="اسم البرنامج" className="h-7 rounded border border-border bg-background px-2 text-xs" />
            <input value={appExe} onChange={(e) => setAppExe(e.target.value)} placeholder="مسار البرنامج (.exe / .py / .js / .bat)" dir="ltr" className="h-7 rounded border border-border bg-background px-2 text-xs md:col-span-2" />
            <input value={appDesc} onChange={(e) => setAppDesc(e.target.value)} placeholder="وصف البرنامج" className="h-7 rounded border border-border bg-background px-2 text-xs md:col-span-2" />
            <input value={appMatch} onChange={(e) => setAppMatch(e.target.value)} placeholder="مفتاح تتبع العملية (اختياري — جزء من سطر التشغيل)" dir="ltr" className="h-7 rounded border border-border bg-background px-2 text-xs" />
            <Button variant="outline" size="sm" disabled={busy || !appName.trim() || !appExe.trim()} className="h-7 text-[11px] text-emerald-200"
              onClick={() => { void post({ action: 'add_app', name: appName, exe: appExe, desc: appDesc, match: appMatch }, 'إضافة برنامج'); setShowAdd(false); setAppName(''); setAppExe(''); setAppDesc(''); setAppMatch('') }}>
              تسجيل في المنصة
            </Button>
          </div>
        )}
        <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
          {apps.map((a) => (
            <div key={a.id} className="group rounded-lg border border-border bg-card p-2">
              <p className="truncate text-xs font-medium">{a.name}</p>
              <p className="truncate text-[10px] text-muted-foreground" title={a.exe} dir="ltr">{a.exe}</p>
              <p className="mt-1 line-clamp-2 h-6 text-[10px] text-muted-foreground">{a.desc}</p>
              <div className="mt-1.5 flex gap-1">
                <Button variant="outline" size="sm" disabled={busy} className="h-6 flex-1 px-1 text-[10px] text-emerald-300" onClick={() => void post({ action: 'start', key: `app:${a.id}` }, `تشغيل ${a.name}`)}>
                  <Play className="size-2.5" /> تشغيل
                </Button>
                <Button variant="ghost" size="sm" disabled={busy} className="h-6 px-1 text-[10px] text-rose-200" onClick={() => void post({ action: 'remove_app', id: a.id }, `حذف ${a.name}`)}>
                  <Trash2 className="size-3" />
                </Button>
              </div>
            </div>
          ))}
          {apps.length === 0 && <p className="col-span-full py-2 text-center text-[11px] text-muted-foreground">لا برامج بعد — أضف أول برنامج External بالزر ☝️</p>}
        </div>
      </div>

      {/* 2️⃣ مدير العمليات */}
      <div className="rounded-xl border border-border p-3">
        <p className="mb-2 text-sm font-medium">⚙️ مدير العمليات (الدايمونز + برامجك)</p>
        <div className="flex flex-col gap-1">
          {procs.map((p) => (
            <div key={p.key} className="flex items-center justify-between rounded-lg border border-border bg-card px-2 py-1.5">
              <div className="flex items-center gap-2">
                <span className={cn('size-2 rounded-full', p.running ? 'bg-emerald-400' : 'bg-rose-400')} />
                <span className="text-xs">{p.name}</span>
                <span className={cn('rounded px-1.5 text-[10px]', p.running ? 'bg-emerald-400/10 text-emerald-300' : 'bg-rose-400/10 text-rose-300')}>
                  {p.running ? `Running • PID ${p.pid}` : 'Stopped'}
                </span>
              </div>
              <div className="flex gap-1">
                <Button variant="outline" size="sm" disabled={busy || p.running} className="h-6 px-1.5 text-[10px] text-emerald-300" onClick={() => void post({ action: 'start', key: p.key }, `Start ${p.name}`)}><Play className="size-3" /></Button>
                <Button variant="outline" size="sm" disabled={busy || !p.running} className="h-6 px-1.5 text-[10px] text-rose-300" onClick={() => void post({ action: 'stop', key: p.key }, `Stop ${p.name}`)}><CircleStop className="size-3" /></Button>
                <Button variant="outline" size="sm" disabled={busy} className="h-6 px-1.5 text-[10px] text-amber-300" onClick={() => void post({ action: 'restart', key: p.key }, `Restart ${p.name}`)}><RotateCw className="size-3" /></Button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 3️⃣ محرر الأكواد — Monaco */}
      <div className="rounded-xl border border-border p-3">
        <div className="mb-2 flex items-center justify-between">
          <p className="flex items-center gap-2 text-sm font-medium"><FileCode2 className="size-4 text-sky-300" /> محرر أكواد المنظومة (Monaco)</p>
          {editPath && (
            <Button variant="outline" size="sm" disabled={busy || !editDirty} className="h-7 px-2 text-[11px] text-sky-200" onClick={() => void saveFile()}>
              💾 حفظ{editDirty ? ' •' : ''}
            </Button>
          )}
        </div>
        <div className="flex flex-wrap gap-1">
          {files.map((f) => (
            <button key={f.path} onClick={() => void openFile(f.path)}
              className={cn('rounded border px-1.5 py-0.5 text-[10px]', editPath === f.path ? 'border-sky-400/50 bg-sky-400/10 text-sky-200' : 'border-border bg-card text-muted-foreground hover:text-foreground')}>
              {f.name}
            </button>
          ))}
        </div>
        {editPath && (
          <div className="mt-2 h-64 overflow-hidden rounded-lg border border-border bg-[#0b0f17]" dir="ltr">
            <MonacoEditor
              height="100%"
              defaultLanguage="json"
              language={/\.env/i.test(editPath) ? 'ini' : 'json'}
              theme="vs-dark"
              value={editContent}
              onChange={(v) => { setEditContent(v ?? ''); setEditDirty(true) }}
              options={{ fontSize: 12, minimap: { enabled: false }, scrollBeyondLastLine: false, wordWrap: 'on', automaticLayout: true, padding: { top: 8 } }}
            />
          </div>
        )}
      </div>

      {/* 4️⃣ التيرمينال الحي */}
      <div className="rounded-xl border border-border bg-[#0a0e14] p-2">
        <p className="mb-1 flex items-center gap-2 px-1 text-xs font-medium text-emerald-300"><Terminal className="size-3.5" /> التيرمينال الحي — سجل العمليات</p>
        <div ref={termRef} className="flex h-40 flex-col-reverse overflow-y-auto px-1 font-mono text-[10px] leading-relaxed text-emerald-100/70" dir="ltr">
          {[...termLines].reverse().map((l, i) => <p key={i} className="whitespace-pre-wrap">{l}</p>)}
        </div>
      </div>
    </div>
  )
}
