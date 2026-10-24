-- cloud/migrations/007_facebook_interactions.sql — المرحلة: الذكاء التفاعلي مع السوشيال ميديا
-- بأمر المالك 2026-10-24 (تكليف مروة-اللابتوب): ربط الوكلاء بفيسبوك — فريق عمل حي.
-- الأمان: RLS مفعّل — anon يملك select/insert/update (بلا حذف — نفس نمط W3 في 006).

-- ─── 1) منشورات فيسبوك (لتحليل أداء كوكو) ───
create table if not exists facebook_posts (
  id uuid primary key default gen_random_uuid(),
  page_name text not null,                    -- 'النجار برنت' | 'ليان ستور'
  fb_post_id text unique not null,            -- معرف المنشور في Graph API
  message text,                               -- نص المنشور
  published_at timestamptz,
  likes integer default 0,
  comments_count integer default 0,
  shares integer default 0,
  reach bigint default 0,
  permalink text,
  collected_at timestamptz not null default now()
);

-- ─── 2) تفاعلات فيسبوك (تعليقات + ردود سلمى المقترحة) ───
create table if not exists facebook_interactions (
  id uuid primary key default gen_random_uuid(),
  page_name text not null,
  fb_comment_id text unique not null,         -- منع التكرار على مستوى القاعدة
  post_fb_id text,
  post_preview text,                          -- مقطع من نص المنشور للعرض السريع
  commenter_name text not null,
  comment_text text not null,
  comment_created_at timestamptz,
  suggested_reply text,                       -- مسودة سلمى (توليد آلي)
  reply_status text not null default 'pending'
    check (reply_status in ('pending','approved','sent','rejected','skipped')),
  replied_at timestamptz,
  replied_by text,
  meta jsonb default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists idx_fb_interactions_status on facebook_interactions (reply_status, created_at desc);

-- ─── 3) تقارير السوشيال ميديا (كوكو) ───
create table if not exists social_reports (
  id uuid primary key default gen_random_uuid(),
  agent_id text not null default 'koko',
  period_label text not null,                 -- مثال: 'أسبوع 20-26 أكتوبر'
  metrics jsonb default '{}'::jsonb,          -- {total_posts, total_comments, avg_engagement...}
  best_posts jsonb default '[]'::jsonb,       -- أفضل البوستات أداءً
  analysis text,                              -- تحليل مبدئي مكتوب
  suggestions text,                           -- مقترحات الحملة القادمة
  created_at timestamptz not null default now()
);

-- ─── 4) سياسات RLS (deny-by-default + منح القراءة/الإضافة/التحديث لـanon — بلا حذف) ───
alter table facebook_posts enable row level security;
alter table facebook_interactions enable row level security;
alter table social_reports enable row level security;

drop policy if exists fb_posts_anon_read on facebook_posts;
create policy fb_posts_anon_read on facebook_posts for select to anon using (true);
drop policy if exists fb_posts_anon_insert on facebook_posts;
create policy fb_posts_anon_insert on facebook_posts for insert to anon with check (true);

drop policy if exists fb_interactions_anon_read on facebook_interactions;
create policy fb_interactions_anon_read on facebook_interactions for select to anon using (true);
drop policy if exists fb_interactions_anon_insert on facebook_interactions;
create policy fb_interactions_anon_insert on facebook_interactions for insert to anon with check (true);
drop policy if exists fb_interactions_anon_update on facebook_interactions;
create policy fb_interactions_anon_update on facebook_interactions for update to anon using (true) with check (true);

drop policy if exists social_reports_anon_read on social_reports;
create policy social_reports_anon_read on social_reports for select to anon using (true);
drop policy if exists social_reports_anon_insert on social_reports;
create policy social_reports_anon_insert on social_reports for insert to anon with check (true);

-- ─── 5) بث لحظي: تعليق جديد = إشعار فوري في الواجهة ───
alter publication supabase_realtime add table facebook_interactions;
