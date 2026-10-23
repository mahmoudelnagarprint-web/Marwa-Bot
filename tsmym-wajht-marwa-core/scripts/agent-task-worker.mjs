// Local background poller for scheduled agent tasks.
// Start explicitly with `pnpm worker:tasks` after the database migration and env setup.
// This process does not send external messages and does not alter the POS database.
import { existsSync } from 'node:fs'
import { resolve } from 'node:path'

const envFile = resolve(process.cwd(), '.env.local')
if (existsSync(envFile) && typeof process.loadEnvFile === 'function') process.loadEnvFile(envFile)

const baseUrl = (process.env.MARWA_BASE_URL || 'http://127.0.0.1:3000').replace(/\/$/, '')
const token = process.env.AGENT_TASK_WORKER_TOKEN
const intervalMs = Math.max(15_000, Number(process.env.AGENT_TASK_WORKER_INTERVAL_MS || 30_000))

if (!token) {
  console.error('AGENT_TASK_WORKER_TOKEN is required; worker not started.')
  process.exit(1)
}

let stopping = false
for (const signal of ['SIGINT', 'SIGTERM']) {
  process.on(signal, () => { stopping = true })
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

while (!stopping) {
  try {
    const response = await fetch(`${baseUrl}/api/tasks/worker`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: '{}',
      signal: AbortSignal.timeout(120_000),
    })
    if (!response.ok && response.status !== 202) {
      console.error(`Worker API returned HTTP ${response.status}`)
    } else {
      const result = await response.json()
      if (result.claimed && result.deferred_ms) {
        // إرجاء متزايد: لا نموذج متاح — المهمة مؤجلة بلا حرق محاولات ولا أرصدة
        const minutes = Math.round(Number(result.deferred_ms) / 60_000)
        console.log(`Scheduled task deferred ${minutes}m (level ${result.backoff_level}): ${result.claimed}`)
      } else if (result.claimed) {
        console.log(`Scheduled task processed: ${result.claimed}`)
      } else if (result.error) {
        console.error(`Scheduled task failed: ${result.error}`)
      }
    }
  } catch (error) {
    console.error(`Worker request failed: ${error instanceof Error ? error.message : String(error)}`)
  }
  await sleep(intervalMs)
}
