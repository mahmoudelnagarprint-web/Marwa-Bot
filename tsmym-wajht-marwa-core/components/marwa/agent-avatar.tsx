import Image from 'next/image'
import { cn } from '@/lib/utils'
import type { Agent } from '@/lib/marwa-data'

const statusColor: Record<Agent['status'], string> = {
  online: 'bg-emerald-400',
  busy: 'bg-amber-400',
  idle: 'bg-zinc-500',
}

export function AgentAvatar({
  agent,
  size = 32,
  showStatus = false,
  className,
}: {
  /** يقبل undefined/null بأمان — يعود للهوية الافتراضية لمروة بدل الانهيار (إصلاح TypeError 2026-10-23) */
  agent?: Pick<Agent, 'name' | 'image' | 'status' | 'tone'> | null
  size?: number
  showStatus?: boolean
  className?: string
}) {
  // هوية احتياطية آمنة إن لم يوجد وكيل مطابق (ضيف غير مسجل أو مفتاح غريب)
  const safeAgent = agent ?? marwaProfile
  return (
    <span
      className={cn('relative inline-flex shrink-0', className)}
      style={{ width: size, height: size }}
      suppressHydrationWarning
    >
      <Image
        src={safeAgent.image}
        alt={safeAgent.name}
        width={size * 2}
        height={size * 2}
        suppressHydrationWarning
        className={cn('size-full rounded-full object-cover ring-1', safeAgent.tone?.ring ?? marwaProfile.tone.ring)}
      />
      {showStatus && (
        <span
          className={cn(
            'absolute -bottom-0.5 -start-0.5 size-2.5 rounded-full ring-2 ring-sidebar',
            statusColor[safeAgent.status],
          )}
          aria-hidden="true"
          suppressHydrationWarning
        />
      )}
    </span>
  )
}

export const marwaProfile = {
  name: 'مروة',
  image: '/agents/marwa.png',
  status: 'online' as const,
  tone: {
    text: 'text-zinc-200',
    softBg: 'bg-zinc-400/10',
    border: 'border-zinc-400/20',
    dot: 'bg-zinc-300',
    ring: 'ring-zinc-400/30',
    gradient: 'from-zinc-400/[0.06]',
    activeBg: 'bg-zinc-400/[0.14]',
  },
}
