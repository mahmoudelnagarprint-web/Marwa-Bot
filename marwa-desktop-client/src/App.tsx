'use client'

// App.tsx — هيكل مركز القيادة: شريط جانبي (وكلاء) + منطقة رئيسية (داشبورد/غرف)
import { useEffect, useState } from 'react'
import { dsh, type TransportKind } from '@/services/dsh-ipc'
import { AgentsSidebar } from '@/components/sidebar/AgentsSidebar'
import { Dashboard } from '@/components/dashboard/Dashboard'
import { AgentRoom } from '@/components/agent/AgentRoom'
import { agentById, type AgentId } from '@/lib/agents'

type View = 'dashboard' | AgentId

export default function App() {
  const [view, setView] = useState<View>('dashboard')
  const [transport, setTransport] = useState<TransportKind>('mock')
  const [bridgeConnected, setBridgeConnected] = useState(false)

  // إقلاع الجسر مرة واحدة — الاشتراك يحدّث شارة الحالة في الترويسة
  useEffect(() => {
    let unsub: (() => void) | null = null
    void dsh.boot().then((kind) => {
      setTransport(kind)
      setBridgeConnected(kind !== 'mock')
      unsub = dsh.subscribe((e) => {
        if (e.type === 'status') {
          setTransport(e.payload.transport)
          setBridgeConnected(e.payload.connected)
        }
      })
    })
    return () => unsub?.()
  }, [])

  const activeAgent = view === 'dashboard' ? null : agentById(view)

  return (
    <div className="flex h-full w-full overflow-hidden bg-matte-950 text-foreground">
      <AgentsSidebar active={view} onSelect={(v) => setView(v)} transport={transport} />

      <main className="flex min-w-0 flex-1 flex-col overflow-hidden">
        {/* الترويسة العلوية — حالة الجسر */}
        <header className="flex items-center justify-between gap-3 border-b border-matte-700 bg-matte-900 px-5 py-3">
          <div className="flex items-center gap-3">
            <span className="font-display text-lg font-bold text-gold-400 gold-glow rounded-lg border border-gold-800/60 bg-matte-900 px-3 py-1">
              MARWA CORE
            </span>
            <span className="text-xs text-matte-600 hidden md:inline">مركز القيادة المباشر</span>
          </div>
          <div className="flex items-center gap-2 text-xs">
            <span
              className={cn(
                'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 font-medium',
                bridgeConnected
                  ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
                  : 'border-amber-500/30 bg-amber-500/10 text-amber-300',
              )}
            >
              <span className={cn('size-2 rounded-full', bridgeConnected ? 'bg-emerald-400' : 'bg-amber-400 animate-pulse')} />
              {bridgeConnected ? `الجسر متصل (${transport})` : 'وضع العرض المحلي — بانتظار الجسر'}
            </span>
          </div>
        </header>

        <div className="min-h-0 flex-1">
          {view === 'dashboard' ? (
            <Dashboard transport={transport} />
          ) : activeAgent ? (
            activeAgent.phase === 'full' ? (
              activeAgent.id === 'marwa' ? (
                <AgentRoom agentId="marwa" onBack={() => setView('dashboard')} />
              ) : (
                <PlaceholderRoom agentId={activeAgent.id} onBack={() => setView('dashboard')} />
              )
            ) : (
              <PlaceholderRoom agentId={activeAgent.id} onBack={() => setView('dashboard')} />
            )
          ) : null}
        </div>
      </main>
    </div>
  )
}

function PlaceholderRoom({ agentId, onBack }: { agentId: string; onBack: () => void }) {
  const agent = agentById(agentId as AgentId)
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 p-8 text-center">
      <div className="flex size-16 items-center justify-center rounded-2xl border border-gold-800/60 bg-matte-900 font-display text-3xl font-bold text-gold-400 gold-glow">
        {agent.glyph}
      </div>
      <h2 className="font-display text-xl font-bold text-foreground">غرفة {agent.name}</h2>
      <p className="max-w-md text-sm leading-relaxed text-muted-foreground">
        الواجهة جاهزة والهوية مثبتة — بانتظار ربط محرك {agent.name} عبر جسر DSH. لن تُعرض أي بيانات وهمية هنا أبداً.
      </p>
      <button
        type="button"
        onClick={onBack}
        className="mt-2 rounded-lg border border-border bg-card px-4 py-2 text-sm text-foreground hover:bg-sidebar-accent/60"
      >
        العودة للداشبورد
      </button>
    </div>
  )
}

import { cn } from '@/lib/utils'
