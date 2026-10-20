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
  agent: Pick<Agent, 'name' | 'image' | 'status' | 'tone'>
  size?: number
  showStatus?: boolean
  className?: string
}) {
  return (
    <span className={cn('relative inline-flex shrink-0', className)} style={{ width: size, height: size }}>
      <Image
        src={agent.image}
        alt={agent.name}
        width={size * 2}
        height={size * 2}
        className={cn('size-full rounded-full object-cover ring-1', agent.tone.ring)}
      />
      {showStatus && (
        <span
          className={cn(
            'absolute -bottom-0.5 -start-0.5 size-2.5 rounded-full ring-2 ring-sidebar',
            statusColor[agent.status],
          )}
          aria-hidden="true"
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
