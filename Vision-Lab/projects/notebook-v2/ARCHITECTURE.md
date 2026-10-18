# 🏛️ Notebook v2 — Proactive Second Brain & Unified Command Center
## Revised Architecture Plan (2026-10-18)

> الطلب: تحويل «النوتبوك الذكية» من مساعد ملاحظات محلي إلى **مركز قيادة موحد**
> لمنظومة النجار برنت: ينسّق المحل (Layan Store / Marwa Fashion / Sokar Banat)
> وورشة النجار برنت والوكلاء، بوت تليجرام شخصي 24/7، ذكاء سحابي قابل للإدارة،
> وعقدتين بتغطي بعض — بحيث البوت لا يتوقف أبدًا.

---

## 1. Executive Summary

| | v1 (اليوم) | v2 (الخطة) |
|---|---|---|
| العقل | SQLite محلي على جهاز واحد | **Supabase PostgreSQL + pgvector** — ذاكرة مشتركة بين كل الأجهزة |
| البوت | @Marwty_bot بـ polling على جهاز واحد + lock file محلي | **@Afkary22Bot** مستقل، مع **عقدة قيادة (leader lease)** على القاعدة السحابية — failover ≤ 45 ثانية |
| الذكاء | قواعد عربية محلية فقط (offline) | قواعد محلية **+ طبقة سحابية** (DeepSeek/OpenAI/Groq/Dahl…) تُدار من صفحة ويب بمفاتيح مشفرة وتبديل ديناميكي |
| التغطية | نوتات/مهام/تذكيرات شخصية | + **ورشة النجار برنت** (موديول مستقل)، **Retail** (لقطات قراءة فقط + تقارير الوكلاء)، **خزنة برومبتات** ببحث دلالي |
| الاستباقية | تذكيرات + ملخص صباحي | + **رادار المشاريع الراكدة**، **بومودورو/تايمبوكسينج**، صندوق إرسال موحد بمنع تكرار |
| الواجهة | صفحة واحدة | صفحات منظمة: لوحة القيادة / **مزودو الـAI** / الورشة / الخزنة |

**قاعدة حاكمة محفوظة من v1:** قاعدة POS الخاصة بالمحل **قراءة فقط** ولا تُكتب أبدًا.

---

## 2. Audit of v1 — ما نبني عليه

نقاط قوة نحافظ عليها حرفيًا (من مراجعة `notebook/`):

1. **البوت بدون مكتبات خارجية** — `telegram_bridge.py` يعمل بـ urllib خالص: تشغيل فوري على أي جهاز بلا pip. v2 يمدّه بقوائم Inline Keyboard ونفس فلسفة الصفر تبعيات.
2. **العقل العربي** (`brain.py`) — تطبيع، تصنيف، استخراج مواعيد («بكرة الساعة 5»)، أولويات، أسئلة توضيحية. يُنقل كطبقة أولى offline-safe في `ai_router.py`.
3. **الأمان الصامت** — الرد على المحادثات المسموحة فقط، مع رفض تعارض الويب هوك (409) بصدق.
4. **مواعيد الصلاة** (`prayer.py`) — تحسب محليًا بدون إنترنت وتُدمج في الجدولة.
5. **نمط الخدمات** (`install_services.ps1`) — schtasks كل 5 دقائق كـ keep-alive مع فحوص single-instance.

الفجوات التي تعالجها v2: بيانات محبوسة على جهاز واحد، لا مزامنة عقدتين، لا إدارة لمزودي AI، لا بحث دلالي، لا موديول ورشة، لا تنسيق مع المحل/الوكلاء، ولا رادار مشاريع.

---

## 3. Target System Overview

