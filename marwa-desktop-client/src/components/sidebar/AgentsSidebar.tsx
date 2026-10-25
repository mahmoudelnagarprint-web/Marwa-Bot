'use client'

import { cn } from '@/lib/utils'
import { AGENTS, agentById, type AgentId } from '@/lib/agents'
import type { TransportKind } from '@/services/dsh-ipc'

export function AgentsSidebar({
  active,
  onSelect,
  transport,
}: {
  active: 'dashboard' | AgentId
  onSelect: (v: 'dashboard' | AgentId) => void
  transport: TransportKind
}) {
  return (
    <aside className="hidden w-64 shrink-0 flex-col border-e border-matte-700 bg-matte-900 lg:flex" aria-label="وكلاء مروة كور">
      <div className="border-b border-matte-700 p-3">
        <button
          type="button"
          onClick={() => onSelect('dashboard')}
          aria-current={active === 'dashboard' ? 'page' : undefined}
          className={cn(
            'flex w-full items-center gap-3 rounded-lg px-2.5 py-2 text-start transition-colors',
            active === 'dashboard' ? 'bg-gold-400/10 text-gold-300' : 'text-foreground hover:bg-matte-800',
          )}
        >
          <span className="flex size-9 items-center justify-center rounded-lg border border-gold-800/60 bg-matte-950 font-display text-lg font-bold text-gold-400 gold-glow">
            م
          </span>
          <span className="min-w-0 flex-1">
            <span className="block text-sm font-semibold">لوحة القيادة</span>
            <span className="block truncate text-xs text-matte-600">نظرة عامة + الإسناد السريع</span>
          </span>
        </button>
      </div>

      <nav className="flex min-h-0 flex-1 flex-col gap-1 overflow-y-auto p-3 scrollbar-thin">
        <p className="mb-1 px-2.5 text-[11px] font-semibold tracking-wide text-gold-600">غرف الوكلاء</p>
        {AGENTS.map((a) => {
          const selected = active === a.id
          const info = agentById(a.id)
          return (
            <button
              key={a.id}
              type="button"
              onClick={() => onSelect(a.id)}
              aria-current={selected ? 'page' : undefined}
              className={cn(
                'flex items-center gap-3 rounded-lg px-2.5 py-2 text-start transition-colors',
                selected ? 'bg-gold-400/10 text-gold-200' : 'text-foreground hover:bg-matte-800',
              )}
            >
              <span
                className={cn(
                  'flex size-9 shrink-0 items-center justify-center rounded-lg border font-display text-base font-bold',
                  a.phase === 'full'
                    ? 'border-gold-800/60 bg-matte-950 text-gold-400'
                    : 'border-matte-600 bg-matte-850 text-matte-600',
                )}
              >
                {a.glyph}
              </span>
              <span className="min-w-0 flex-1">
                <span className="flex items-center gap-1.5">
                  <span className="truncate text-sm font-medium">{a.name}</span>
                  {a.phase === 'full' && (
                    <span className="size-1.5 shrink-0 rounded-full bg-emerald-400" title="المحرك مربوط" />
                  )}
                </span>
                <span className="block truncate text-[11px] text-matte-600">
                  {a.phase === 'full' ? info.title : 'بانتظار ربط المحرك…'}
                </span>
              </span>
            </button>
          )
        })}
      </nav>

      <div className="border-t border-matte-700 p-3">
        <div className="rounded-lg border border-matte-600 bg-matte-850 p-2.5">
          <p className="text-[10px] text-matte-600">ناقل الجسر</p>
          <p className="mt-0.5 font-mono text-[11px] text-gold-300">{transport}</p>
        </div>
      </div>
    </aside>
  )
}
