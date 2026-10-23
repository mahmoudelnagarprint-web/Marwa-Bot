'use client'

// components/marwa/settings-dialog.tsx — الإعدادات العامة (أمر المالك 2026-10-23)
// 🎛️ إعادة تصميم Edge-to-Edge: اللوحة تملأ الشاشة بالكامل بالهوية الداكنة الزجاجية،
// بترويسة ثابتة (Sticky) وشريط تنقّل جانبي — مثل باقي شاشات المنظومة.

import { useState } from 'react'
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog'
import { Cpu, Files, Settings2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import { AiFleet } from './ai-fleet'
import { WorkspaceFiles } from './workspace-files'

type Pane = 'fleet' | 'workspaces'

const NAV: { id: Pane; label: string; hint: string; icon: typeof Cpu }[] = [
  { id: 'fleet', label: 'أسطول الذكاء', hint: 'المزودون والنماذج والاختبار الحي', icon: Cpu },
  { id: 'workspaces', label: 'ملفات الـ Workspaces', hint: 'مرجع عميق لملفات الوكلاء', icon: Files },
]

export function SettingsDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
  const [pane, setPane] = useState<Pane>('fleet')

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        showCloseButton
        className="inset-0 top-0 left-0 flex h-dvh w-screen max-w-none translate-x-0 translate-y-0 flex-col gap-0 overflow-hidden rounded-none border-0 bg-background p-0 text-foreground ring-0 data-open:zoom-in-100 sm:max-w-none"
      >
        {/* ترويسة ثابتة Edge-to-Edge */}
        <header className="flex shrink-0 flex-wrap items-center gap-3 border-b border-border/60 bg-sidebar/80 px-5 py-3 pe-14 backdrop-blur-xl">
          <span className="flex size-9 shrink-0 items-center justify-center rounded-xl border border-primary/30 bg-primary/15">
            <Settings2 className="size-4 text-primary" aria-hidden="true" />
          </span>
          <div className="min-w-0 leading-tight">
            <DialogTitle className="font-display text-base font-semibold text-foreground">
              الإعدادات العامة — بوابة الذكاء الاصطناعي
            </DialogTitle>
            <DialogDescription className="truncate text-[11px] text-muted-foreground">
              إدارة مزودي الذكاء للمنظومة كلها — نفس المحرك يغذي الشات الرئيسي وكل الغرف
            </DialogDescription>
          </div>
        </header>

        <div className="flex min-h-0 flex-1 flex-col md:flex-row">
          {/* شريط تنقّل عمودي (أفقي في الموبايل) */}
          <nav
            aria-label="أقسام الإعدادات"
            className="flex shrink-0 gap-1.5 overflow-x-auto border-b border-border/50 bg-card/20 p-2 md:w-56 md:flex-col md:overflow-y-auto md:border-e md:border-b-0 scrollbar-thin"
          >
            {NAV.map(({ id, label, hint, icon: Icon }) => {
              const active = pane === id
              return (
                <button
                  key={id}
                  type="button"
                  onClick={() => setPane(id)}
                  aria-current={active ? 'page' : undefined}
                  className={cn(
                    'group flex shrink-0 items-center gap-2.5 rounded-xl px-3 py-2 text-start transition-all md:w-full',
                    active
                      ? 'border border-primary/25 bg-primary/10 text-foreground shadow-sm'
                      : 'border border-transparent text-muted-foreground hover:bg-accent/60 hover:text-foreground',
                  )}
                >
                  <Icon className={cn('size-4 shrink-0', active ? 'text-primary' : 'text-muted-foreground')} aria-hidden="true" />
                  <span className="min-w-0">
                    <span className="block truncate text-xs font-semibold">{label}</span>
                    <span className="hidden truncate text-[10px] text-muted-foreground md:block">{hint}</span>
                  </span>
                </button>
              )
            })}
          </nav>

          {/* مساحة المحتوى: تملأ الباقي بلا هوامش */}
          <div className="min-h-0 flex-1 overflow-y-auto scrollbar-thin">
            {pane === 'fleet' ? (
              <AiFleet />
            ) : (
              <div className="p-4 md:p-6">
                <p className="mb-3 flex items-center gap-2 text-sm font-semibold text-foreground">
                  <Files className="size-4 text-primary" aria-hidden="true" />
                  ملفات الـ Workspaces
                </p>
                <WorkspaceFiles />
              </div>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