```
                        ┌────────────────────────────────────────────┐
                        │            Telegram (المالك)              │
                        │        @Afkary22Bot  (owner-only)          │
                        └───────────────▲────────────────────────────┘
                                        │ polling (Leader فقط)
   WORKSHOP DESKTOP ──────────────┐     │      ┌────────────── SURFACE PRO 4
  ┌────────────────────────────┐  │     │      │  ┌───────────────────────────┐
  │ start_node.py              │  │     │      │  │ start_node.py             │
  │  • Web UI :8110            │──┼─────┼──────┼──│  • Web UI :8110            │
  │  • Bot (إذا Leader)        │  │     │      │  │  • Bot (إذا Leader)        │
  │  • Proactive crons         │  │     │      │  │  • Proactive crons         │
  │  • HA heartbeat            │  │     │      │  │  • HA heartbeat            │
  │  • Retail POS pull (قراءة)  │  │     │      │  │  • (standby جاهز)          │
  └───────────┬────────────────┘  │     │      │  └───────────┬───────────────┘
              │                   └─────┼──────┘              │
              ▼                         ▼                      ▼
   POS SQLite (قراءة فقط)      ┌──────────────────────────────────────┐
   (قاعدة المحل لا تُمس)        │   Supabase PostgreSQL + pgvector     │
                              │   العقل المشترك الوحيد (source of   │
   وكلاء مروة (تقارير) ──────▶ │   truth): captures, projects, vault, │
   POST /api/agents/report     │   ws_*, retail_*, nodes, lease,     │
   (X-NB2-Token)               │   agent_reports, outbox, cron_runs  │
                              └──────────────▲───────────────────────┘
   مزودو AI السحابيون ◀──────────────────────┘  nb/providers.py
   (DeepSeek / OpenAI / Groq / Dahl … مفاتيح مشفرة + اكتشاف نماذج)
```

**المبادئ:**
1. **Single Source of Truth**: كل الحالة في PostgreSQL السحابي — أي عقدة تقدر تحل مكان التانية في أي لحظة.
2. **عقدة قيادة واحدة**: polling تليجرام لا يحتمل أكثر من مستقبل واحد (409) — فالقيادة تُمنح بعقد إيجار ذري على القاعدة.
3. **Offline-first للالتقاط**: لو مفيش إنترنت/سحابة AI، الالتقاط والتصنيف والقواعد يشتغلوا محليًا (v1 brain) — السحابة تُحسّن مش تُعطّل.
4. **عزل السياقات**: الورشة (ws_*) والمحل (retail_*) وحدات منفصلة تمامًا — لا جدول مشترك، لا استعلام متشابك.
5. **الصدق الهندسي**: كل فشل يُسجّل (`sync_log`/اللوج) — لا نتيجة مُختلقة.

---

## 4. Requirement → Design Mapping

### R1 — Unified Ecosystem Integration (Retail & Workshop)
- **Retail**: `retail.py` يسحب **لقطة** من قاعدة POS (SQLite, mode=ro) على الجهاز اللي عنده القاعدة (جهاز الورشة) → تُخزن في `retail_snapshots` + `retail_inventory`. البوت والواجهة تعرض آخر لقطة فقط — لا استعلام حي على قاعدة المحل. **قاعدة POS لا تُكتب مطلقًا.**
- **الوكلاء (مروة وكوكو وبيبو وفارس وسلمى وحكيم وراصد…)**: كل وكيل يقدر يبلّغ تقرير عبر `POST /api/agents/report` بتروك `X-NB2-Token`. التقارير تتخزن في `agent_reports` وخطورة `critical` تُرسل فورًا للمالك عبر outbox.
- **Workshop (النجار برنت)**: موديول مستقل كامل البنية: `ws_customers`, `ws_jobs` (pipeline: quote→confirmed→design→production→finishing→ready→delivered/cancelled), `ws_materials` + مخزون، `ws_job_materials`, لوج كامل. صفحة `/workshop` وقائمة بوت خاصة — **صفر تشابك مع الـRetail**.

### R2 — Telegram Bot Localization & Personalization
- بوت مستقل **@Afkary22Bot** بتروكن من `.env` الجذر.
- **Authorization Middleware صارم**: كل update (message/callback/edited) يُفحص `from.id == OWNER_TELEGRAM_ID` (561770354). غير المالك → تجاهل صامت + تسجيل. لا استجابة من أي نوع.
- `/start` → لوحة Inline: 🏪 نظام المحل | 🔧 ورشة النجار برنت | 🧠 الذاكرة الثانية | 📜 خزنة البرومبتات | 📊 حالة المنظومة.
- التخصيص: عربي مصري، شخصية «منظّم حياة وأعمال»، مواعيد الصلاة مدمجة، نفس أوامر v1 («تم 5»، «أجّل»، «المستحق»…) للانتقال السلس.

