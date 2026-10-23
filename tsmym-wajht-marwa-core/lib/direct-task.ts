import { createClient } from '@supabase/supabase-js'
import { enqueueInboxTask, lookupAgentKey } from '@/lib/agent-intelligence'

export type DirectTaskResult = {
  ok: boolean
  message: string
  taskId?: string
  agentId?: string
  title?: string
}

/** Parse and create an explicit owner /task command; no model interpretation is involved. */
export async function createDirectTask(command: string): Promise<DirectTaskResult> {
  const match = /^\s*\/task\s+@([\p{L}][\p{L}\p{N}_-]*)\s+([\s\S]{2,2000})\s*$/iu.exec(command)
  if (!match) {
    return { ok: false, message: 'الصيغة: /task @اسم_الوكيل تفاصيل المهمة' }
  }

  const agentId = lookupAgentKey(match[1])
  if (!agentId) return { ok: false, message: `اسم الوكيل @${match[1]} غير معروف.` }
  const detail = match[2].trim()
  const title = detail.replace(/\s+/g, ' ').slice(0, 120)
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL
  const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
  if (!url || !anonKey) return { ok: false, message: 'إعداد Supabase غير مكتمل؛ لم تُنشأ المهمة.' }

  const client = createClient(url, anonKey, { auth: { persistSession: false, autoRefreshToken: false } })
  const { data, error } = await client.from('agent_tasks').insert({
    agent_id: agentId,
    title,
    description: detail,
    status: 'pending',
    priority: 'normal',
    source: 'ui',
    created_by: 'mahmoud',
  }).select('id').single()

  if (error || !data?.id) {
    return { ok: false, message: `تعذر حفظ المهمة في قاعدة المهام: ${error?.message || 'استجابة غير مكتملة'}` }
  }

  const inbox = enqueueInboxTask({ from: 'marwa', to: agentId, type: 'task', body: detail })
  const inboxNotice = inbox.ok ? 'ووصلت لصندوق الوارد المحلي.' : `لكن تعذر تحديث صندوق الوارد المحلي: ${inbox.error || 'سبب غير معروف'}`
  return {
    ok: true,
    taskId: data.id,
    agentId,
    title,
    message: `اتسجلت المهمة «${title}» لـ@${agentId} في قاعدة المهام ${inboxNotice}`,
  }
}
