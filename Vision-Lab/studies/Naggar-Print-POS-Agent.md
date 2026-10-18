# 🏗️ ملخص معماري: Naggar Print POS Agent (Marwa-Bot)

> دراسة معمارية بقلم وكيل «فيجن» لمساحة الوكيل «مروة» (ورشة النجار برنت).
> قراءة فقط — لم يُعدَّل أي ملف مُدرَس. الجذر: `G:\ai\Naggar Print POS Agent`
> الحالة: **مكتملة** — **الملفات المقروءة: 15/20** (داخل الميزانية) + جرد أسماء وأدلة grep موثقة.

---

## 1) الغرض
مساحة وكيل «مروة» (Marwa-Bot) لورشة «النجار برنت»: منظومة Python متعددة الأجزاء — نظام نقاط بيع كامل (`pos_system`) + نوتبوك ذكية شخصية (`notebook`) + أوركسترا وكلاء (`orchestrator`) + مرآة مزامنة بين جهازين (**WORKSHOP ⬌ LAPTOP**) بهوية `NODE_ID` من `.env`، فوق قاعدة محلية `pos_data.db` وسحابة Supabase وقناتي تليجرام.
- **الدليل**: `requirements.txt` سطر 1: «Marwa-Bot laptop kit — الأساسيات لتشغيل مروة والعقدة على أي جهاز»؛ و`tools/laptop_sync.py` سطر 4: «Marwa Laptop Sync — العقدتان متزامنتان دائماً (الورشة + اللابتوب)».

## 2) نقاط الدخول + المهام المجدولة
**نقاط دخول مكتشفة:**
- `pos_system/backend.py` — خلفية Eel لواجهة سطح المكتب (تستدعي `init_db()` عند الاستيراد).
- `pos_system/mobile_local_api_server.py` — خادم FastAPI محلي «Elnagar POS Local Mobile API» v1.0 للجوال.
- `pos_system/telegram_bot/bot.py` — بوت POS «Smart Arabic POS Assistant» (ConversationHandler ذكي).
- `pos_system/firebase_importer_loop.py` — حلقة استيراد Firebase (كل 10 ث).
- `pos_system/desktop_sidebar.py` — شريط أوامر جانبي CustomTkinter «Command Center Sidebar v2.0».
- `notebook/app.py` (Flask على 8100، وAPI التقاط: `POST /api/capture`) + `notebook/telegram_bridge.py --watch` + `notebook/automation.py --morning|--evening|--cycle|--test`.
- `tools/laptop_sync.py` (--pull-all / --pull-brain / --push-brain / --restore-env / --status / --no-git) و`scripts/git_autosync.py --loop`.

**مهام Windows المجدولة MarwaBot_\*** (دليل: `notebook/install_services.ps1` سطر 23-27، `scripts/install_git_autosync_task.ps1` سطر 5-20، `tools/safe_pull.py` سطر 4، و`notebook/README.md` سطر 58-60):
| المهمة | السكربت | الدور/الإيقاع |
|---|---|---|
| MarwaBot_Notebook | notebook/app.py --port 8100 | واجهة الويب — دائمة (keep-alive كل 5 د) |
| MarwaBot_NotebookBridge | notebook/telegram_bridge.py --watch | استقبال تليجرام + تذكيرات — دائمة |
| MarwaBot_NotebookMorning | automation.py --morning | جدول الصباح (صلاة+مهام) على تليجرام |
| MarwaBot_NotebookEvening | automation.py --evening | مراجعة المساء + ترحيل المهام |
| MarwaBot_NotebookCycle | automation.py --cycle | فحص كل 30 د: تذكيرات مستحقة + تنبيه صلاة قادمة |
| MarwaBot_GitSync (+_Logon) | scripts/git_autosync.py | مزامنة GitHub كل 15 د + عند الدخول |
| MarwaBot_AutoPull | tools/safe_pull.py | سحب آمن مجدول |

