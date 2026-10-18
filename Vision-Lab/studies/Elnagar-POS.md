# 🏗️ ملخص معماري: Elnagar POS

> **حالة الدراسة**: مكتملة — 20/20 ملف مقروء (قراءة جزئية موجّهة + جرد أسماء للمجلدات).
> **مصدر الدراسة**: `G:\ai\Elnagar POS` — نظام نقاط بيع إنتاجي شغّال حاليًا للورشة.
> قاعدة الدراسة: قراءة فقط — لا فتح لأي قاعدة بيانات — الاستنتاج بالأسماء والكود.

---

## 1) الغرض
نظام **ERP نقاط بيع** مكتبي/شبكي لإدارة ورشة «النجار برنت» للطباعة والقص بالليزر — أبعد من POS بسيط: عملاء، طلبات ببنود، مخزون، مالية بمحرك مركزي، **فواتير مشتريات، موظفون وحضور ورواتب والتزامات ونوبات يومية** (27 جدول SQLite)، مع توجيه إنتاج لمحطات الورشة (ليزر/سبليميشن/فوتو/تجميع). حاجة الإدخال متعددة القنوات: كاشير ويب (Eel)، إضافة متصفح، تطبيق جوال، بوت تليجرام، وطوابير Firebase/Supabase. **حالة إنتاجية شغّالة حاليًا** — قاعدة حية `pos_data.db` بجوار الكود.

## 2) نقاط الدخول + التشغيل
✅ مؤكد بالقراءة:

| نقطة الدخول | المنفذ | الدور |
|---|---|---|
| `main_desktop.py` (59 سطرًا) | — | **القاذف الرئيسي**: يشغّل `app.py` كعملية Flask منفصلة (5050) ثم يفتح Eel على 8000 (Chrome App Mode ← Edge ← متصفح افتراضي)؛ يقتل الـ Sidebar عند الخروج |
| `backend.py` (927 سطرًا) | عبر Eel | باكند سطح المكتب: دوال `py_*` للواجهة (إعدادات، عملاء، اختبار Sheets)؛ يوجّه كل المخرجات إلى `backend_crash.log` |
| `app.py` (1873 سطرًا) | 5050 | **Flask API + خادم ثابت `web/`**: نقاط `/api/*` (عملاء/طلبات/صور/حافظة)، Blueprint مزامنة `server_extensions.sync_bp`، محرك `laser_engine` |
| `mobile_local_api_server.py` (663 سطرًا) | 7777 + UDP:7789 | **FastAPI** لتطبيق الجوال: مصادقة بمفتاح اختياري، تحليل طلبات بالذكاء الاصطناعي عبر OpenRouter، إشعارات ويندوز Toast |
| `main.py` (804 سطرًا) | عميل | تطبيق **Flet** «Elnagar POS Mobile» Offline-First بقاعدة محلية `mobile.db` مزامنة للسيرفر |

التشغيل (مؤكد من `elnagar_service_manager.py` — 249 سطرًا): مدير خدمات يشغّل 4 خدمات بملفات PID في `runtime/` وسجلات في `runtime_logs/` باستخدام **pythonw من `.venv`**: `backend.py`، `telegram_bot/bot.py`، `mobile_local_api_server.py`، `firebase_importer_loop.py` (مع فحص حالة ونقص شجرة العمليات بـ psutil). *ملاحظة: فحص منفذ خدمة backend مضبوط على 7777 وهو منفذ API الجوال لا Eel (8000) — يبدو خطأ نسخ.* حولها عائلة سكربتات .bat/.vbs (تشغيل/إيقاف/حالة/إصلاح + `install_startup.bat`).

## 3) الهيكل العام
المنطق كله في **جذر المشروع** (المجلدات فرعية وهامشية):
- **بيانات**: `database.py` (3523 سطرًا — الأكبر) فوق SQLite.
- **واجهة مكتبية**: `web/` (HTML/JS) ← Eel ← `backend.py` على 8000.
- **خوادم**: `app.py` Flask:5050 (لإضافة المتصفح/واتساب) + `mobile_local_api_server.py` (FastAPI:7777 للجوال).
- **مزامنة خارجية**: عائلة `google_*`/`sheets_*` + عائلة `firebase_*` + `sync_manager.py` + `drive_sync.py`.
- **استيراد طلبات**: `telegram_importer.py` (+loop) و`android_importer.py` (+loop).
- **مجلدات مساندة**: `src/` (4 ملفات فقط!)، `cloud/` (14)، `telegram_bot/`، `erp_extension/`، `orchestrator/`، `web/`، `static/`، `ui/`، `orders/`، `pos_images/`.
- **أرشفة مفرطة حول الكود**: 6 مجلدات نسخ احتياطية قديمة + نسخ `.bak` في الجذر نفسه (بما فيها نسخ `database.py` بأربعة تواريخ).

