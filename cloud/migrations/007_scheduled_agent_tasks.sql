-- 007_scheduled_agent_tasks.sql — Scheduled tasks, dependencies and audit-safe archive
-- Local migration draft only. Do NOT apply to the live database without a separate owner approval.
-- The official POS SQLite database is not touched by this migration.

alter table public.agent_tasks
  add column if not exists dependency_id uuid references public.agent_tasks(id) on delete restrict,
  add column if not exists archived_at timestamptz,
  add column if not exists schedule_type text not null default 'none',
  add column if not exists scheduled_time time,
  add column if not exists schedule_day_of_week smallint,
  add column if not exists schedule_timezone text not null default 'Africa/Cairo',
  add column if not exists last_run_at timestamptz,
  add column if not exists attempt_count integer not null default 0;

-- Migration 006 only whitelisted part of the current agent roster.
alter table public.agent_tasks drop constraint if exists agent_tasks_agent_id_check;
alter table public.agent_tasks add constraint agent_tasks_agent_id_check
  check (agent_id in ('salma','fares','bebo','koko','rased','vision','marwa','sasa','hakim','afkar'));
alter table public.agent_updates drop constraint if exists agent_updates_agent_id_check;
alter table public.agent_updates add constraint agent_updates_agent_id_check
  check (agent_id in ('salma','fares','bebo','koko','rased','vision','marwa','sasa','hakim','afkar'));

alter table public.agent_tasks drop constraint if exists agent_tasks_schedule_type_check;
alter table public.agent_tasks drop constraint if exists agent_tasks_schedule_consistency_check;
alter table public.agent_tasks drop constraint if exists agent_tasks_schedule_day_check;
alter table public.agent_tasks drop constraint if exists agent_tasks_not_self_dependent_check;
alter table public.agent_tasks drop constraint if exists agent_tasks_attempt_count_check;
alter table public.agent_tasks
  add constraint agent_tasks_schedule_type_check
    check (schedule_type in ('none', 'daily', 'weekly')),
  add constraint agent_tasks_schedule_consistency_check
    check ((schedule_type = 'none' and scheduled_time is null and schedule_day_of_week is null) or
           (schedule_type = 'daily' and scheduled_time is not null and schedule_day_of_week is null) or
           (schedule_type = 'weekly' and scheduled_time is not null and schedule_day_of_week between 0 and 6)),
  add constraint agent_tasks_schedule_day_check
    check (schedule_day_of_week is null or schedule_day_of_week between 0 and 6),
  add constraint agent_tasks_not_self_dependent_check
    check (dependency_id is null or dependency_id <> id),
  add constraint agent_tasks_attempt_count_check
    check (attempt_count >= 0);

create index if not exists idx_agent_tasks_dependency
  on public.agent_tasks (dependency_id) where dependency_id is not null;

create index if not exists idx_agent_tasks_scheduled
  on public.agent_tasks (schedule_type, status, scheduled_time)
  where archived_at is null and schedule_type in ('daily', 'weekly');

create index if not exists idx_agent_tasks_active_agent_created
  on public.agent_tasks (agent_id, created_at desc)
  where archived_at is null;