## 3) الهيكل العام
```
Naggar Print POS Agent/
├── pos_system/        # نظام POS الكامل (Eel + FastAPI + بوت تليجرام + مستوردات مزامنة) ~90 ملفًا
│   ├── telegram_bot/  # بوت الطلبات الذكي (bot.py 2594 سطر + config + openrouter + firebase_client)
│   ├── backend.py / main.py / app.py / database.py(130KB) / desktop_sidebar.py(41KB)
│   ├── firebase_importer(_loop).py, android_importer.py, telegram_importer.py  ← مستوردات مع نسخ احتياطي لكل دورة
│   ├── sheets/google: sync_pos_to_sheet, google_sheet_realtime_sync, sheets_queue(41KB)
│   └── web/ (index.html 286KB) + sidepanel كروم + ui/
├── notebook/          # النوتبوك الذكية: app(Flask)+brain+store+scheduler+prayer+automation+telegram_bridge + notebook.db
├── orchestrator/      # أوركسترا وكلاء: core/router/base/steering_bar + squad/{bibo,fares,hakim,koko,marwa,rased,salma,sasa}
│   └── squad: cfo, crm, data_healer, manufacturing_agent, marketing, meta_agent, system_worker (بنسخ .bak)
├── tools/             # laptop_sync.py (مرآة العقدتين) + safe_pull + استيراد/تصدير Excel
├── mcp/               # pos-reader (server.py 49.8KB) + pos-writer (server.py 16.9KB)
├── scripts/           # git_autosync.py + مثبتات المهام المجدولة
├── memory/            # ذاكرة قرارات المشروع (decisions_log, owner_preferences...)
├── cloud/  skills/  backup/  exports/  logs/
├── Vision-Lab/        # مختبر وكيل «فيجن» (هذا المسار): AGENT/README/RULES/SQUAD+STATUS + ai_templates + config(data_source) + tools(inventory/verify) + studies(13 دراسة) + projects
└── (جذر) pos_data.db + STATUS.md + RULES.md + AGENT.md + ملفات حالة (SASA/SALMA/BIBO) + fix_*.py
```