## 4) الوحدات الرئيسية
*(مكتملة)*

| الوحدة | الملفات | الدور |
|---|---|---|
| نواة البيانات | `database.py` | جداول settings/clients/products/orders/transactions + migrations هادئة + خطاف مزامنة Sheets لكل طلب |
| مكتب الويب المحلي | `backend.py` + `main_desktop.py` | جسر Eel ↔ JS لواجهة `web/` |
| API الشبكة | `app.py` + `server_extensions.py` | Flask:5050 — تفاصيل عميل (من إضافة واتساب)، بيانات كاملة، صور، ليزر |
| API الجوال | `mobile_local_api_server.py` | FastAPI:7777 + تحليل طلب نصي بالذكاء الاصطناعي (OpenRouter) + اكتشاف UDP |
| جوال مرافق | `main.py` / `mobile_app_stable_v0.8.0.py` | Flet — طلبات Offline تُزامن لاحقًا (`is_synced`) |
| مالية | `financial_engine.py` (36KB) + `financial_functions.py` + `finances.json` | محرك مالية مستقل + مخزن JSON |
| سحابة ثانية | `cloud/supabase_sync.py` + `cloud_webhook_server.py` + `schema_migrator.py` | مسار Supabase موازٍ لـ Firebase |
| إضافة متصفح | `erp_extension/` (sidepanel.js 50KB) | Chrome extension — تكلم Flask:5050 |
| إنتاج/ليزر | `laser_engine.py` + `ui/laser_ops.py` + `src/production_engine.py` | طبقات تشغيل القص |
| Orchestrator | `orchestrator/` (base.py, core.py, steering_bar.py, agents/) | إطار وكلاء AI صغير داخل النظام |
| بوت تليجرام | `telegram_bot/bot.py` (2594 سطرًا) | محادثة عربية بـ 8 حالات (اسم/هاتف/نوع/أصناف/مدفوع/ملاحظات/صور/تأكيد) + ذكاء `gpt-4o-mini` عبر OpenRouter + طابور قابل للتبديل (Firebase↔Sheets) |
| توجيه الإنتاج | `src/production_engine.py` (174 سطرًا) | `ProductionRouter` يستخرج المقاسات والمواد (خشب/MD F، أكريليك، جلد) ومحطات العمل (ليزر/سبليميشن/فوتو/تجميع) من اسم المنتج بالعربية + قواعد متعلّمة من القاعدة |

## 5) المكتبات
**`requirements.txt` (20 حزمة)**: Flask + Flask-Cors + Eel (سطح مكتب)، FastAPI + uvicorn + python-multipart (API)، streamlit + pandas، google-api-python-client + google-auth-oauthlib + google-auth-httplib2 (Google)، watchdog (مراقبة ملفات)، Pillow + mss + pyperclip (صور/شاشة/حافظة)، customtkinter + tkinterdnd2 (واجهات مكتبية)، openai، python-telegram-bot>=21.9,<22، supabase.

**`requirements_detected.txt` (22)**: يضيف gevent + gevent-websocket (محرك Eel)، pywin32، psutil، requests، flet، arabic-reshaper + python-bidi (دعم العربية).

**`requirements_windows_fixed.txt` (25)**: الأشمل — يضيف **firebase-admin**.
⇒ ثلاث ملفات requirements غير متطابقة (20/22/25) = بيئة غير موحّدة؛ المرجع العملي غالبًا `requirements_windows_fixed.txt`.

