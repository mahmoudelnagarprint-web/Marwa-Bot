-- 006_agent_workspace.sql — MARWA CORE: العقل السحابي للواجهة (تطبيق بأمر المالك 2026-10-20)
-- جداول غرفة الوكيل: agent_tasks (المهام) + agent_updates (الاقتراحات والشكاوى)
-- يُطبَّق على السحابة فقط عبر cloud/apply_006_cloud.py — القاعدة الحية pos_data.db بلا أي لمس.
-- النمط: 005_pulse_realtime.sql (RLS + publication + تسجيل schema_migrations).

-- ═══════════════════════════════════════════════════════════════
-- agent_tasks — المهام الجارية لكل وكيل (تُكتب من الواجهة ومن fast_ops.py)
-- ═══════════════════════════════════════════════════════════════
create table if not exists public.agent_tasks (
  id          uuid primary key default gen_random_uuid(),
  agent_id    text not null check (agent_id in ('salma','fares','bebo','koko','rased','vision','marwa')),
  title       text not null,
  description text,
  status      text not null default 'pending'
              check (status in ('pending','in_progress','done','rejected')),
  priority    text not null default 'normal'
              check (priority in ('low','normal','high','urgent')),
  source      text not null default 'ui' check (source in ('ui','notebook','agent','marwa')),
  created_by  text not null default 'mahmoud',
  result_note text,
  op_id       text unique,                    -- idempotency (ULID من المصدر)
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

create index if not exists idx_agent_tasks_agent
  on public.agent_tasks (agent_id, created_at desc);
create index if not exists idx_agent_tasks_status
  on public.agent_tasks (status);

-- ═══════════════════════════════════════════════════════════════
-- agent_updates — الاقتراحات والشكاوى والتنبيهات (أزرار ✅ اعتماد / ❌ رفض)
-- ═══════════════════════════════════════════════════════════════
create table if not exists public.agent_updates (
  id         uuid primary key default gen_random_uuid(),
  agent_id   text not null check (agent_id in ('salma','fares','bebo','koko','rased','vision','marwa')),
  kind       text not null default 'suggestion'
             check (kind in ('suggestion','complaint','alert','report')),
  title      text not null,
  body       text,
  severity   text default 'متوسط' check (severity in ('عالي','متوسط','منخفض')),
  status     text not null default 'pending' check (status in ('pending','approved','rejected')),
  decided_by text,
  decided_at timestamptz,
  payload    jsonb,
  op_id      text unique,
  created_at timestamptz not null default now()
);

create index if not exists idx_agent_updates_agent
  on public.agent_updates (agent_id, created_at desc);

-- ملاحظة تنفيذية: لا trigger دوال plpgsql هنا — مقسّم الجُمل الرسمي
-- (_split_statements) لا يدعم dollar-quoting؛ updated_at يُضبط من الكاتب
-- (supabase-js / fast_ops.py) في كل UPDATE. جداول خفيفة كما أمر المالك.

-- ═══════════════════════════════════════════════════════════════
-- Realtime: بث لحظي للواجهة (WebSockets — supabase-js)
-- ═══════════════════════════════════════════════════════════════
alter publication supabase_realtime add table public.agent_tasks;
alter publication supabase_realtime add table public.agent_updates;

-- ═══════════════════════════════════════════════════════════════
-- RLS + سياسات anon: الواجهة تقرأ وتكتب بمفتاح publishable (أداة داخلية
-- لعقدة واحدة) — لا سياسة حذف إطلاقاً (W3: لا حذف من السحابة).
-- الكتابة الإدارية الحساسة تبقى عبر مفتاح الخدمة في fast_ops.py.
-- ═══════════════════════════════════════════════════════════════
alter table public.agent_tasks   enable row level security;
alter table public.agent_updates enable row level security;

drop policy if exists agent_tasks_anon_select on public.agent_tasks;
create policy agent_tasks_anon_select on public.agent_tasks
  for select to anon using (true);

drop policy if exists agent_tasks_anon_insert on public.agent_tasks;
create policy agent_tasks_anon_insert on public.agent_tasks
  for insert to anon with check (true);

drop policy if exists agent_tasks_anon_update on public.agent_tasks;
create policy agent_tasks_anon_update on public.agent_tasks
  for update to anon using (true) with check (true);

drop policy if exists agent_updates_anon_select on public.agent_updates;
create policy agent_updates_anon_select on public.agent_updates
  for select to anon using (true);

drop policy if exists agent_updates_anon_insert on public.agent_updates;
create policy agent_updates_anon_insert on public.agent_updates
  for insert to anon with check (true);

drop policy if exists agent_updates_anon_update on public.agent_updates;
create policy agent_updates_anon_update on public.agent_updates
  for update to anon using (true) with check (true);

grant select, insert, update on public.agent_tasks   to anon;
grant select, insert, update on public.agent_updates to anon;