## 4) الوحدات الرئيسية
| وحدة | الدور | الحالة |
|---|---|---|
| `pos_system/backend.py` | طبقة Eel بين واجهة JS وقاعدة SQLite: `init_db()`، إعدادات Google Sheet، اختبار اتصال، تسجيل أعطال في `backend_crash.log` | ✅ مقروء (1-100/927) |
| `pos_system/telegram_bot/bot.py` | بوت POS: محادثة طلب ذكية من 8 مراحل + أسماء أوامر عربية + AI (gpt-4o-mini/OpenRouter) لتصنيف النية واستخراج طلب JSON | ✅ مقروء (1-100/2594) |
| `pos_system/mobile_local_api_server.py` | FastAPI محلي للموبايل: CORS مفتوح، مفتاح API اختياري، استخراج طلبات بالذكاء الاصطناعي، إشعارات Toast | ✅ مقروء (1-80/663) |
| `pos_system/firebase_importer_loop.py` | حلقة لا نهائية: heartbeat كل 60ث إلى Firestore، استيراد كل 10ث، أخطاء إلى مجموعة `errors` | ✅ مقروء (42/42) |
| `pos_system/desktop_sidebar.py` | شريط أوامر جانبي سطح مكتب (CustomTkinter، داكن زجاجي، إخفاء من شريط المهام بـWin32) — يستورد `database` + `file_ops_engine` | ✅ مقروء (1-60/755) |
| `notebook/app.py` | واجهة ويب Flask للنوتبوك: التقاط ذكي `brain.analyze→store.add_note`، فلاتر، عرض المستحق/المتأخر | ✅ مقروء (1-80/263) |
| `notebook/telegram_bridge.py` | جسر تليجرام بلا مكتبات خارجية (urllib long-polling): أمان بالمحادثات المصرّح بها، رفض تعارض 409، offset في `data/telegram_state.json`، تذكيرات + ملخص 08:00 | ✅ مقروء (1-60/616) |
| `notebook/store.py` | طبقة تخزين SQLite **معزولة تمامًا** عن pos_data.db (`notebook/data/notebook.db`) — 12+ تصنيفًا افتراضيًا | ✅ مقروء (1-30/496) |
| `notebook/brain.py` | «العقل» قواعدي **بلا إنترنت وبلا مفتاح**: تطبيع عربي، نوع (نوت/مهمة/تذكير/فكرة/فكرة برنامج)، تصنيف/أولوية/ميعاد، سؤال توضيحي واحد، لا يخترع | ✅ مقروء (1-30/499) |
| `notebook/scheduler.py` | «منظم الحياة اليومية — الشخصية الاستباقية»: جدول اليوم (محل + شخصي + مواقيت صلاة)، ترحيل المهام غير العاجلة، اقتراح خطوات لأفكار البرامج، مراجعة مساء، تحذير نوم 22:30/23:00 | ✅ مقروء (1-30/304) |
| `notebook/prayer.py` | مواقيت الصلاة حسابًا فلكيًا **بلا إنترنت** (PrayTimes، منهج مصرية: فجر 19.5°/عشاء 17.5°) بإحداثيات الخارجة (25.4478, 30.5463) | ✅ مقروء (1-30/237) |
| `notebook/automation.py` | مشغّل المهام المجدولة: `--morning` جدول الصباح، `--evening` مراجعة وترحيل، `--cycle` فحص كل 30 د — يستخدم جسر الإرسال نفسه (توكن من .env الجذر) لتفادي التعارض | ✅ مقروء (1-30/158) |
| `orchestrator/` | أوركسترا وكلاء (جرد أسماء فقط): `core/router/base/steering_bar` + `squad/` بـ8 وكلاء (bibo, fares, hakim, koko, **marwa**, rased, salma, sasa) — كل وكيل بـAGENT_PROFILE.md + CHAT_BOOTSTRAP_PROMPT.md؛ و`agents/` بنفس الطاقم (cfo, coder, crm, data_healer, manufacturing_agent, marketing, meta_agent, system_worker + system_apps.json) بنسخ `.bak-2026-10-18-marwa-task2` | 🏷️ جرد أسماء |
| `tools/laptop_sync.py` | **قلب المزامنة**: خزينة سحابية `system_brain_sync` (Supabase، migration 003) نقطة التقاء العقدتين؛ `--pull-all` يبني مرآة pos_data.db من 7 جداول (clients/products/orders/order_items/transactions/raw_materials/product_recipes) ولا يلمس قاعدة الورشة الحية؛ `--push-brain` يرفع الذاكرة+.env؛ `--restore-env` يعيد بناء .env بـNODE_ID=LAPTOP تلقائيًا | 📖+🏷️ (1-40/578) |
| `mcp/pos-reader` و`mcp/pos-writer` | خوادم MCP لقراءة/كتابة بيانات POS (server.py 49.8KB / 16.9KB) — بوابة الوكلاء إلى القاعدة | 🏷️ جرد أسماء |
| `Vision-Lab/` | مختبر وكيل «فيجن»: دراسات معمارية (13 ملفًا في studies/ بفهرس STUDY_INDEX.md) + قوالب crewai + أدوات جرد/تحقق + سجل قرارات | 🏷️ جرد سطحي |

## 5) المكتبات
من `requirements.txt` (حزمة اللابتوب): `supabase>=2.32` (laptop_sync + المرآة — REST فقط)، `requests`، `openpyxl` (كتالوج إكسيل)، `psycopg2-binary` (cloud/schema_migrator.py)، `mss` (لقطات system_worker)، `flask` (هوك سحابي اختياري + واجهة النوتبوك).
مكتشفة من الكود: `eel` (backend)، `python-telegram-bot` (bot.py)، `fastapi/uvicorn/openai` (mobile API)، `firebase_admin` (المستوردات)، `customtkinter/tkinter/PIL/pyperclip/tkinterdnd2` (desktop_sidebar — اختيارية بحماية ImportError عدا customtkinter)، `urllib` فقط للجسر («بلا مكتبات خارجية»)، `math` لحساب فلكي في prayer.py («بلا إنترنت»).
المتطلبات الكاملة للـPOS في `pos_system/requirements_full.txt`.

