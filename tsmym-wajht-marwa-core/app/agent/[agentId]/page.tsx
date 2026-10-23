import { MarwaApp } from '@/components/marwa/marwa-app'
import { agents } from '@/lib/marwa-data'

export function generateStaticParams() {
  return agents.map((a) => ({
    agentId: a.id,
  }))
}

export default async function AgentPage({
  params,
}: {
  params: Promise<{ agentId: string }>
}) {
  const { agentId } = await params
  return (
    <main className="h-full w-full" suppressHydrationWarning>
      <MarwaApp initialAgentId={agentId} />
    </main>
  )
}
