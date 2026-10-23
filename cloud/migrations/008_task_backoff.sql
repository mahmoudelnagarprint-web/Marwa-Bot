-- 008_task_backoff.sql — الإرجاء المتزايد لمهام الوكلاء المجدولة
-- Cloud-only migration: the official POS SQLite database is not touched.
-- deferred_until: لا يلمس العامل المهمة قبل هذا الوقت (5 دقائق ثم 10 دقائق تصاعدياً)
-- backoff_level: 0 = محاولة فورية، 1 = 5 دقائق، 2+ = 10 دقائق
-- last_failure_reason: سبب الإرجاء الأخير للعرض في غرفة الوكيل بلا حذف أي سجل

alter table public.agent_tasks
  add column if not exists deferred_until timestamptz,
  add column if not exists backoff_level integer not null default 0,
  add column if not exists last_failure_reason text;

alter table public.agent_tasks drop constraint if exists agent_tasks_backoff_level_check;
alter table public.agent_tasks
  add constraint agent_tasks_backoff_level_check check (backoff_level >= 0 and backoff_level <= 6);

create index if not exists idx_agent_tasks_deferred
  on public.agent_tasks (deferred_until)
  where archived_at is null and schedule_type in ('daily', 'weekly');