## 6) مخازن البيانات (محلي + Supabase)
- **محلي**: `pos_data.db` (SQLite، 84KB + WAL) بجذر المشروع — المرآة المحلية للـPOS؛ `notebook/data/notebook.db` (40KB) للنوتبوك — **فصل صريح**: «منفصلة تمامًا عن قاعدة البرنامج — لا كتابة على البرنامج أبدًا» (store.py سطر 4-5، README سطر 43)؛ `notebook/data/telegram_state.json` لـoffset + قفل single-instance.
- **Supabase**: جدول المرآة (7 جداول: clients, products, orders, order_items, transactions, raw_materials, product_recipes) + خزينة العقل `system_brain_sync` (migration 003) بعشرة مفاتيح (status_md/decisions_log_md/roadmap_md/learned_rules/owner_preferences_md/lessons_md/agent_charter_md/env_backup/local_state_json/brain_manifest) — دليل: laptop_sync.py سطر 6-7, 17-19 + `memory/decisions_log.md` سطر 147.
- **Firebase/Firestore**: قوائم استيراد + `importer_heartbeats/main_loop` + `errors`.
- **GitHub** (`Marwa-Bot` مستودع خاص): تزامن الكود + ملفات الذاكرة بين العقدتين.
- **قواعد التزامن** (دليل: laptop_sync.py سطر 6-13 + decisions_log سطر 151): الكتابة من الورشة فقط؛ اللابتوب `--push-brain` فقط؛ مستقبِل تليجرام واحد (webhook سحابي) — منع Poller ثانٍ (409)؛ `*.db` و`backup/` خارج Git.

## 7) التكاملات
1. **تليجرام ×2**: بوت POS (محادثة طلبات ذكية عربية، webhook سحابي) + بوت مروة **@Marwty_bot** عبر notebook bridge (long-polling urllib، محادثات مصرّح بها من .env: OWNER_TELEGRAM_ID / ALLOWED_CHAT_IDS).
2. **Supabase**: مرآة القاعدة + خزينة `system_brain_sync` (psycopg2 للترحيلات المباشرة في cloud/schema_migrator.py).
3. **OpenRouter** (gpt-4o-mini): تصنيف نية، استخراج طلب JSON، مساعد عام (bot.py + mobile API).
4. **Firebase**: استيراد طلبات + نبضات + سجل أخطاء.
5. **Google Sheets/Drive**: مزامنة فورية ونسخ احتياطي (google_sheet_realtime_sync.py, backup_google_sheet.py).
6. **GitHub**: مزامنة تلقائية كل 15 دقيقة (MarwaBot_GitSync).
7. **نوتبوك**: قناة @Marwty_bot (تقاط من أي مكان + تذكير قبل الميعاد بساعة + ملخص 08:00) + API محلي `POST /api/capture` من أي مصدر.