**المستخدم فعليًا في الكود المقروء:** Eel (backend/main_desktop)، Flask+CORS (app.py + cloud_webhook_server)، FastAPI+uvicorn (mobile API)، python-telegram-bot (bot.py)، عميل OpenAI→OpenRouter (bot + mobile API)، googleapiclient + service_account (Sheets)، firebase-admin (المستورد)، psutil (مدير الخدمات)، pywin32+PIL (حافظة في app.py)، flet (main.py)، shutil للنسخ، psutil/psutil.
*ملاحظة أمان: مفتاح OpenRouter مضمّن كقيمة احتياطية في `mobile_local_api_server.py` (لا تُطبع قيمته هنا) بينما `telegram_bot/config.py` يحمّل التوكنات من `.env.telegram` بطريقة صحيحة — تفاوت في الممارسة بين الملفين.*

## 6) مخازن البيانات
*(استنتاج من الكود فقط — لم تُفتح أي قاعدة)*

| المخزن | المالك | الجداول المرصودة في الكود |
|---|---|---|
| `pos_data.db` (SQLite + WAL — حية) | `database.py` | **27 جدولًا** (معدودة من `CREATE TABLE IF NOT EXISTS` في database.py): settings، clients، products، categories، orders، order_items، transactions، obligations، obligation_payments_history، scheduled_obligations، daily_financial_archive، purchase_invoices، purchase_items، inventory_counts، shortages، production_tasks، tasks، staff، staff_calls، attendance، payroll_transactions، requests، chat_messages، security_tokens، operation_logs، file_movement_logs، daily_shifts |
| `mobile.db` (SQLite محلية) | `main.py` (عميل Flet) | settings، clients، products، suppliers، transactions، orders (بحقل `is_synced` للمزامنة) |
| Supabase (سحابي) | `cloud/supabase_sync.py` | مرآة جداول POS + جدول `commands` (طابور أوامر) |
| Firebase Firestore | `firebase_importer.py` + `telegram_bot/firebase_client.py` | مجموعات طوابير (عملاء/منتجات/طلبات) + `importer_heartbeats` + `errors` |
| `elnagar_pos.db` / `elnagar_mobile.db` / `mobile.db` (بالجذر) | لم يُرَ مالكها في المقروء | أرشيف غالبًا |
| JSON | `finances.json`، `sidebar_notes.json`، `logs_dump.json` | بيانات مساندة/تصدير |
| Sheets/Firebase | مرايا سحابية للقراءة والتنسيق | 5 تبويبات مرآة + أوامر |

**نسخ القاعدة في الجذر (من أسماء الملفات):** `pos_data.db` (~240KB، مع `-shm/-wal` حيتان = قيد فتح) + ~14 نسخة مؤرخة (bak/backup من 2026-10-11 إلى 16 + jan19/before_reset/merge) — النسخ الآلي مصدره `firebase_importer.backup_db()` (كل دورة) دون تنظيف.

## 7) التكاملات (تليجرام / Firebase / أجهزة)
*(محدّث بعد دفعة 3)*

**Firebase — طابور أوامر Firestore بين الجوال/الويب والـ POS:**
- `firebase_importer.py` (300 سطرًا): يسحب مستندات `status=pending` (50 لكل دورة) من مجموعات العملاء/المنتجات/الطلبات، يغيّر حالتها `processing → imported/failed`، ويدخلها في `pos_data.db` عبر دوال `database` (add_new_client/add_quick_product/…). الفرز المحلي بـ `created_at` لتجنّب فهرس Firestore مركّب.
- `firebase_importer_loop.py`: حلقة كل **10 ثوانٍ** (`POLL_INTERVAL=10`)، نبضة `importer_heartbeats/main_loop` كل 60 ثانية، وأخطاء تُسجّل في مجموعة Firestore `errors`.
- قرينة مهمة: `firebase_importer_loop.py:26` يستدعي `run_import_cycle(dry_run=False)` في كل دورة، و`firebase_importer.py:25` يعرّف `BACKUP_DIR = <الجذر>/Backups` — انظر §8 للجذر الكامل.
- الميران المكمّلان: `firebase_mirror_from_pos.py` (POS → Firebase) و`firebase_admin_client.py` (get_db/get_bucket/update_doc_status).

**تليجرام:** `telegram_bot/` هو البوت الحقيقي — `bot.py` ضخم (109KB!)، `openrouter_client.py` (26KB، ذكاء اصطناعي لتفسير الطلب)، `firebase_client.py`، `config.py`، و`sheets_queue.py` (42KB). المسار: طلب تليجرام → **قائمة انتظار في Google Sheets** (تُقرأ صفًّا صفًّا برأس أعمدة ثابت) → `telegram_importer.py` يدخلها في POS ويحدّث الصف. مفاتيحه في `.env.telegram`.