### R3 — Frontend UI Revamp & Cloud AI Provider Management
- واجهة منظمة: `base.html` بشريط تنقل + 4 صفحات: Dashboard / **Providers** / Workshop / Vault، بنفس الهوية البصرية الملونة RTL.
- **صفحة «مزودو الـAI»** (`/providers`): إضافة مزود (اسم + base_url + مفتاح)، **اكتشاف النماذج تلقائيًا** (`GET {base_url}/models`)، اختبار مفتاح برسالة حقيقية، تحديد **النموذج الافتراضي**، تفعيل/إيقاف، مؤشر صحة آخر فحص. المفاتيح تُخزن **مشفرة Fernet** ولا تُعرض إلا مموّهة.
- الهدف: «النوتبوك يعمل بالسحابة حتى لو الموديلات/الأجهزة المحلية offline» — كل نداءات AI تمر على `providers.chat()` الذي يختار المزود الافتراضي ديناميكيًا.

### R4 — Dual-Node High Availability
- كل عقدة تشغّل `scripts/start_node.py`: نبضة كل 15 ثانية في `nodes`، ومحاولة تجديد/أخذ `leader_lease` (TTL 45 ثانية، بوقت **السيرفر** لمنع انحراف ساعات الجهازين).
- **القائد فقط** يشغّل: polling البوت، المهام المجدولة، معالجة outbox. العقدة الأخرى hot-standby جاهزة.
- Failover: لو السيرفس برو انطفى، الورشة تلتقط القيادة خلال ≤ 45 ثانية — **البوت لا يفصل**. لو الاتنين شغالين: القيادة للسابق، والثاني غطاء فوري (والويب شغال على الاتنين).
- `scripts/health_sync.py`: فحص يدوي/مجدول (صحة العقد + القاعدة + آخر لقطة Retail + تشغيل دورة التذكيرات مرة).

### R5 — Proactive Second Brain
- **AI Router** (`ai_router.py`): نص/صوت ← تصنيف إلى `task / idea / home_item / workshop_need / note / reminder / program_idea`. الطبقة الأولى قواعد v1 (بلا إنترنت)، والثانية تحسين سحابي (JSON محكم low-temperature) يُستخدم عند توفر مزود.
- **Project Radar & Timeboxing** (`proactive.py`): ملخص صباح (08:00 قابل للتعديل) يشمل الصلاة+المهام+الرادار+المحل؛ **رادار المشاريع الراكدة** (مافيش حركة > N يوم → تنبيه يومي مُزال التكرار)؛ **بومودورو** (25/50 دقيقة) بإشعار نهاية.
- **Prompt Vault** (`prompt_vault.py`): حفظ/تصنيف/وسم + **بحث دلالي pgvector** (`embedding <=> query`) مع بديل بحث كلمات (pg_trgm) لو مفيش خدمة embeddings — البحث يعمل دائمًا.

---

## 5. Data Architecture

| الطبقة | التقنية | الدور |
|---|---|---|
| العقل المشترك | Supabase PostgreSQL 15+ | كل جداول v2 (المخطط الكامل أدناه) |
| البحث الدلالي | pgvector (`vector(1536)`, ivfflat cosine) | خزنة البرومبتات |
| البحث النصي | pg_trgm + GIN | fallback عربي للخزنة والنوتات |
| POS المحل | SQLite الموجود كما هو | **قراءة فقط** — لقطات دورية/يدوية |
| v1 القديم | notebook.db (SQLite) | لا يُمس أثناء الترحيل — v2 يعمل بجواره |