## 8) تقييم الصحة (بدليل)
- 🚨 **حرج — تراكم نسخ DB بلا تنظيف**: `firebase_importer_loop.py` سطر 8 `POLL_INTERVAL = 10` (ثانية) يستدعي `run_import_cycle` كل دورة؛ و`firebase_importer.py` سطر 260 ينادي `backup_db()`، وسطر 14-22: ينسخ القاعدة كاملة بـ`shutil.copy2` إلى `pos_system/Backups/pos_data_backup_fb_importer_<timestamp>.db` — **اسم جديد بطابع زمني كل دورة ⇒ نسخة جديدة كل ~10-12 ثانية**، وgrep لا يُظهر أي دالة حذف/تنظيف في الملف. نفس النمط في `android_importer.py` سطر 154-158 (مجلد `android_importer_<stamp>` لكل تشغيل) و`telegram_importer.py` سطر 31 — ثلاثة مستوردات تنتسخ بلا حد. أثر إضافي: ملف جذر فارغ `_last_backup.txt`.
- 🔴 **خطر أمني — سر مضمن في الكود**: `mobile_local_api_server.py` سطر 29-32 يضع **مفتاح OpenRouter كامل كقيمة افتراضية** داخل الكود (قيمة لا تُطبع هنا) — التزامن عبر git يعرّضها للتسريب. كما أن `verify_api_key` سطر 40-43: لو `LOCAL_MOBILE_API_KEY` فارغ فالتحقق يمر للجميع، مع CORS مفتوح `*` (سطر 21-26) — أي جهاز في الشبكة المحلية يستطيع النداء. ومقابل ذلك: واجهة النوتبوك مكشوفة أيضًا على LAN (README سطر 12) دون توثيق ظاهر للـAPI.
- 🟠 **مكرر/غير نظيف**: `orchestrator/squad/` و`orchestrator/agents/` يحملان نسخ `.bak-2026-10-18-marwa-task2` جانب الأصل — تعديل مباشر بلا Git (متناقض مع سياسة GitSync) + سكربتات ترقيع بجذر المشروع (`fix_balance.py`, `fix_balance2.py`, `fix_correct_db.py`).
- 🟡 **حجم غير صحي**: `pos_system/database.py` (130KB)، `bot.py` (2594 سطرًا)، `web/index.html` (286KB)، `sheets_queue.py` (41KB) — ملفات عملاقة.
- 🟢 **جيد — عزل النوتبوك**: store.py سطر 4 «منفصلة تمامًا… لا كتابة على البرنامج أبدًا» + استبعاد *.db من Git (README سطر 44).
- 🟢 **جيد — قرارات بلا اعتماديات**: عقل قواعدي بلا إنترنت (brain.py سطر 7)، صلاة حسابية بلا إنترنت (prayer.py سطر 7)، جسر تليجرام بلا مكتبات خارجية (telegram_bridge سطر 4) — قرارات تقلّل الاعتماديات وتتحمل انقطاع الشبكة.
- 🟢 **جيد**: حاجز أسرار في `git_autosync.py`، قفل single-instance للجسر، `--restore-env` يفرض NODE_ID=LAPTOP على جهاز جديد ويرفض المسح بلا `--force` (laptop_sync.py سطر 26-28).

## 9) خريطة دخول للتطوير
- **لإصلاح تراكم النسخ** (الأولوية 1): `pos_system/firebase_importer.py` — دالة `backup_db()` سطر 16-22 + استدعاؤها سطر 260 (حذف النسخ الأقدم من N أيام أو التخفيف لكل ساعة) وليس الـloop.
- **للـPOS**: تشغيل `pos_system/run_app.bat` → backend.py (Eel) + database.py؛ بوت الطلبات `pos_system/telegram_bot/bot.py` (+ config/openrouter_client).
- **للموبايل**: `pos_system/mobile_local_api_server.py` (أمنه أولًا: مفتاح مضمن سطر 29-32 + تحقق اختياري سطر 40-43).
- **للمزامنة بين الأجهزة**: `tools/laptop_sync.py` + NODE_ID في `.env` + جدول `system_brain_sync` (migration 003).
- **للنوتبوك**: العقل `brain.py` (قواعد/مفردات) ← التخزين `store.py` ← واجهة `app.py` ← القناة `telegram_bridge.py` ← التشغيل الآلي `automation.py` ← الخدمات `install_services.ps1`.
- **للـMCP**: `mcp/pos-reader/server.py` (قراءة) و`mcp/pos-writer/server.py` (كتابة) — بوابة الوكلاء للقاعدة.
- **لهذه الدراسة**: `Vision-Lab/studies/STUDY_INDEX.md` فهرس الدراسات الأخرى (Elnagar-POS، Marwa-elnagar، live_db_architecture…).