**Google Sheets (مسار حي ثانٍ):** `google_sheet_realtime_sync.py` (يُستدعى داخل `database.py` نفسه لكل تغيير طلب) + `sync_pos_to_sheet.py` + `sheets_sync.py` + `google_api_sync.py` + `backup_google_sheet.py` + `drive_sync.py`، بمصادقة `credentials.json`/`token.json`/`token.pickle` في الجذر.

**Supabase + Webhook — «Marwa Cloud Brain» (سحابة ذكية موازية):**
- `cloud/supabase_sync.py` (537 سطرًا) — «HermesSyncManager»: `push_mirror` يرفع مرآة جداول `pos_data.db` إلى Supabase (يفتح القاعدة **وضع ro فقط**)، و`pull_queue` ينفّذ أوامر جدول `commands` ذات `status=pending` محليًا عبر دوال البرنامج الرسمية ثم `applied`، مع أوضاع `--push-once/--pull-once/--daemon/--query-*`. التعهد الداخلي: لا تُطبع القيم السرية.
- `cloud/cloud_webhook_server.py` (379 سطرًا) — خادم Telegram Webhook يُنشر على Replit: يستقبل رسائل بوت المالك (`@Marwty_bot`) وقت انطفاء جهاز المحل، يستخدم مرآة Supabase كذاكرة + LLM بشخصية «وكيل النجار برنت»، ويحوّل أوامر النظام (لقطة شاشة/إغلاق الجهاز/إعادة تشغيل) إلى صفوف `commands` pending ينفذها `supabase_sync.py` محليًا — **قناة تحكم عن بُعد كاملة في جهاز المحل** (محصورة بـ OWNER_TELEGRAM_ID).

**إضافة متصفح ERP:** `erp_extension/` (manifest/background/content/sidepanel.js بحجم 50KB) — لالتقاط بيانات العملاء (من واتساب ويب) واستدعاء Flask:5050.

**الجوال:** `android_companion_app/` يتصل عبر FastAPI:7777 ويكتشف الخادم ببث UDP:7789.

**عمليات الخدمات:** مجلد `runtime/` يحفظ PID لكل خدمة (backend، firebase_importer، local_mobile_api، telegram_bot) — تُدار بـ `elnagar_service_manager.py`.

## 8) تقييم الصحة (بدليل)
*(تحديث أولي — الأدلة تتراكم مع القراءة)*

🚨 **أمني:**
1. **مفتاح API سري مكتوب حرفيًا داخل `mobile_local_api_server.py`** (قيمة احتياطية لمتغير OpenRouter في السطور ~29–32) — سرّ في الكود؛ *قيمته لا تُطبع هنا*.
2. **المصادقة اختيارية** في نفس الملف: `verify_api_key` تمرّر إن كان `LOCAL_MOBILE_API_KEY` فارغًا + CORS `allow_origins=["*"]` مع `allow_credentials=True`.
3. **`app.py`**: `CORS(origins="*")` و`/api/get_full_data` يصبّ العملاء/المنتجات/الطلبات كلها بلا مصادقة — مكشوف لكل جهاز على الشبكة.
4. **أسرار على القرص في الجذر**: `.env`، `.env.telegram`، `firebase_service_account.json`، `credentials.json`، `token.json`، `token.pickle`، `client_secret_*.json` (لم تُقرأ — جرد بالأسماء).