**المخطط (db/schema_pgvector.sql)** — مجمّعات:
- `settings` — إعدادات kv (وقت الملخص، المزود الافتراضي…).
- `ai_providers` + `ai_models` — سجل المزودين والنماذج المكتشفة.
- `vault_prompts` (+embedding) — خزنة البرومبتات.
- `captures` + `capture_events` — نوتات/مهام/أفكار/تذكيرات (امتداد notes في v1 بأنواع home_item/workshop_need + `routed_by`).
- `projects` + `project_log` — مشاريع + رادار الركود.
- `home_lists` + `home_items` — قوائم البيت.
- `ws_*` — موديول الورشة المستقل (عملاء/مهام/خامات/مخزون/لوج).
- `retail_snapshots` + `retail_inventory` — مرآة قراءة للمحل.
- `agent_reports` + `sync_log` — تقارير الوكلاء وسجل المزامنة.
- `nodes` + `leader_lease` + `bot_state` — HA (نبضات، إيجار القيادة، offset البوت المشترك بين العقدتين).
- `cron_runs` + `outbox` + `pomodoros` — الاستباقية (منع التكرار، صندوق إرسال، تايمبوكسينج).

---

## 6. Security Model

1. **Owner-only bot**: middleware على كل نوع update؛ غير المالك = صمت + سطر لوج.
2. **Mفاتح مشفرة**: Fernet بمفتاح `AI_VAULT_MASTER_KEY` من .env — المفتاح يظهر مموّهًا (`sk-…ab12`) فقط.
3. **Ingest tokens**: تقارير الوكلاء تتطلب `X-NB2-Token: $NB2_INGEST_TOKEN`.
4. **لا أسرار في Git**: `.env` في `.gitignore` لكل مشروع (قاعدة المعمل).
5. **SQL دائمًا parameterized** (psycopg2 placeholders) — لا تركيب نصوص.
6. توكن @Afkary22Bot وصل في نص محادثة — **يُنصح بتدويره من BotFather** بعد الاعتماد، ثم تحديث `.env` الجذر فقط (لا مكان آخر يقرأه).

---

## 7. AI Provider Layer (تفصيل R3)

```
UI /providers ──▶ web.py ──▶ providers.py ──▶ ai_providers/ai_models (PG, مشفر)
                                   │
                                   ├─ discover(): GET {base_url}/models  (OpenAI-compatible)
                                   ├─ test():    POST {base_url}/chat/completions — «قل: تم»
                                   ├─ chat():    النموذج الافتراضي الحالي (settings)
                                   └─ embed():   POST {base_url}/embeddings (للفولت — اختياري)
```
- كل المزودين OpenAI-compatible: DeepSeek (`https://api.deepseek.com/v1`)، OpenAI، Groq (`…/openai/v1`)، Dahl (من .env) — presets جاهزة في الصفحة.
- **التبديل الديناميكي**: تغيير الافتراضي = سطر settings — يأثر فورًا على AI Router والملخصات بدون إعادة تشغيل.
- فشل مزود → سجل صحي + fallback تلقائي لأي مزود نشط آخر (round-robin بسيط) ثم للقواعد المحلية.

## 8. Dual-Node HA (تفصيل R4)

```
every 15s on each node:
  heartbeat: INSERT INTO nodes ... ON CONFLICT UPDATE last_seen=now()
  lease:     INSERT INTO leader_lease ... ON CONFLICT DO UPDATE ...
             WHERE expires_at < now() OR holder = me
  → row returned? I am leader (start bot/crons if not started)
  → no row?   I am standby (stop bot polling if it was mine)
```
- TTL 45s بوقت السيرفر؛ offset البوت محفوظ في `bot_state` (PG) — العقدة الوارثة تكمل من آخر رسالة بلا فقد ولا تكرار.
- الويب (8110) يعمل على العقدتين — المالك يفتح أقرب جهاز.
- حماية 409: قبل الـpolling يُفحص webhook مسجل؟ → رفض صادق مع السبب (نفس عقل v1).

## 9. Proactive Engine (تفصيل R5)

| الوظيفة | التوقيت | منع التكرار |
|---|---|---|
| تذكيرات المستحق | كل دقيقة (tick) | `remind_at` يتقدّم/يُغلق بعد الإرسال |
| الملخص الصباحي | نافذة 08:00–09:00 | `cron_runs(job='morning', run_date=today)` |
| رادار المشاريع | مع الملخص + دورة الظهر | `cron_runs(job='radar', run_date)` |
| بومودورو | جدولة لكل جلسة | صف `pomodoros` بحالة |
| تقارير critical من الوكلاء | فوري عند الاستقبال | outbox `dedupe_key` |

## 10. Bot UX (قوائم وأوامر)

