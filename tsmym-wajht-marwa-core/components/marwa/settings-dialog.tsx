'use client'

// components/marwa/settings-dialog.tsx — الإعدادات العامة (أمر المالك 2026-10-21)
// ⚙️ في الشريط العلوي تفتح النافذة: أسطول الذكاء الاصطناعي + ملفات الـ Workspaces.
// انتقلت من غرفة فيجن لتصبح إعداداً عاماً للمنظومة كلها (ليست أداة وكيل).

import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { AiFleet } from './ai-fleet'
import { WorkspaceFiles } from './workspace-files'
import { IntegrationsPanel } from './integrations-panel'

export function SettingsDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[88dvh] overflow-y-auto sm:max-w-4xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-lg">
            ⚙️ الإعدادات العامة — بوابة الذكاء الاصطناعي
          </DialogTitle>
          <DialogDescription>
            إدارة مزودي الذكاء الاصطناعي للمنظومة كلها: سحب النماذج تلقائياً، اختبار حي، ومؤشر الاستهلاك — نفس المحرك يغذي الشات الرئيسي وكل الغرف.
          </DialogDescription>
        </DialogHeader>

        <div className="rounded-xl border border-border bg-card/40">
          <AiFleet />
        </div>

        <div className="mt-2 border-t border-border pt-3">
          <p className="mb-2 text-sm font-medium text-muted-foreground">📁 ملفات الـ Workspaces (مرجع عميق)</p>
          <div className="max-h-72 overflow-y-auto scrollbar-thin">
            <WorkspaceFiles />
          </div>
        </div>

        <div className="mt-2 border-t border-border pt-3">
          <IntegrationsPanel />
        </div>
      </DialogContent>
    </Dialog>
  )
}