⚠️ **هيكلي/تشغيلي:**
5. **جذر كارثة Backups (59GB) — موثّق بالكود**: `firebase_importer.py` سطور 13–22: `BACKUP_DIR = <جذر المشروع>/Backups`، ودالة `backup_db()` تنسخ `pos_data.db` كاملًا إلى `pos_data_backup_fb_importer_<timestamp>.db` بـ `shutil.copy2` **ولا يوجد أي حذف/تنظيف للنسخ القديمة**؛ والحلقة `firebase_importer_loop.py` تنادي `run_import_cycle(dry_run=False)` كل **10 ثوانٍ** (POLL_INTERVAL=10) — أي أن كل دورة قابلة لتوليد نسخة جديدة بمقياس مئات النسخ يوميًا. و`telegram_importer.py` كذلك يستخدم نفس مجلد `Backups` (BACKUP_ROOT سطر 31). **تأكيد موضع الاستدعاء (جرد):** `backup_db()` يُستدعى عند `firebase_importer.py:260` — أول ما تفعله `run_import_cycle()` (التعريف سطر 251) — أي **نسخة كاملة من القاعدة مع كل دورة كل 10 ثوانٍ** ⇒ نظريًا ~8,600 نسخة/يوم وأكوام بلا حد؛ هذا هو السبب المباشر لتضخم `Backups/` إلى 59GB (أفرغه المالك يدويًا، والسلوك ما يزال في الكود).
6. Migrations بـ `try/except: pass` في `database.py` و`main.py` — أخطاء مخطّاة تبتلع بصمت.
7. تهيئة قاعدة الجوال في `main.py` تسلسل مكرر مع `database.py` (مخططان منفصلان).
8. تاريخ نسخ `.bak` متعدد لنفس المصدر (app.py، database.py، mobile_local_api_server.py، sync_manager.py) = تعديلات إنتاج حية بلا Git نشط للمصدر.
9. `main_desktop.py` يقتل العمليات بـ `taskkill/wmic` حسب عنوان النافذة — هش وعرضة لقتل عمليات أخرى.
10. ملف `Firestore)` بسعة 0 بايت في الجذر — أثر أمر خاطئ (إعادة توجيه).
11. **بوت تليجرام بلا تحقق إن غاب المالك**: `telegram_bot/config.py` سطر 53–57 — `is_authorized` ترجع **True للجميع** إذا كان `OWNER_TELEGRAM_ID` فارغًا.
12. `elnagar_service_manager.py`: خدمة backend تُفحَص على المنفذ **7777** (منفذ API الجوال) بينما باكند Eel يعمل على 8000 — تهيئة منسوخة بشكل خاطئ (فحص صحة مضلل).
13. معرف جدول Google مضمّن في `google_sheet_realtime_sync.py` (DEFAULT_CONFIG) — إعداد بيئة داخل الكود بدل config خارجي.

✅ **مؤشرات صحّية جيدة:**
- `pos_data.db` بوضع **WAL** (تزامن آمن) في `get_db_connection()`.
- `financial_engine.py` (909 سطرًا): كل عمليات الرصيد إلزاميًا عبره، مع «المعادلة النووية» `recalculate_balance` لإعادة بناء الرصيد من الحركات الخام ومعالجة بيانات قديمة (type='Income' القديم، استثناء قيود الطلبات المكررة).
- المرآة السحابية تفتح `pos_data.db` بوضع **ro فقط** (تعهد مكتوب في `supabase_sync.py`).
- نبضات حياة + تسجيل أخطاء في Firestore من حلقة الاستيراد، وسجلات لكل خدمة في `runtime_logs/`.
- انفصال طبقي واضح رغم الفوضى: بيانات (database) / مالية (financial_engine) / توجيه إنتاج (production_engine) / تكاملات (مستوردون مستقلون).

## 9) خريطة دخول للتطوير
| أريد أن… | ابدأ من | انتبه إلى |
|---|---|---|
| تعدّل شاشة الكاشير/الحسابات | `web/index.html` (293KB) + دوال `py_*` في `backend.py` | الواجهة HTML عملاقة أحادية؛ Eel يعمل على 8000 |
| تضيف نقطة API | `app.py` (Flask:5050) أو `mobile_local_api_server.py` (7777) | CORS مفتوح والمصادقة اختيارية — اضبط قبل النشر |
| تعدّل المخطط | `database.py:init_db()` (27 جدولًا) | migrations بـ try/except — انسخ `pos_data.db` يدويًا أولًا وأغلق الخدمات |
| تعدّل المالية | `financial_engine.py` أولاً وقبلًا | كل تأثير على الرصيد يجب أن يمر عبره (توثيق داخلي صريح) |
| تعدّل منطق الإنتاج/الليزر | `laser_engine.py` + `ui/laser_ops.py` + `src/production_engine.py` | توجيه الإنتاج من اسم المنتج + قواعد متعلمة |
| تكامل تليجرام | `telegram_bot/bot.py` + `config.py` + `openrouter_client.py` | الأسرار في `.env.telegram`؛ الحلقة القديمة `telegram_importer.py` تعتمد نفس الإعدادات |
| تصلح جذر Backups | `firebase_importer.py` سطر 16–22 + 260 | أضف سياسة تنظيف (احتفظ بآخر N) قبل إعادة تشغيل الحلقة كل 10 ثوانٍ |
| تطبّق التطبيق الجوال | `android_companion_app/` (Flutter) + FastAPI:7777 | الأصول ~1GB؛ البناء عبر `mobile_build_ready/` وأدوات rewrite_*.py |
| تدير الخدمات | `elnagar_service_manager.py` + `runtime/*.pid` + `runtime_logs/` | 4 خدمات فقط تُدار؛ Flask:5050 يُطلق مع Eel فقط |
| تلغي/تضيف سحابة | `cloud/supabase_sync.py --daemon` و`cloud_webhook_server.py` | مساران موازيان (Firebase Firestore + Supabase) — حدد القناة الأصل قبل التعديل |