```
/start →
 🏪 نظام المحل      🔧 ورشة النجار برنت
 🧠 الذاكرة الثانية   📜 خزنة البرومبتات
 📊 حالة المنظومة
```
- **المحل**: آخر ملخص مالي / الطلبات المفتوحة / مخزون ناقص / آخر تقارير الوكلاء.
- **الورشة**: مهام قيد التنفيذ / إضافة مهمة (سطر حر: عميل | وصف | مبلغ | ميعاد) / الخامات / أوامر خامات.
- **الذاكرة**: مستحق الآن / قائمتي / ابدأ بومودورو / إضافة نوت.
- **الخزنة**: أحدث 5 برومبتات / بحث (أرسل كلمة) / إضافة (عنوان ثم النص).
- نص حر = التقاط فوري عبر AI Router بتأكيد عربي كامل؛ الصوت يُحفظ ويعلن أن التفريغ قادم (P2).

## 11. File Map

```
projects/notebook-v2/
├─ ARCHITECTURE.md  README.md  .env.example  requirements.txt  .gitignore
├─ db/schema_pgvector.sql  db/migrate.py
├─ nb/ (الحزمة)
│  ├─ config.py db.py secrets.py providers.py ai_router.py prompt_vault.py
│  ├─ workshop.py retail.py proactive.py ha.py prayer.py
│  ├─ bot.py web.py
│  ├─ templates/ base.html index.html providers.html workshop.html vault.html
│  └─ static/style.css
└─ scripts/start_node.py  scripts/health_sync.py   (+ run.bat, install_services.ps1)
```

## 12. Deployment & Migration Plan

- **P0 (منجز في هذا التسليم)**: المخطط كامل + العقدة الواحدة تعمل (ويب/بوت/HA/استباقية) + صفحة المزودين + موديول الورشة والفولت.
- **P1 (تجربة المالك)**: تشغيل على السيرفس برو أولًا؛ اعتماد المزودين بمفاتيح حقيقية من صفحة `/providers`؛ إضافة مشروعين حقيقيين ورصدهم.
- **P2 (عقدتان + Retail)**: تشغيل على جهاز الورشة + ضبط `NB2_POS_DB_PATH` → سحب اللقطات من هناك؛ اختبار قتل القائد والتقاط القيادة؛ تفعيل تفريغ الصوت (Whisper محلي على جهاز الورشة).
- **P3 (cutover v1)**: تحويل الخدمات المجدولة إلى v2، إيقاف جسر v1 أو إبقاء @Marwty_bot كقناة احتياطية، أرشفة notebook.db بعد تصدير/ترحيل النوتات المفتوحة (سكربت ترحيل بسيط: SQLite → PG).
- **P4 (توسّع)**: أوتوميشن الوكلاء عبر CrewAI داخل المعمل يبلّغ تقاريره مباشرة إلى `/api/agents/report`؛ WebApp تليجرام مصغّر للواجهة؛ مزامنة انتقالية عند غياب الإنترنت (outbox محلي).

## 13. Key Decisions (ADR مختصر)

1. **Supabase بدل قاعدة محلية مشتركة** — موجود أصلًا في `.env` الجذر، يدعم pgvector، ويلغي مسألة مزامنة ملفات بين الجهازين. Tradeoff: يحتاج إنترنت للعقل المشترك — عولج بـ offline-first للالتقاط (قواعد v1 محليًا) وQUEUE نصي بسيط يعاد إرساله (P2).
2. **Lease على PG بدل advisory locks** — يعمل عبر Supavisor pooler بلا مشاكل جلسات، ويعطي مراقبة بشرية (جدول مقروء).
3. **urllib بدل python-telegram-bot** — عقل v1: صفر تبعيات تشغيلية للبوت؛ القوائم والردود المرقمة تُبنى يدويًا (تم في `nb/bot.py`).
4. **Fernet بدل نص صريح** — توازن أمان/بساطة بمكتبة واحدة `cryptography` موجودة في requirements.
5. **vector(1536)** — الأبعاد الأشهر لمزودي embeddings؛ عمود واحد + `embed_model` اسم يسمح بالترحيل لاحقًا (إعادة تضمين دفعة عند تغيير الموديل).
