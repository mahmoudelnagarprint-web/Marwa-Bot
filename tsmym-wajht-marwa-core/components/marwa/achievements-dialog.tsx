'use client'

// components/marwa/achievements-dialog.tsx — الإنجازات (MARWA CORE)
// مُطهَّر (task-2 فيجن): لا شارات إنجاز متخيلة (كانت «تحصيل المليون 78%»
// و«حساب شركة الأفق» إلخ). يعرض الآن أهداف المنظومة من الميثاق/الدفاتر الرسمية
// بلا إنجازات مزعومة، وسجل إنجازات فارغ حتى يسجل الدماغ السحابي إنجازاً حقيقياً.

import { Flame, Lock, Trophy } from 'lucide-react'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'

// أهداف المنظومة المعتمدة (من الدفاتر الرسمية) — كلها غير محققة بعد، بلا نسب متخيلة
const goals = [
  { title: 'أسبوع بلا تأخير', desc: '7 أيام تسليم في الموعد — قياس حي من الطلبات' },
  { title: 'فريق متكامل', desc: 'تفعيل كل الوكلاء في مهمة واحدة' },
  { title: 'صفر طلبات بلا سداد', desc: 'توثيق السداد لكل طلبية لحظة إنشائها (§6-4)' },
  { title: 'جرد الخامات مكتمل', desc: 'جرد فعلي لجدول فارس §5 كاملاً' },
  { title: 'شيفت يومي مُقفل', desc: 'أول إقفال رسمي بتصفير رقابي (§2)' },
  { title: 'هامش صافي محسوب', desc: 'وصفات التصنيع مكتملة لكل الكتالوج (§4-ب)' },
]

export function AchievementsDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85dvh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Trophy className="size-4 text-amber-300" aria-hidden="true" />
            الإنجازات
          </DialogTitle>
          <DialogDescription>تقدم المنظومة — يُحسب من بيانات حقيقية فقط، بلا إنجازات متخيلة.</DialogDescription>
        </DialogHeader>

        <div className="grid gap-2 sm:grid-cols-3">
          <div className="rounded-xl border border-amber-400/20 bg-amber-400/[0.06] p-4 sm:col-span-2">
            <p className="text-xs text-muted-foreground">المستوى الحالي</p>
            <p className="mt-1 flex items-baseline gap-2">
              <span className="font-mono text-3xl font-semibold tabular-nums">—</span>
              <span className="text-sm text-amber-200">يُفعَّل بعد أول شيفت يومي مقفل</span>
            </p>
            <p className="mt-3 text-[11px] text-muted-foreground">
              نقاط المستوى تُبنى من إنجازات موثقة (لا نقاط تقديرية).
            </p>
          </div>
          <div className="rounded-xl border border-border bg-card p-4">
            <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <Flame className="size-3.5 text-rose-300" aria-hidden="true" />
              سلسلة الإنجاز
            </p>
            <p className="mt-1 font-mono text-3xl font-semibold tabular-nums">0</p>
            <p className="text-[11px] text-muted-foreground">تبدأ من أول يوم تشغيل رسمي</p>
          </div>
        </div>

        <ul className="grid grid-cols-2 gap-2 sm:grid-cols-3">
          {goals.map((b) => (
            <li key={b.title} className="rounded-xl border border-dashed border-border bg-transparent p-3">
              <span className="flex size-8 items-center justify-center rounded-lg bg-muted text-muted-foreground">
                <Lock className="size-3.5" aria-hidden="true" />
              </span>
              <p className="mt-2 text-sm font-medium">{b.title}</p>
              <p className="text-[11px] leading-relaxed text-muted-foreground">{b.desc}</p>
            </li>
          ))}
        </ul>

        <section>
          <h3 className="mb-2 text-sm font-medium">آخر إنجازات الوكلاء</h3>
          <ul className="flex flex-col divide-y divide-border rounded-xl border border-border bg-card px-3">
            <li className="py-6 text-center text-xs text-muted-foreground">
              لم تُسجَّل إنجازات حية بعد — تُوثَّق هنا عند اعتماد أول إنجاز من دفاتر الفريق.
            </li>
          </ul>
        </section>
      </DialogContent>
    </Dialog>
  )
}
