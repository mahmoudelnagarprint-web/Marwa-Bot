-- 009_orphan_recovery.sql — تحرير المهام العالقة (Zombie / Orphaned Tasks)
-- Cloud-only migration: the official POS SQLite database is not touched.
-- المشكلة: عامل يحجز مهمة (in_progress) ثم يموت أو يرمي خطأ قاتل غير مُلتقَط،
--          فتبقى المهمة «جارية» للأبد ولا يلتقطها أي عامل آخر.
-- الحل: أعمدة تُثبت مَن حجزها ومتى، وعدّاد تحرير يمنع الحلقة الساخنة على مهمة مسمومة.

-- claimed_by: هوية من حجز المهمة ('worker' / 'manual') — يُصفَّر عند التحرير أو الإغلاق
-- claimed_at: لحظة الحجز — مرجع إضافي لحساب العمر الفعلي للمهمة الجارية
-- release_count: كم مرة أُعيدت هذه المهمة للطابور بعد عُلوقها (حماية من مهمة تُسقِط العامل كل مرة)
alter table public.agent_tasks
  add column if not exists claimed_by text,
  add column if not exists claimed_at timestamptz,
  add column if not exists release_count integer not null default 0;

alter table public.agent_tasks drop constraint if exists agent_tasks_release_count_check;
alter table public.agent_tasks
  add constraint agent_tasks_release_count_check check (release_count >= 0 and release_count <= 50);

-- فحص اليتامى يبدأ دائماً من المهام الجارية وحدها: فهرس جزئي صغير جداً
create index if not exists idx_agent_tasks_stuck
  on public.agent_tasks (updated_at)
  where archived_at is null and status = 'in_progress';

-- طابور الإسناد السريع (schedule_type='none') — كان خارج نطاق العامل تماماً قبل 009
create index if not exists idx_agent_tasks_adhoc_queue
  on public.agent_tasks (status, created_at)
  where archived_at is null and schedule_type = 'none';

-- طابور المهام الأقدم ملاحظةً: الإسناد السريع يلتقط الأقدم أولاً
comment on column public.agent_tasks.release_count is
  'عدد مرات تحرير المهمة من حالة in_progress بعد توقف العامل — عند تجاوز الحد تُؤرشف كمهمة مسمومة';
