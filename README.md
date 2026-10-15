# Marwa-Bot 🧠 — عقل مروة لمنظومة النجار برنت

المستودع الرسمي المعتمد لعقل **مروة** (الوكيل الرقمي لورشة النجار برنت) وكافة الوكلاء وأدوات المنظومة.
عقدتان تعملان بالكامل من نفس هذا الكود: **الورشة** (الجهاز الرئيسي) و**اللابتوب** (النسخة المتزامنة) — وكل عقدة تعمل حتى لو الجهاز الآخر مغلق تماماً.

```
   ورشة WORKSHOP                          لابتوب LAPTOP
   pos_data.db (الحي)                     pos_data.db (مرآة مبنية من السحابة)
        │                                       │
        │ cloud/supabase_sync.py --push-once    │ tools/laptop_sync.py --pull-all
        ▼                                       ▲
   ┌───────────────── Supabase ──────────────────┐
   │  7 جداول مرآة + system_brain_sync (العقل)  │
   └────────────────────────────────────────────┘
        │                                       ▲
        │ --push-brain (ذاكرة + قواعد + env)     │ --pull-brain
        └──────────── GitHub: Marwa-Bot ────────┘ (git pull/push)
```

## محتويات المستودع

| المسار | المحتوى |
|---|---|
| `AGENT.md` / `RULES.md` / `STATUS.md` | ميثاق الوكيل + قواعد المحل + حالة النظام |
| `memory/` | العقل الهندسي: سجل القرارات، خارطة الطريق، الدروس، التفضيلات، التقارير |
| `orchestrator/` | المنسق العام + **الوكلاء الثمانية** (data_healer, crm, cfo, marketing, system_worker, coder, meta_agent, manufacturing) |
| `cloud/` | محرك المزامنة Hermes + محرك الترحيلات المزدوج + الويب هوك + `migrations/` |
| `tools/` | **`laptop_sync.py`** (مزامنة العقدتين) + أدوات الإكسيل (تصدير/استيراد الكتالوج) |
| `scripts/` | النسخ الاحتياطي + حارس التطابق parity_watchdog |
| `mcp/` | خوادم pos-reader (قراءة فقط) و pos-writer (كتابة محكومة) |
| `skills/` | مهارات مروة (التقرير اليومي، حسم المتأخر، الاستكشاف) |
| `pos_system/` | كود منظومة النجار برنت كاملة (الواجهة، المحرك المالي، التليجرام، المزامنات، طبقة التشغيل) |
| `.agents/skills/` | مهارات Supabase الرسمية المثبتة |

## تفعيل العقدة الجديدة (اللابتوب) — خطوات يدوية

1. `git clone https://github.com/mahmoudelnagarprint-web/Marwa-Bot.git`
2. انسخ `.env.example` → `.env` واملأ القيم الحقيقية، وعلى رأسها `NODE_ID="LAPTOP"`
   (القيم الحقيقية عند المالك في ملف **LAPTOP_SECRET_KIT.md المحلي** — لا يُرفع للمستودع أبداً)
3. `python -m venv .venv` ثم `.venv\Scripts\pip install -r requirements.txt`
4. `python tools/laptop_sync.py --pull-all` — يبني `pos_data.db` محلياً من كل جداول السحابة + ينزّل ملفات الذاكرة
5. افتح DSH في مجلد المستودع… ومروة جاهزة بكامل ذاكرتها.

*(هناك برومبت تفعيل كامل بضغطة واحدة داخل `LAPTOP_SECRET_KIT.md`.)*

## أوامر المزامنة

| الأمر | الوظيفة |
|---|---|
| `python tools/laptop_sync.py --pull-all` | اسحب كل البيانات + الذاكرة ← ابنِ/حدّث `pos_data.db` والملفات محلياً |
| `python tools/laptop_sync.py --push-brain` | ارفع تعديلات الذاكرة/القواعد للخزينة السحابية + git push (الورشة تلتقطها عند الفتح) |
| `python tools/laptop_sync.py --pull-brain` | اسحب تحديثات الذاكرة فقط (التقاط سريع) |
| `python tools/laptop_sync.py --restore-env` | استرجاع `.env` من الخزينة السحابية (جهاز جديد) |
| `python tools/laptop_sync.py --status` | حالة العقدة: هوية + صفوف المرآة + مفاتيح الخزينة وأعمارها |

## خزينة العقل السحابية (`system_brain_sync` — ترحيل 003)

| المفتاح | المحتوى |
|---|---|
| `status_md` / `decisions_log_md` / `roadmap_md` | ملفات الحالة والقرارات وخارطة الطريق |
| `learned_rules` / `owner_preferences_md` / `lessons_md` / `agent_charter_md` | القواعد المكتسبة وتفضيلات العمل والدروس والميثاق |
| `env_backup` | نسخة احتياطية من `.env` (الاسترجاع يعيد ضبط NODE_ID تلقائياً) |
| `local_state_json` | حالة الشيفت المفتوح + settings (لتطابق الأرقام المالية بين العقدتين) |
| `brain_manifest` | من دفع آخر تحديث ومتى |

الجدول **مؤمّن بـRLS بدون سياسات** = لا يقرؤه ولا يكتبه إلا المفتاح السري.

## قواعد أمان ثابتة

- `.env` و`LAPTOP_SECRET_KIT.md` وكل قواعد البيانات والنسخ الاحتياطية **ممنوعة من المستودع** (`.gitignore`).
- **على اللابتوب: لا تشغّل `cloud/supabase_sync.py --push-once/--daemon` أبداً** — البيانات الرسمية تُرفع من الورشة فقط، وإلا استبدلت نسخة قديمة بالأحدث.
- الكتابة على بيانات المنظومة (طلبات/دفعات/عملاء) تتم عبر مسار الورشة الرسمي فقط (commands queue → دوال database.py).
- بوت التليجرام له مستقبِل واحد (الويب هوك السحابي) — لا تشغّل Poller ثانٍ على اللابتوب بنفس التوكن (تعارض 409).

## المسار السريع (للمطور)

```bash
python tools/laptop_sync.py --status          # فين واقف؟
python tools/laptop_sync.py --pull-all        # نسخة كاملة محلية
python cloud/schema_migrator.py --all         # تطبيق ترحيلات جديدة (محلي + سحابي)
```
