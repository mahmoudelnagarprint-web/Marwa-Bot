// scripts/test-agent-tasks-insert.mjs — إثبات قراءة/إدراج agent_tasks
// بنفس مسار الواجهة بالضبط: supabase-js + anon key من .env.local + سياسات anon.
// يُنشئ مهمة اختبار معلَّمة (source=ui مثل زر الواجهة) ثم يقرأ الجدول للتحقق.
// لا يطبع أي مفاتيح أو قيم إعدادات — فقط النتائج.
import { createClient } from '@supabase/supabase-js'
import { readFileSync } from 'node:fs'

const env = {}
for (const line of readFileSync(new URL('../.env.local', import.meta.url), 'utf8').split('\n')) {
  if (line.trim().startsWith('#') || !line.includes('=')) continue
  const idx = line.indexOf('=')
  env[line.slice(0, idx).trim()] = line.slice(idx + 1).trim()
}

const url = env.NEXT_PUBLIC_SUPABASE_URL
const key = env.NEXT_PUBLIC_SUPABASE_ANON_KEY
console.log('env loaded:', { hasUrl: Boolean(url), hasKey: Boolean(key) })
const supabase = createClient(url, key)

const title = 'مهمة اختبار من واجهة فيجن (PoC task-2) — تحقق إدراج agent_tasks'
console.log('== SELECT agent_tasks for fares ==')
const sel = await supabase
  .from('agent_tasks')
  .select('id, agent_id, title, status, priority, source, created_by, created_at')
  .eq('agent_id', 'fares')
  .order('created_at', { ascending: false })
  .limit(10)
if (sel.error) {
  console.log('SELECT ERROR:', sel.error.code ?? '', sel.error.message)
} else {
  console.log(`rows: ${sel.data.length}`)
  for (const t of sel.data) console.log(`- [${t.status}] ${t.title} (source=${t.source}) created=${t.created_at}`)
}

console.log('\n== INSERT test task (same payload shape as UI button) ==')
const ins = await supabase
  .from('agent_tasks')
  .insert({
    agent_id: 'fares',
    title,
    description: 'من اختبار فيجن الآلي — نفس مسار زر «إضافة» في الواجهة (anon INSERT policy)',
    status: 'pending',
    priority: 'normal',
    source: 'ui',
  })
  .select()
  .limit(1)
if (ins.error) {
  console.log('INSERT ERROR:', ins.error.code ?? '', ins.error.message)
  process.exitCode = 1
} else {
  console.log('INSERT OK id:', ins.data?.[0]?.id, 'status:', ins.data?.[0]?.status)
}

console.log('\n== agent_updates (suggestion) ==')
const upd = await supabase
  .from('agent_updates')
  .select('id, kind, title, status, severity, created_at')
  .eq('agent_id', 'fares')
  .order('created_at', { ascending: false })
  .limit(5)
if (upd.error) {
  console.log('agent_updates ERROR:', upd.error.message)
} else {
  for (const u of upd.data ?? []) console.log(`- [${u.kind}/${u.status}] ${u.title} (${u.severity ?? '—'}) ${u.created_at}`)
}
