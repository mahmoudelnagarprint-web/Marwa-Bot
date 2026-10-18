-- 005_pulse_realtime.sql — ⚠️ DRAFT / NOT APPLIED ⚠️
-- Marwa Pulse: جداول الأحداث اللحظية (تصميم راصد 2026-10-18 — REALTIME_SYNC_ARCHITECTURE.md)
-- لا يُطبَّق هذا الملف إلا بموافقة المالك الصريحة (خطوة من خطة النشر المرحلية §8).
-- بعد التطبيق: يُسجَّل في applied_migrations.log وفق عادة المشروع.

-- ═══════════════════════════════════════════════════════════════
-- sync_events — بث تنبيهات التغيير (Control Plane لبروتوكول النبض)
-- المستهلك: لابتوب (سحب فوري عند حدث جديد من الورشة)
-- ═══════════════════════════════════════════════════════════════
create table if not exists public.sync_events (
  op_id      text primary key,              -- ULID من المصدر (idempotency)
  node       text not null,                 -- WORKSHOP | LAPTOP
  kind       text not null default 'db_change',  -- db_change | git_nudge | command_seen
  tables     text[] default '{all}',        -- الجداول التي تغيّرت (v1: all)
  hlc        text,                          -- ساعة هجينة: ترتيب سببي بين العقد
  created_at timestamptz default now()
);

create index if not exists idx_sync_events_created
  on public.sync_events (created_at desc);

-- ═══════════════════════════════════════════════════════════════
-- applied_ops — دفتر منع التكرار (I2: النقل at-least-once → التأثير exactly-once)
-- كل مستهلك يسجل ما طبّقه قبل التنفيذ؛ المكرر يُتخطى.
-- ═══════════════════════════════════════════════════════════════
create table if not exists public.applied_ops (
  op_id      text primary key,
  node       text not null default '',      -- من طبّق (تشخيص)
  applied_at timestamptz default now(),
  result     jsonb
);

-- ═══════════════════════════════════════════════════════════════
-- Realtime: نشر التغييرات للعقدتين (قناة واحدة لكل جدول)
-- يشترط تفعيل publication على الجدولين (Supabase → Database → Realtime)
-- ═══════════════════════════════════════════════════════════════
alter publication supabase_realtime add table public.sync_events;
alter publication supabase_realtime add table public.commands;   -- أوامر فورية بدل 60s

-- ═══════════════════════════════════════════════════════════════
-- RLS: الجداول تُدار بمفتاح الخدمة (service key) من سكربتات العقدتين فقط.
-- تمكين RLS = دفاع عميق: أي وصول بمفتاح publishable يُرفض.
-- ═══════════════════════════════════════════════════════════════
alter table public.sync_events enable row level security;
alter table public.applied_ops  enable row level security;
-- لا سياسات عامة عن قصد (deny-by-default) — الوصول عبر service_role فقط.

-- ═══════════════════════════════════════════════════════════════
-- قفل إيجار الكاتب الوحيد (W1) — يُخزن في system_brain_sync القائمة
-- أو جدول مخصص إن رغب المالك؛ هنا توثيق بروتوكولي (ملاحظة لا تعريف):
-- leader_lease: {"holder": "WORKSHOP", "expires_at": "...+90s"}
-- أي دفع مرآة من غير حامل الإيجار → رفض (طبقة حماية إضافية فوق W1).
-- ═══════════════════════════════════════════════════════════════
