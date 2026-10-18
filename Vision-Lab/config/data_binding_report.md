# تقرير ربط البيانات — task-2 (قطع قراءة الوكلاء من `pos_data.db` القديم)

**المالكة:** مروة (مديرة النظام) • **التاريخ:** 2026-10-18 00:35 (Africa/Cairo)
**الـ workspace:** `G:\ai\Naggar Print POS Agent\Vision-Lab`
**مسارات الكتابة الأصلية:** `config/` و`tools/` — وملفات أدوات الوكلاء المقصودة بالربط فقط (بـ`.bak` صريحة، القسم 6).

---

## 1) الخلاصة التنفيذية

| البند | القيمة |
|---|---|
| **المصدر الرسمي الحي** | `G:\ai\Elnagar POS\pos_data.db` (قاعدة تطبيق Elnagar POS الشغّال: Flask على **8888** + Mobile API على **7777**، بدأ 2026-10-17 23:57:09) |
| **النسخة القديمة المرفوضة** | `G:\ai\Naggar Print POS Agent\pos_data.db` (52 عميلاً/50 طلباً، أقصى طلب **#323**، أقصى تاريخ **2026-08-31**، مجموع الأرصدة **0.0**) |
| **إجمالي المديونيات الحية اليوم** | **1040.0 جنيه** لـ **4 عملاء مدينين** (التعريف الرسمي `balance > 0`) |
| **نفس التعريف على المصدر القديم** | **0.0** (صفر كاذب) — الفرق المثبت: **1040.0 − 0 = 1040.0 جنيه** |
| **طبقة الاتصال المركزية** | `config/data_source.py` + `config/data_source.json` — رفض صريح لكل مسار قديم |
| **سكربت الاستعلام الموحّد** | `tools/debt_total.py` (مُشغَّل فعليًا ⇒ 1040.0) |
| **اختبار القبول** | `tools/verify_binding.py` ⇒ **18/18 PASS** |
| **جرد خام للأدلة** | `config/inventory_raw.txt` (520 مطابقة في 241 ملفاً، من `tools/inventory_scan.py`) |
| **موضع الخلاف مع الفرضية الأولى** | PostgreSQL/`layan_erp` **ليس** المصدر الحي (لا عملية java، لا شيء على 18080، وبياناته متوقفة عند 24/09/2026) — المصدر الحي هو قاعدة Elnagar POS. تم الرجوع لتصحيح الـ lead بالدليل المقيس. |

---

## 2) جدول الجرد الكامل

> الأرقام في عمود «السطر» هي أرقام الأسطر **قبل** التعديل (في النسخ `.bak` مطابقة تمامًا).
> الملفات المعلَّمة ✅ عُدّلت (مع `.bak`)، ⬜ لم تُعدّل (السبب في العمود الأخير).

### أ) أدوات استعلام الوكلاء — نسخة مساحة العمل `G:\ai\Naggar Print POS Agent\orchestrator\agents\` (كانت تقرأ النسخة الميتة)

| الملف | السطر | كان يقرأ من | الغرض | الإجراء |
|---|---|---|---|---|
| `crm.py` ✅ | 20 (ROOT)، 21 (DB_PATH)، 28 (`sqlite3.connect` mode=ro) | `G:\ai\Naggar Print POS Agent\pos_data.db` | **سلمى** — ملف العميل/الطلبات/المتأخر | `DB_PATH = _central.db_path()` و`_ro_conn() → _central.open_readonly()` + `.bak` |
| `cfo.py` ✅ | 24، 25، 30 | نفسه | **فارس** — الخزينة/الديون/المستحقات/الهوامش | نفسه + `.bak` |
| `marketing.py` ✅ | 19، 20، 28 | نفسه | **كوكو** — الراكد/الباقات | نفسه + `.bak` |
| `data_healer.py` ✅ | 18، 19، 29 **و 415** (`sqlite3.connect(DB_PATH)` كتابةً) | نفسه | **حكيم** — الفحوص + الوسم الآلي | القراءة → الطبقة المركزية؛ **الكتابة** → `_central.open_readwrite(approved=False)` ⇒ مرفوضة افتراضيًا (قرار أمان — القسم 7) + `.bak` |
| `manufacturing_agent.py` ✅ | 29، 30، 36 | نفسه | **بيبو** — الخامات/الوصفات/بطاقة الشغل | نفسه + `.bak` |

**مروة** (`orchestrator/core.py`) = المنسّق العام وليست أداة استعلام مباشرة: لا اتصال SQLite فيها (توجيه + بطاقات هوية فقط) — لا تغيير. أدوات **سلمى** الفعلية هي `crm.py` أعلاه.

### ب) المزامنة السحابية والمرآة

| الملف | السطر | كان يقرأ من | الغرض | الإجراء |
|---|---|---|---|---|
| `cloud/supabase_sync.py` ✅ | 42 (ROOT)، 49 (DB_PATH)، 164‑165 (mode=ro) | `G:\ai\Naggar Print POS Agent\pos_data.db` (أرصدة صفرية) | رفع المرآة إلى Supabase | رُبط بالطبقة المركزية (يقرأ الحي الآن) + `.bak` — **لم يُشغَّل** (لا كتابة سحابية في هذه المهمة) |
| `G:\ai\Elnagar POS\cloud\supabase_sync.py` ⬜ | 49، 166 | `G:\ai\Elnagar POS\pos_data.db` ✔ (الحي) | نفسه | سليم أصلاً — لا تغيير (P1: توجيهه للطبقة لاحقًا) |
| `cloud/schema_migrator.py` ⬜ | 45 (LOCAL_DB)، 79 | نسخة المساحة الميتة | ترحيل مخطط محلي | P1 — ليس أداة استعلام؛ لم يُعدّل |
| `G:\ai\Elnagar POS\cloud\schema_migrator.py` ⬜ | 45، 79 | الحي ✔ | نفسه | سليم (P1) |

### ج) قارئ MCP (تحقّق بلا تعديل — بأمر الـ lead)

| الملف | السطر | كان يقرأ من | الغرض | الإجراء |
|---|---|---|---|---|
| `mcp/pos-reader/server.py` ⬜ | 14، 33 (DEFAULT)، 37 (`POS_DB_PATH`)، 43‑44 (`mode=ro`) | `G:\ai\Elnagar POS\pos_data.db` ✔ (الحي) + تجاوز للاختبار على نسخة | قارئ MCP قراءة فقط | **تحقّق:** `mode=ro` صارم، صفر `INSERT/UPDATE/DELETE`، صفر PRAGMA كتابة ⇒ **لم يُلمس** (لا كسر لأداة تعمل) |
| `mcp/pos-reader/README.md` ⬜ | 3، 36 | توثيق المسار | توثيق | لا تغيير |
| `mcp/pos-reader/test_against_backup.py` ⬜ | 2، 23 | `backup\pos_data_2026-10-10_1128.db` | اختبار مقابل نسخة احتياطية | لا تغيير (اختبار مقصود) |
| `mcp/pos-reader/check_financial_parity.py` ⬜ | 23 | `"pos_data.db"` نسبي (cwd) | مطابقة مالية | P1 — المسار النسبي خطر؛ لم يُعدّل |

### د) سكربتات وأدوات النظام

| الملف | السطر | كان يقرأ من | الغرض | الإجراء |
|---|---|---|---|---|
| `scripts/backup_pos.py` ⬜ | 23 (`SRC_DB=ROOT/pos_data.db`)، 46‑47، 81 | نسخة المساحة **الميتة** | نسخ احتياطي دوري | ⚠️ P1 عاجل: النسخ الاحتياطية الحالية بلا قيمة (تحفظ صفر أرصدة) — موصى بتوجيهه للطبقة؛ لم يُعدّل |
| `scripts/parity_watchdog.py` ⬜ | 6، 12، 48 (DEFAULT_LOCAL_DB)، 86، 201 | `G:\ai\Elnagar POS\pos_data.db` ✔ | مراقبة التطابق محلي↔سحابة | سليم — لا تغيير |
| `tools/laptop_sync.py` ⬜ | 19، 51 (DB_PATH)، 295، 359، 402، 517، 528 | نسخة المساحة (بناء المرآة) + الحي (402) | مرآة الجهاز/العقل | P1 — يحفظ نسخة محلية مشتقة؛ لم يُعدّل |
| `tools/export_products_excel.py` ⬜ | 16، 102، 268 | `G:\ai\Elnagar POS\pos_data.db` ✔ | تصدير كتالوج | سليم — لا تغيير |
| `tools/import_products_excel.py` ⬜ | 11، 48، 113، 252 | الحي ✔ | استيراد آمن + نسخة `.bak` | سليم — لا تغيير |
| `tools/safe_pull.py` ⬜ | 77، 125 | `LS.DB_PATH` (laptop_sync) | سحب آمن | لا تغيير |

### هـ) برنامج POS منسوخ داخل المساحة (`pos_system/`) — ليس أداة وكيل

| الملف | السطر | كان يقرأ من | الغرض | الإجراء |
|---|---|---|---|---|
| `pos_system/database.py` ⬜ | 7 (`DB_NAME="pos_data.db"`)، 30 | نسبي حسب cwd | دوال البرنامج | لا تغيير (نسخة برنامج) |
| `pos_system/app.py` ⬜ | 1830‑1831 | نسبي | فحص WAL للبرنامج | لا تغيير |
| `pos_system/main.py` / `mobile_app_stable_v0.8.0.py` ⬜ | 34 / 23 | نسبي | واجهة الجوال | لا تغيير |
| `pos_system/firebase_mirror_from_pos.py` ⬜ | 6، 84 | `os.path.dirname(__file__)/pos_data.db` | مرآة Firebase | لا تغيير |
| `pos_system/firebase_importer.py` ⬜ | 13، 20 | نسبي + نسخة احتياطية | مستورد Firebase | لا تغيير |
| `pos_system/android_importer.py` ⬜ | 18، 156، 158 | `ROOT_DIR/pos_data.db` | مستورد الأندرويد | لا تغيير |
| `pos_system/telegram_importer.py` ⬜ | 137، 139 | نسبي | مستورد تليجرام | لا تغيير |
| `pos_system/reset_drawer.py` / `reset_accounts.py` ⬜ | 9‑10 / 5‑6، 18 | نسبي | تصفير الدرج/الحسابات | لا تغيير (سكربتات تشغيلية) |
| `pos_system/sync_pos_to_sheet.py` ⬜ | 94، 322، 349 | نسخة البرنامج | مرآة Google Sheets | لا تغيير |
| `pos_system/telegram_bot/README.md` ⬜ | 8 | توثيق | توثيق | لا تغيير |

### و) سكربتات إصلاح لمرة واحدة

| الملف | السطر | كان يقرأ من | الغرض | الإجراء |
|---|---|---|---|---|
| `fix_balance.py` ⬜ | 8، 15 | نسخة المساحة | إصلاح أرصدة تاريخي | لا تغيير (تاريخي) |
| `fix_balance2.py` ⬜ | 8، 13 | `_sandbox_pos_writer\pos_data.db` | إصلاح على الساندبوكس | لا تغيير |
| `fix_correct_db.py` ⬜ | 8، 13 | `G:\ai\Elnagar POS\pos_data.db` (**كتابة**) | تصحيح تاريخي على الحي | لا تغيير — ⚠️ يُذكر أن فيه كتابة مباشرة على الحي (خطر إن أُعيد تشغيله) |

### ز) ساندبوكس/أرشيف/نسخ احتياطية/توثيق (كلها خارج الاستعلام الحي)

| النطاق | أمثلة (أسطر) | الإجراء |
|---|---|---|
| `_sandbox_pos_writer\*` | `database.py` 7/30، `test_purchase_fixes.py`، `test_fixes.py`، `test_live_port.py`، `patches\*` | لا تغيير — بيئة اختبار |
| `G:\ai\Elnagar POS\_ARCHIVE_SCRIPTS\*` | `simple_check.py` 3، `migrate_db_v*`، `inspect_*`، `fix_*` … (~30 ملفاً) | لا تغيير — كود مؤرشف |
| `G:\ai\Elnagar POS\_quarantine_unused_20260514_225636\*` | `main.py` 31، `mobile_app_stable_v0.8.0.py` 23، `revert_script.py` 3/8 … | لا تغيير — معزول |
| `G:\ai\Elnagar POS\backup_code_before_fix\*` | `database_*.py`، `database.py.*.bak` | لا تغيير — نسخ كود |
| `G:\ai\Elnagar POS\SAFE_BACKUP_BEFORE_REPAIR\*\Backups\*` | `database.py`، `fix_*.py` … (~22 ملفاً) | لا تغيير — نسخ احتياطية |
| `G:\ai\Elnagar POS\android_companion_app*\*` | `order_queue_service.dart`، `Code.gs`، READMEs | لا تغيير — تطبيق أندرويد لا يلمس القاعدة |
| `G:\ai\Elnagar POS\docs_ai_audit\*` | تقارير وثّقت «هل لُمست القاعدة» | لا تغيير — توثيق |
| `G:\ai\Elnagar POS\scratch\*` | `check_clients.py`، `db_schema.py`، `test_db.py` | لا تغيير — مسودة |

### ح) قواعد وتوثيق وذاكرة (لا تغيير)

`RULES.md` 38 («القاعدة هي المرجع الوحيد») • `README.md` 8/41/50 • `STATUS.md` (عدة مواضع) • `SALMA_CRM_STATE.md` 18/69 • `memory\decisions_log.md` 16 سطراً • `memory\roadmap.md` • `memory\reports\*` • `.env.example` 9 (`LIVE_DB_PATH`) • `LAPTOP_SECRET_KIT.md` (لا يُطبع منه شيء) • `notebook\store.py` 4/86 و`projects\MarwaNotebook\store.py` 4/86 (قاعدة **مستقلة** `notebook.db` صراحةً) • `cloud\migrations\003_*.sql`.

### ط) البرنامج الحي ونسخ Elnagar للمنسّق

| الملف | السطر | كان يقرأ من | الغرض | الإجراء |
|---|---|---|---|---|
| `G:\ai\Elnagar POS\database.py` ⬜ | 7 (`DB_NAME`)، 30 | `pos_data.db` نسبي = **الحي** | محرك البرنامج الرسمي | لا تغيير (هو الحي) |
| `G:\ai\Elnagar POS\app.py` ⬜ | 1830‑1831 | نسبي | فحص WAL | لا تغيير |
| `G:\ai\Elnagar POS\orchestrator\agents\crm.py` ⬜ | 21، 28 | `ROOT = G:\ai\Elnagar POS` ⇒ **الحي** ✔ | سلمى | سليم أصلاً — لا تغيير (P1: توجيهه للطبقة المركزية) |
| `...\cfo.py` ⬜ | 25، 30 | الحي ✔ | فارس | سليم (P1) |
| `...\marketing.py` ⬜ | 20، 28 | الحي ✔ | كوكو | سليم (P1) |
| `...\data_healer.py` ⬜ | 19، 29، 415 | الحي ✔ | حكيم | سليم (P1) |
| `...\manufacturing_agent.py` ⬜ | 30، 36 | الحي ✔ | بيبو | سليم (P1) |

> **للأمانة:** نسخة Elnagar للمنسّق لم تُعدّل عن قصد — مخرجاتها صحيحة أصلاً (تشير للحي)، وتعديلها يزيد مساحة الخطر على النظام الشغّال. موصى بتوجيهها للطبقة المركزية في جولة قادمة (P1).
> **حدود الجرد:** الأدلة الخام الكاملة (490 مطابقة/240 ملفاً بالمسارات والأسطر) في `config/inventory_raw.txt`؛ تم تخطي مجلدات `.venv/.git/build/node_modules/.gradle` وسكربتات JDK المرفقة.

---

## 3) طبقة الاتصال المركزية الواحدة

**الملفات:** `config/data_source.json` (الإعداد) + `config/data_source.py` (المنفّذ) + `config/__init__.py`.

| الواجهة | الوظيفة |
|---|---|
| `db_path()` | المسار الرسمي الحي (من الإعداد ثم `POS_LIVE_DB`)؛ يحذّر بصوت عالٍ ويسجّل المخالفة إن كان المسار قديمًا |
| `classify(path)` | تصنيف أي مسار: `official` / `legacy` / `other` + السبب |
| `open_readonly()` | اتصال `mode=ro` بالمصدر الرسمي **فقط**؛ يرفع `LegacySourceRefused` لأي مسار قديم أو غير معتمد |
| `open_readwrite(purpose, approved)` | الكتابة على الحي **مرفوضة افتراضيًا**؛ يلزم `POS_LIVE_WRITE=1` **و** `approved=True` |
| `debt_totals()` / `debtors()` | التعريف الرسمي للمديونية + أعلى المدينين (مع حجب أي اسم يشبه رقم هاتف) |
| `forensic_open_readonly(path)` | قراءة **تشخيصية غير محكومة** — للمقارنة الإثباتية فقط (لا تُستخدم في أي أداة) |
| `assert_official()` / `refuse_if_legacy()` / `last_violation()` | الحاجز + سجل المخالفات |

**المصادر المرفوضة بالاسم** (من `data_source.json` / `KNOWN_LEGACY`):

| المسار | السبب |
|---|---|
| `G:\ai\Naggar Print POS Agent\pos_data.db` | نسخة متجمدة: 52 عميلاً/50 طلباً، أقصى طلب #323، أقصى تاريخ 2026-08-31، مجموع الأرصدة 0.0 |
| `G:\ai\Naggar Print POS Agent\_sandbox_pos_writer\pos_data.db` | ساندبوكس اختبار كتابة |
| `G:\ai\Elnagar POS\pos_data_merge_backup.db` | نسخة قبل دمج المكرّرات |

**قواعد الرفض العامة:** أي `pos_data.db` ليس المسار الرسمي • أي مسار داخل `backup\`/`Backups\`/`_quarantine_unused*`/`_ARCHIVE_SCRIPTS`/`backup_code_before_fix\` • أي اسم يطابق `pos_data.db.*` أو `pos_data_backup*` أو `pos_data_merge_backup*` أو `pos_data_20*` أو `*.bak-*`.

**منفذ التجاوز الوحيد:** `POS_LIVE_DB` — **ولا يسمح** بتمرير مسار قديم (يُرفض رغم التجاوز).

---

## 4) سكربت الاستعلام الموحّد + الرقم الحقيقي

**الأمر المنفَّذ فعليًا:**
```
python tools\debt_total.py --top 5
```

**الاستعلام الحرفي (التعريف الرسمي من `G:\ai\Elnagar POS\app.py` 1655/1712):**
```sql
SELECT COUNT(*) AS debt_clients_count,
       IFNULL(SUM(balance), 0) AS total_receivables
FROM clients WHERE balance > 0
```

**النتيجة الحية (مُشغَّلة الآن):**

| الحقل | القيمة |
|---|---|
| المصدر | `G:\ai\Elnagar POS\pos_data.db` (تصنيف: official) |
| بيانات آخر طلب | **#334** بتاريخ **2026-10-16 16:22:56** |
| عدد العملاء المدينين | **4** |
| **إجمالي المديونيات الحية** | **1040.0 جنيه** |
| أعلى المدينين | 350 / 250 / 240 / 200 جنيه (المجموع 1040) |
| التطابق مع المرجع | مطابق ✔ |

**مطابقة الواجهة الحية (acceptance cross-check):** `GET http://127.0.0.1:7777/api/dashboard-summary` →
`clients_count=56, orders_total=58, products_count=105, debt_clients_count=4, total_receivables=1040.0` ⇒ **الرقم نفسه**.

---

## 5) إثبات أن المسار القديم لم يعد المصدر

`python tools\verify_binding.py` ⇒ **18/18 PASS** (الخروج 0). أهم الفحوص:

| الفحص | النتيجة | الدليل |
|---|---|---|
| المصدر الرسمي معتمد | PASS | `live_db=G:\ai\Elnagar POS\pos_data.db` (verdict=official) |
| الرقم الحي = التعريف الرسمي | PASS | `(4, 1040.0)` |
| رفض المساحة المتجمدة | PASS | `LegacySourceRefused` — «نسخة مساحة العمل المتجمدة … مجموع الأرصدة = 0.0 (صفر كاذب)» |
| رفض نسخة احتياطية | PASS | «مجلد أرشيف/نسخ احتياطي (backup)» |
| رفض الساندبوكس | PASS | «نسخة الساندبوكس … ليست بيانات حية» |
| **الفرق الرقمي** | PASS | **الحي 1040.0 − القديم 0 = 1040.0 جنيه** (القديم: 50 طلباً، أقصى #323، 2026-08-31) |
| مطابقة واجهة 7777 | PASS | `api=(4, 1040.0)` = `tool=(4, 1040.0)` |
| `POS_LIVE_DB=<قديم>` | PASS | رفض صريح + خروج **2** (التجاوز لا يُبيح مصدرًا قديمًا) |
| `POS_LIVE_DB=<الرسمي>` | PASS | خروج 0 و1040.0 |
| ربط الوكلاء الخمسة | PASS ×5 | `DB_PATH=G:\ai\Elnagar POS\pos_data.db`، صفر `sqlite3.connect(` في الكود، صفر `ROOT / "pos_data.db"` |
| اختبار وظيفي (فارس/CFO) | PASS | رد حي: «إجمالي الديون: **1040 جنيه** (كل الأرصدة)» |
| الاكتشاف الآلي للوكلاء | PASS | `AgentRegistry` سجّل `crm, cfo, marketing, data_healer, manufacturing` والتوجيه لـ«ديون ومستحقات» ⇒ `cfo` (لم يختفِ أي وكيل بسبب الربط) |

**نص الرفض الفعلي (مقتطف من stderr عند تمرير المسار القديم):**
```
⛔ مرفوض: محاولة قراءة من مصدر SQLite قديم/ميت
   المسار المطلوب : G:\ai\Naggar Print POS Agent\pos_data.db
   السبب          : نسخة مساحة العمل المتجمدة: 52 عميلاً/50 طلباً، أقصى طلب #323، أقصى تاريخ 2026-08-31، مجموع الأرصدة = 0.0 (صفر كاذب)
   المصدر الرسمي  : G:\ai\Elnagar POS\pos_data.db
```

**دليل «ماذا كان الوكلاء سيرون قبل الربط»:** نفس الوكيلان بعد الربط يعرضان أرقامًا حية —
فارس: «إجمالي الديون: 1040 جنيه»؛ سلمى: «Delivered: 52 / Under Preparation: 6» مع طلبات **#327–#333** التي لا وجود لها في النسخة القديمة (أقصاها #323).

---

## 6) الملفات التي لُمست + النسخ الاحتياطية

**جديد بالكامل (داخل نطاق `config/` و`tools/`):**
`config/data_source.py` · `config/data_source.json` · `config/__init__.py` · `tools/debt_total.py` · `tools/verify_binding.py` · `tools/inventory_scan.py` · `config/data_binding_report.md` (هذا الملف) · `config/inventory_raw.txt` (أدلة مُولَّدة).

**معدَّل خارج `config/` و`tools/`** — لأنها **أدوات الوكلاء المقصودة بالربط** صريحًا في المهمة، ولكل ملف نسخة `.bak-2026-10-18-marwa-task2` بجواره:

1. `orchestrator\agents\crm.py` → `crm.py.bak-2026-10-18-marwa-task2`
2. `orchestrator\agents\cfo.py` → `cfo.py.bak-2026-10-18-marwa-task2`
3. `orchestrator\agents\marketing.py` → `marketing.py.bak-2026-10-18-marwa-task2`
4. `orchestrator\agents\data_healer.py` → `data_healer.py.bak-2026-10-18-marwa-task2`
5. `orchestrator\agents\manufacturing_agent.py` → `manufacturing_agent.py.bak-2026-10-18-marwa-task2`
6. `cloud\supabase_sync.py` → `supabase_sync.py.bak-2026-10-18-marwa-task2`

**التحقق البنيوي:** `py_compile` للملفات التسعة (الجديدة + المعدّلة) ⇒ خروج 0 بلا أخطاء.
**لم يُلمس:** `G:\ai\codex\LayanStoreERP` (قراءة فقط) • `mcp\pos-reader\server.py` • أي `.db` (لا حذف ولا كتابة) • `.env`/أسرار • نسخ Elnagar للمنسّق.

---

## 7) ملاحظات ومخاطر وقرارات

1. **قرار أمان (تغيير سلوك مقصود):** `data_healer._auto_tag` كان يكتب `material_type/operation_type` على النسخة الميتة. بعد الربط صارت الكتابة تمر بـ`open_readwrite(approved=False)` ⇒ **مرفوضة افتراضيًا** برسالة صريحة. لتفعيلها على الحي يلزم اعتماد المالك + `POS_LIVE_WRITE=1`.
2. **`scripts\backup_pos.py` (P1 عاجل):** ينسخ النسخة الميتة، فالنسخ الاحتياطية الحالية تحفظ صفر أرصدة. موصى بربطه بالطبقة المركزية في جولة تالية.
3. **`mcp\pos-reader\check_financial_parity.py`:** يستخدم `sqlite3.connect("pos_data.db")` نسبيًا (حسب cwd) — مسار غير آمن؛ P1.
4. **`fix_correct_db.py`:** فيه كتابة مباشرة على القاعدة الحية (سكربت تاريخي) — لا يُعاد تشغيله إلا بمراجعة.
5. **الخصوصية:** بعض صفوف `clients.name` في القاعدة الحية **هي أرقام هواتف** كنص، وردود فارس/سلمى تطبعها كما هي (قاعدة المشروع: لا أرقام هواتف). سكربتنا الموحّد يحجبها (`mask_phone_like`)، والوكلاء لم يُعدّلوا في هذه النقطة (خارج نطاق الربط) — P1.
6. **الطزاجة:** بيانات القاعدة الحية آخر طلب **#334 / 2026-10-16** (المصدر لم يستقبل جديدًا بعد ذلك حتى لحظة التقرير 2026-10-18 00:35).
7. **حد صريح في التحقق:** لم أستطع التحقق من أن نسخة Elnagar للمنسّق هي التي يخدم بها «شات مروة» فعلاً — لذلك لم ألمسها؛ ربطها بالطبقة خطوة P1 بعد تأكيد الـ lead.
8. **إصلاح باج الإشارة (قرار المالك 2026-10-18):** كان `mobile_local_api_server.py:206,340` و`firebase_mirror_from_pos.py:64` يستخدمان `balance < 0` فتُرجع المديونيات 0 دائمًا (كل الأرصدة موجبة). عُدّل إلى `balance > 0` ليطابق تعريف `app.py:1655/1712`. نسخ `.bak-2026-10-18-signfix` أُخذت لكل ملف؛ تحقق الـ Lead: py_compile=0، الفرق vs `.bak` محصور في الشرط فقط (8+2 سطور)، و`balance > 0` ⇒ 4 مدينين / 1040.0 مقابل `balance < 0` ⇒ 0، وصفر `balance < 0` متبقٍّ في `Elnagar POS\*.py`. (`app.py`/`database.py` لم يُلمسا — قرار المالك: توثيق فقط حاليًا.)

---

## 8) الجولة الموالية (marwa-merge — 2026-10-18 ليلًا): بنود P1 أُغلقت

تنفيذًا لاعتماد المالك «نفّذ المراحل 1→2→3 العاجلة» (بعد تقرير فحص الميثاق الموحد v3):

| البند | الحالة | التفاصيل |
|---|---|---|
| `scripts\backup_pos.py` (البند 2 أعلاه — عاجل) | ✅ أُغلق | SRC_DB من `LIVE_DB_PATH` في `.env` + رفض صريح للنسخة المتجمدة؛ تشغيل حي 05:17 + **المهمة المجدولة 06:00 اشتغلت بالإصلاح** (56/58/45) |
| `cloud\schema_migrator.py` | ✅ أُغلق | الهدف المحلي = الحي عبر هذه الطبقة (`db_path()`) + بوابة `POS_LIVE_WRITE=1` لأي DDL + تحقق mode=ro + فشل سحابي أنيق؛ ترحيل 004 نُسخ للمستودع + بذر السجل من سجل مجلد الحي (pending=0) |
| `tools\laptop_sync.py` | ✅ أُغلق (بوابة عقدة — لا ربط بالطبقة عمدًا) | `--pull-all`/`--restore-env` مرفوضان على WORKSHOP — مرآة اللابتوب هدف مشروع لكنها ليست هدفًا ورشيًا (قرار 70)؛ `--status` صار واعيًا بالعقدة |
| `mcp\pos-reader\check_financial_parity.py` | ✅ أُغلق | مسار مطلق صريح + mode=ro + رفض إنشاء قاعدة — **PASS حيًا** (الأداة = الدالة الرسمية) |
| النسخة القديمة بجذر المستودع | ✅ معزولة | `backup\stale_isolated_2026-10-18\` مع README — جذر المستودع خالٍ من أي `pos_data.db` |
| إخفاء أرقام الهواتف في ردود فارس/سلمى (البند 5) | ⬜ يتبقى | الحل جاهز (`mask_phone_like` بهذه الطبقة) — جولة قادمة |
| نسخ مجلد الحي من الأدوات/الوكلاء → الطبقة (البند 7) | ⬜ يتبقى | مؤجل بقرار task-2 |

إصلاح إضافي ضمن الجولة: مسار هذه الطبقة في كتل الاستيراد صار نسبيًا في 6 ملفات (كان مطلقًا — كسر صامت محتمل على اللابتوب)، و`psycopg2-binary 2.9.13` رُكّب في `.venv` (معلن في requirements.txt).
السجل الكامل: `memory/decisions_log.md` (2026-10-18 — جولة marwa-merge).