## 10) فهرس الملفات المهمة (جدول)
| الملف | الدور (استنتاج/قراءة) | مصدر المعرفة |
|---|---|---|
| requirements.txt | حزمة العقدة (أساسيات) | 📖 مقروء |
| pos_system/backend.py | خلفية Eel + إعدادات Sheet | 📖 مقروء (1-100/927) |
| pos_system/telegram_bot/bot.py | بوت الطلبات الذكي | 📖 مقروء (1-100/2594) |
| pos_system/mobile_local_api_server.py | API محلي للموبايل | 📖 مقروء (1-80/663) |
| pos_system/firebase_importer_loop.py | حلقة استيراد 10ث + heartbeat 60ث | 📖 مقروء (42/42) |
| pos_system/desktop_sidebar.py | شريط أوامر سطح مكتب CustomTkinter | 📖 مقروء (1-60/755) |
| pos_system/firebase_importer.py | منطق الاستيراد + backup_db() كل دورة | 🔍 grep (سطر 14-22، 260) |
| pos_system/android_importer.py / telegram_importer.py | مستوردان بنمط نسخ احتياطي مماثل | 🔍 grep |
| pos_system/database.py | طبقة DB الكاملة (130KB — غير مقروء، دورها مستنتج) | 🏷️ بالاسم + مراجع |
| notebook/app.py | واجهة ويب Flask + API التقاط | 📖 مقروء (1-80/263) |
| notebook/telegram_bridge.py | جسر تليجرام urllib + تذكيرات | 📖 مقروء (1-60/616) |
| notebook/store.py | تخزين SQLite معزول | 📖 مقروء (1-30/496) |
| notebook/brain.py | عقل قواعدي عربي بلا إنترنت | 📖 مقروء (1-30/499) |
| notebook/scheduler.py | منظم اليوم + ترحيل + مراجعة مساء | 📖 مقروء (1-30/304) |
| notebook/prayer.py | مواقيت صلاة فلكية بلا إنترنت | 📖 مقروء (1-30/237) |
| notebook/automation.py | مشغّل الصباح/المساء/الدورة كل 30 د | 📖 مقروء (1-30/158) |
| notebook/README.md | التوثيق الرسمي للنوتبوك + API + قناة Marwty | 📖 مقروء (75/75) |
| tools/laptop_sync.py | مرآة العقدتين + خزينة system_brain_sync | 📖 مقروء (1-40/578) |
| notebook/install_services.ps1 | مثبت مهام MarwaBot_* الخمس | 🔍 grep (سطر 23-27) |
| scripts/git_autosync.py | مزامنة Git + حاجز أسرار + NODE_ID | 🔍 grep |
| memory/decisions_log.md | قواعد التزامن والخزينة | 🔍 grep |
| mcp/pos-reader/server.py + mcp/pos-writer/server.py | بوابة MCP للقراءة/الكتابة | 🏷️ بالاسم |

## 11) سجل الجولة (تتبع تقدم الدراسة)
- [x] المرحلة 0: قراءة الهيكل السابق + جرد الجذر والمجلدات (pwsh).
- [x] المرحلة 1: requirements.txt + backend.py + telegram_bot/bot.py + mobile_local_api_server.py + firebase_importer_loop.py (+ أدلة grep للـBackups/MarwaBot/NODE_ID).
- [x] المرحلة 2أ: desktop_sidebar.py + notebook (app/telegram_bridge/store/brain) — 5 ملفات.
- [x] المرحلة 2ب: notebook (scheduler/prayer/automation) + notebook/README + laptop_sync.py (1-40) — 5 ملفات.
- [x] المرحلة 3: جرد أسماء orchestrator (core/router/squad بـ8 وكلاء) + pos_system + mcp (pos-reader/pos-writer) + tools — بالأسماء.
- [x] المرحلة 4: جرد سطحي Vision-Lab (studies/config/tools/ai_templates/memory — bلا قراءة داخلية) + الإغلاق النهائي.