## 10) فهرس الملفات المهمة
| الملف | الدور | ملاحظات |
|---|---|---|
| `requirements.txt` / `_detected` / `_windows_fixed` | 20/22/25 حزمة | ثلاث بيئات غير موحّدة؛ الأشمل `requirements_windows_fixed.txt` |
| `backend.py` (927 سطرًا) | باكند Eel (سجل crash واحد متضخم) | قُرئت أول 120 |
| `database.py` (3523 سطرًا) | نواة البيانات — **27 جدولًا** | الأكبر؛ قُرئت أول 100 + جرد CREATE TABLE |
| `app.py` (1873) | Flask API:5050 + ملفات ساكنة | CORS مفتوح |
| `main_desktop.py` (59) | قاذف المكتب (Eel 8000 + Flask 5050) | قُرئت كاملة |
| `mobile_local_api_server.py` (663) | FastAPI:7777 + تحليل AI | مفتاح OpenRouter مضمّن ⚠️ |
| `main.py` (804) | عميل Flet جوال Offline | قاعدة `mobile.db` مستقلة |
| `financial_engine.py` (909) | «محرك سلامة مالية» مركزي | «المعادلة النووية» للرصيد |
| `firebase_importer.py` (300) | Firestore → POS (طوابير) | `backup_db()` عند L260 — **جذر 59GB** |
| `firebase_importer_loop.py` (42) | حلقة كل 10 ثوانٍ + نبضات | قُرئت كاملة |
| `telegram_importer.py` (627) | طلبات تليجرام من قائمة Sheets | يعتمد telegram_bot/config + sheets_queue |
| `telegram_bot/bot.py` (2594) | البوت الذكي العربي | أول 80 سطرًا |
| `telegram_bot/config.py` (111) | إعدادات `.env.telegram` | تفويض مفتوح إن غاب المالك ⚠️ |
| `google_sheet_realtime_sync.py` (534) | مرآة Sheets حية | خطافات مباشرة من database.py |
| `cloud/supabase_sync.py` (537) | HermesSyncManager | ro-only + طابور commands |
| `cloud/cloud_webhook_server.py` (379) | «Marwa Cloud Brain» webhook (Replit) | تحكم عن بعد بأوامر نظام ⚠️ |
| `src/production_engine.py` (174) | توجيه إنتاج من اسم المنتج | src = ملفان فقط |
| `elnagar_service_manager.py` (249) | مدير 4 خدمات (PID/psutil) | فحص منفذ backend خاطئ (7777) |

### ما لم يُقرأ (خارج الميزانية عمدًا)
`sync_manager.py`، `desktop_sidebar.py` (42KB)، `android_importer.py` (30KB)، `sync_pos_to_sheet.py`، بقية `database.py`، `erp_extension/sidepanel.js`، `orchestrator/` (جرد أسماء فقط)، `android_companion_app/` (جرد سطحي — Flutter + apps_script_proxy + أدوات rewrite_*.py)، `web/*.html`، `sheets_sync.py`، `financial_engine.py` (بعد السطر 60).

---
*اكتملت الدراسة: **20/20 ملف مقروء** (قراءة جزئية موجّهة؛ عمليات الجرد والبحث الإجرائية خارج العدّ) — نسبة الجاهزية التقديرية: **~80%**.*
