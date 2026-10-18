# 🗄️ العمارة الحقيقية لقواعد البيانات — مشروع النجار برنت / LayanStoreERP

**المهمة:** `task-1` (المالك: vision) — إثبات المسار الرسمي الوحيد (Single Source of Truth) الذي يقرأ/يكتب منه النظام الحي.
**تاريخ الفحص:** 2026-10-18 (00:14–00:30 بتوقيت القاهرة) — كل رقم هنا مقيس الآن، لا منقول من ذاكرة.
**القاعدة الحاكمة:** قراءة فقط داخل `G:\ai\codex\LayanStoreERP` — لم يُعدَّل أي ملف هناك. لا كلمات مرور ولا مفاتيح في هذا التقرير.

---

## 1) الحكم النهائي في سطر واحد

> **النظام الحي = `G:\ai\Elnagar POS` (Python/Eel + Flask)، وقاعدته `G:\ai\Elnagar POS\pos_data.db`.**
> **PostgreSQL `layan_erp` + مشروع `LayanStoreERP` = فرع ميت (Dead End)** — خدمة PostgreSQL شغّالة، لكن التطبيق نفسه لا يعمل، وبياناتها متجمدة عند 24/09/2026.

---

## 2) الاتصال الحرفي

| البند | القيمة |
|---|---|
| **الاتصال الحرفي (URL)** | `jdbc:postgresql://localhost:5432/layan_erp` |
| المصدر | `src\main\resources\application.properties` سطر 14 (معدّل 24/09/2026) |
| **نسخة البناء (target\classes)** | **نفس الاتصال حرفيًا** — لا اختلاف بين src و target\classes |
| محرّك | PostgreSQL 18.3 (x86_64-windows)، الخدمة `postgresql-x64-18` — Running/Automatic |
| قاعدة البيانات | `layan_erp` — موجودة، حجمها 11 MB، **47 جدولًا** في schema `public` |

**الاتصال الثاني داخل الكود (نفس القاعدة):** `src\main\java\com\layan\erp\db\Database.java` سطر 20:
`config.setJdbcUrl("jdbc:postgresql://localhost:5432/layan_erp")` — أي أن الـ helper القديم (الذي تستدعيه كل الـ controllers) أيضًا على PostgreSQL، **لا SQLite**.

### ملفات الإعداد — مين الفعّال ومين بقايا

| الملف | المحتوى | الحالة |
|---|---|---|
| `src\main\resources\application.properties` | port 18080 + `jdbc:postgresql://localhost:5432/layan_erp` | ✅ **الفعّال** (Spring Boot يقرأ هذا الاسم افتراضيًا) |
| `target\classes\application.properties` | مطابق لـ src حرفيًا (43 سطر) | نسخة بناء، لا اختلاف |
| `src\main\resources\application_new.properties` | port **9090** + `jdbc:h2:mem:layan_erp` (H2) | ❌ **بقايا ميتة** — Spring Boot لا يحمّله (الاسم غير قياسي)، لا يوجد فيه أي profile |
| `Layan ERP apk\src\main\resources\application.properties` | نفس اتصال PostgreSQL | مشروع فرعي/نسخة APK، ليس هو المُشغَّل |
| أي `*.yml` / `*.yaml` | لا يوجد | — |

---

## 3) هل توجد عملية حية الآن؟ (القياس المباشر)

| الفحص | النتيجة |
|---|---|
| `Get-Process java,javaw` | **لا توجد أي عملية Java على الجهاز** — صفر |
| منفذ **18080** (Spring Boot حسب `server.port`) | **لا شيء يستمع** |
| منفذ **9090** (بوابة `ServerApp` القديمة) | **لا شيء يستمع** |
| منفذ **5432** | يستمع — PID 5708 (`postgres`)، خدمة `postgresql-x64-18` Running |
| `pg_stat_activity` على `layan_erp` | **الاتصال الوحيد الموجود = اتصال `psql` بتاعي** (application_name=psql) — لا يوجد أي اتصال `PostgreSQL JDBC Driver` |
| منفذ **8888** (Eel / واجهة المتصفح) | يستمع — PID 3788 (`pythonw`، بدأ 17/10/2026 23:57:01) |
| منفذ **7777** (Flask API للموبايل) | يستمع — نفس العملية PID 3788 |

**معنى ده:** PostgreSQL شغّال كخدمة (Service)، لكن **مفيش أي تطبيق متصل بيه** — يعني «الحي» في PostgreSQL هو الخدمة فقط، مش النظام.

كود التشغيل الفعلي في الباك إند:
- `pom.xml` → `spring-boot-maven-plugin` → `mainClass = com.layan.erp.main.ServerApp` (سطر 127).
- `ServerApp.java` سطر 64: `int httpPort = 9090;` (بوابة `com.sun.net.httpserver` قديمة) + سطر 76-77 يقلع Spring Boot في thread خلفي على **18080**.
- أي: تشغيل واحد يفتح 9090 + 18080 في نفس الـ JVM. الاتنين مقفولين الآن.

---

## 4) المصادر الثلاثة — المقارنة الحاسمة

| # | المصدر | المسار / الاتصال | آخر تاريخ بيانات | عملاء | طلبات | حركات | يعمل الآن؟ |
|---|---|---|---|---|---|---|---|
| أ | **PostgreSQL** `layan_erp` | `jdbc:postgresql://localhost:5432/layan_erp` | **24/09/2026 18:57** (customer_ledger) | **11** | 8 (transactions) | 8 | ⚠️ الخدمة تعمل / **التطبيق ميت** (لا java، لا 18080) |
| ب | **النظام الحي (Elnagar POS)** | `G:\ai\Elnagar POS\pos_data.db` | **16/10/2026 20:39** (txn #482) | **56** | **58** | **44** | ✅ **نعم — شغّال فعلًا** |
| ج | **نسخة مساحة الوكلاء (متجمدة)** | `G:\ai\Naggar Print POS Agent\pos_data.db` | **03/09/2026** | **52** | **50** | **41** | ❌ لا — نسخة قديمة، بلا أي كتابة |
| ج2 | نسخة الكتابة المعزولة | `G:\ai\Naggar Print POS Agent\_sandbox_pos_writer\pos_data.db` | 03/09/2026 (ملف 16/10 23:08) | 52 | 50 | 41 | ❌ (هدف كتابة، مش مصدر حقيقة) |
| د | **مرآة سحابية Supabase** | `G:\ai\Elnagar POS\cloud\supabase_sync.py` | آخر دفع **17/10/2026 19:45 UTC** = 21:45 القاهرة | 56 | 58 | 44 | ✅ مرآة **قراءة فقط** للحي (opens `mode=ro`) |
| هـ | مرآة Google Sheets | `google_sheets_sync.log` | حتى طلب **#334** في 16/10 19:23 | — | — | — | ✅ كانت شغّالة (Realtime sync) |

### أهم نتيجة: أي مصدر يحمل الأحدث؟
**ب (Elnagar POS)** — بفرق واضح: عملاء 56 مقابل 52 و11، وطلبات 58 مقابل 50 و8، وحركات حتى 16/10 مقابل 03/09 و24/09.

### أدلة الفروق بالأرقام
```
PostgreSQL layan_erp : customers=11  transactions=8  customer_ledger=8  obligations=2  products=56
                       آخر ledger 2026-09-24 18:57 | آخر obligation 2026-09-22
Elnagar POS (حي)     : clients=56  orders=58  order_items=104  transactions=44  operation_logs=201
                       آخر order #334 (16/10 16:22) | آخر txn #482 (16/10 20:39)
Agent root (متجمد)   : clients=52  orders=50  transactions=41  max order id=323 (31/08/2026)
_sandbox_pos_writer  : clients=52  orders=50  transactions=41  (نفس الجدول القديم)
```

**ملاحظة فنية مهمة:** النسخة المتجمدة في جذر مساحة الوكلاء فيها **9 جداول فقط** (بنية POS القديمة: clients/orders/transactions/…)، بينما الحي و sandbox فيهما **32 جدولًا**. يعني هي مش «نسخة أحدث ناقصة»، هي **snapshot أقدم ببنية أقدم**. ملفها اتلمس آخر مرة 16/10 22:53 لكن البيانات جواها واقفة عند 03/09 — و`pos_data.db-wal` صفر بايت من 14/10 (مفيش أي كتابة).

---

## 5) إثبات إن الحي بيقرأ فعلًا من `G:\ai\Elnagar POS\pos_data.db`

ده أقوى دليل، ومقيس مباشرة من الـ API الشغّال:

**استدعاء حي** `GET http://127.0.0.1:7777/api/clients`:
```json
{"success": true, "customers": [ ... 56 عميلًا ... ]}
```

**نفس الاستعلام على الملفات الثلاثة (قراءة SQL مباشرة):**

| المقياس | Postgres | Elnagar POS (حي) | Agent root | sandbox |
|---|---|---|---|---|
| عدد العملاء | 11 | **56** | 52 | 52 |
| `SUM(clients.balance)` | 0 | **1040.0** | 0.0 | 0.0 |

الـ API رجّع **56 عميلًا**، ودي القيمة الوحيدة المطابقة لـ `G:\ai\Elnagar POS\pos_data.db` (52 و11 و0 كلهم اختلفوا) → **الحي يقرأ من ملف Elnagar POS، قطعًا.**

كمان الكود يثبت الاتجاه:
- `G:\ai\Elnagar POS\database.py` سطر 7: `DB_NAME = "pos_data.db"` (مسار **نسبي** — يعني قاعدة البيانات = ملف في مجلد تشغيل العملية).
- `G:\ai\Naggar Print POS Agent\.env` فيه مفتاح صريح:
  `LIVE_DB_PATH = "G:\ai\Elnagar POS\pos_data.db"` — يعني حتى مساحة الوكلاء **معرِّفة الحي صح**، والكود بيقرأ منه:
  `tools\laptop_sync.py` سطر 399: `live = (env.get("LIVE_DB_PATH") or "").strip()` ثم يفتحه `mode=ro`.
- `scripts\parity_watchdog.py` سطر 48: `DEFAULT_LOCAL_DB = r"G:\ai\Elnagar POS\pos_data.db"`.
- `mcp\pos-writer\server.py` سطر 23: `LIVE = r"G:\ai\Elnagar POS"` — والهدف الافتراضي `_sandbox_pos_writer` إلا لو `POS_WRITER_TARGET=live`.

---

## 6) رقم المالك: إجمالي المديونيات = 1040 جنيه ✅ (مؤكَّد من مصدرين)

**المصدر 1 — الملف الحي (SQL):**
```
id 107 | +20 10 90357093   | Retail    | 350
id 108 | اسراء هلال          | Wholesale | 250
id  63 | زينب               | Wholesale | 240
id 109 | 201096899777      | Retail    | 200
                          المجموع = 1040.0 جنيه
```

**المصدر 2 — الـ API الحي (`/api/clients`، مجموع `total_debt`):**
```
clients returned : 56
sum(total_debt)  : 1040
أصحاب المديونية  : 107=350 | 109=200 | 108=250 | 63=240
```

**المقابل في PostgreSQL: صفر.** كل `customers.current_balance` = 0 (وحتى آخر حركة ledger 24/09 فيها `balance_after = 0.00`). يعني لو الوكلاء بصول على PostgreSQL، الرقم الحي (1040) **مش موجود خالص** — ده بالظبط شكل «انفصام البيانات».

### أسماء جداول المديونيات/العملاء وعدد الصفوف

**في القاعدة الحية (SQLite — Elnagar POS):**

| الجدول | الدور | الصفوف |
|---|---|---|
| `clients` | العملاء + عمود `balance` (المديونية) | **56** |
| `transactions` | الحركات (Income/Expense/Payment) وفيه `category = 'Debt Collection'` للتحصيل | **44** |
| `orders` / `order_items` | الطلبات وبنودها | **58** / **104** |
| `operation_logs` | سجل العمليات (تدقيق) | **201** |
| `daily_shifts` | الورديات | 1 |

**في PostgreSQL `layan_erp` (47 جدولًا، الأسماء PascalCase قديمة + snake_case جديدة):**

| الجدول | الدور | الصفوف |
|---|---|---|
| `customers` | العملاء + `current_balance` | **11** (4 منهم `is_deleted=true`) |
| `customer_ledger` | دفتر حركات العملاء (`transaction_type`, `amount`, `balance_after`) | **8** |
| `transactions` + `transaction_items` | الفواتير/المبيعات | **8** / **10** |
| `obligations` | الالتزامات (إيجار/فواتير) | **2** (450 + 6000 = 6450 جنيه) |
| `supplier_ledger` / `suppliers` | الموردون | 4 / 6 |
| `pending_invoices` | فواتير معلّقة | 4 |
| `products` / `staff` / `branches` | أصناف/موظفين/فروع | 56 / 4 / 3 |

> ⚠️ **لا يوجد جدول اسمه `debts` في أي من القاعدتين.** المديونية في الحي = `clients.balance`، وفي PostgreSQL = `customers.current_balance` + `customer_ledger`.

---

## 7) دليل من السجلات (كما طلبت المهمة)

**سجلات Spring Boot تثبت إن الباك إند كان على PostgreSQL:** ملفات `spring_boot_probe.out` (26/04/2026) و`run_output.txt` (20/04) و`run_output_debug_2.txt` (07/05) — كلها:
```
INFO com.zaxxer.hikari.pool.HikariPool : HikariPool-1 - Added connection org.postgresql.jdbc.PgConnection@...
INFO ... : Initialized JPA EntityManagerFactory for persistence unit 'default'
?? Layan ERP — Spring Boot + PostgreSQL
?? Server running on port 9090
?? Database: layan_erp (PostgreSQL)
```
(بوابة 9090 + Spring 18080، والاتصال بقاعدة `layan_erp`.)

**سجلات النظام الحي (`G:\ai\Elnagar POS\backend_crash.log` — آخر الملف):**
```
==================================================
Backend Started: 2026-10-17 23:57:09.564383
==================================================
[OK] Database Initialized Successfully.
Starting Mobile Flask API on port 7777...
 * Running on http://127.0.0.1:7777
Starting Elnagar POS in Independent Window...
INFO:geventwebsocket.handler:127.0.0.1 - - [2026-10-18 00:21:49] "GET /index.html HTTP/1.1" 200 293327
INFO:werkzeug:127.0.0.1 - - [18/Oct/2026 00:21:49] "GET /api/clients HTTP/1.1" 200 -
```
ده **سجل مباشر من لحظة الفحص** (00:21:49 اليوم) — النظام الحي بيخدم `/api/clients` بنجاح الآن.

**سجل المرآة السحابية (`G:\ai\Elnagar POS\cloud\supabase_sync.log`):**
```
2026-10-17T19:45:06+00:00 [INFO] push_mirror: clients rows=56 upserted=56
2026-10-17T19:45:07+00:00 [INFO] push_mirror: orders rows=58 upserted=58
2026-10-17T19:45:07+00:00 [INFO] push_mirror: order_items rows=104 upserted=104
2026-10-17T19:45:07+00:00 [INFO] push_mirror: transactions rows=44 upserted=44
```
الأرقام **مطابقة حرفيًا** لمحتوى الحي (56/58/104/44) → السحابة **مرآة**، مش مصدر مستقل.

**مرآة Google Sheets (`google_sheets_sync.log`):** `Realtime sync order #334` في 16/10 19:23 — آخر طلب في الحي (#334) بالظبط.

**تقرير التكافؤ التاريخي (`memory\reports\parity-LATEST.md` — 13/10/2026):** «✅ clients/products/orders/order_items/transactions: مطابق» مع `clients count=52` — يعني في 13/10 كانت النسختان متطابقتين (52 عميلًا)، وبعدها كبر الحي لـ 56 والنسخ القديمة وقفت.

---

## 8) ليه فيه «تلات مصادر»؟ (العلاقة بين LayanStoreERP والمشروع القديم)

الخلاصة: **مش انفصام في نظام واحد — دول نظامان مختلفان + نسخة مجمّدة + مرآة.** التفصيل بالأدلة:

### 8.1 `G:\ai\codex\LayanStoreERP` = محاولة كتابة ثانية (Rewrite) اتعملت لمحل ليان ستور وهُجرت
- آخر **commit** في Git: `04d010f — 2026-09-25 23:37` (اللي قبله 22/09). آخر تعديل ملفات `src`: **25/09/2026 00:55** (`ServerApp.java`). يعني المشروع **ساكن من 3 أسابيع**.
- دليل «انتقال لم يكتمل» — `POSTGRES_MIGRATION_FINALIZATION.md` بنصّه:
  > «The repository is not PostgreSQL-only yet… Legacy SQLite code is still compiled into the application and is still referenced by important business flows.»
  > «PostgreSQL is active, but the user-facing workflow path is still partially dependent on legacy SQLite code.»
  ويسرد إن `SalesController` / `InventoryController` / `CustomerController` / `InvoicesController` … لسه على `Database.connect()`، وإن `customers.html` بتبعت `POST` والـ Spring مستني `PUT` (mismatch)، وإن `pos.js` بتستخدم `/api/sales/create` القديم.
- `MIGRATION_PAGE_BY_PAGE_PLAN.md` كمان بنصّه: «Do not migrate all pages at once… do not start with POS, invoices, accounting» — خطة ترحيل **صفحة بصفحة** اتوقفت في نصّها.
- `DATA_DISAPPEARANCE_AUDIT.md` (01/05/2026) اكتشف سببًا إضافيًا للارتباك: كان فيه **نسختان** من نفس المشروع وقتها — الأصل `G:\ai\codex\LayanStoreERP` والنسخة المشغّلة `g:\ai\LayanStorFinal\LayanStoreERP` (متأخرة commit)، فالصفحات كانت بتطلع فاضية رغم إن الداتا موجودة. **دلوقتي `G:\ai\LayanStorFinal` مش موجود أصلًا** (`Test-Path` = False) — يعني اتشال/اتدمج، والنسخة الباقية هي codex.
- `CLOUD_MIRROR_AUDIT.md`: مجلد `cloud-mirror\` (Next.js) مربوط بـ `firebase.json` → `"public": "cloud-mirror/out"`، وفيه روابط hardcoded على `http://localhost:9090` — واجهة نشر، مش قاعدة بيانات. و`firebase-key.json` موجود (17/05) لكن **مفيش أي عملية Firebase شغّالة الآن** (لا java أصلًا). يبقى: **مسار سحابي Firebase = بقايا غير فعّالة**، عكس Supabase اللي بيدفع فعلًا من النظام الحي.
- المحتوى نفسه يؤكد إنه لمحل ليان: العملاء `عميل نقدي عابر - مروه فاشون`، `عميل نقدي عابر - ليان ستور`، و`total_purchases` 1490 / 310 — **مش ورشة النجار برنت**.

### 8.2 `G:\ai\Elnagar POS` = النظام الإنتاجي الحقيقي للورشة
Python + Eel (واجهة على 8888) + Flask API (7777)، شغّال من 17/10 23:57، وDB حي، ومرآة Supabase، ومزامنة Google Sheets — ده اللي المالك بيشتغل عليه فعلًا، وده اللي رقم 1040 طلع منه.

### 8.3 `G:\ai\Naggar Print POS Agent` = مساحة الوكلاء (مش مصدر حقيقة)
- فيها **نسخة قديمة** في الجذر (`pos_data.db`) + **نسخة معزولة للكتابة** (`_sandbox_pos_writer`) — و`mcp\pos-writer\server.py` بيقول بالنص: *«الهدف الافتراضي نسخة الاختبار (_sandbox_pos_writer)؛ الحي يتطلب POS_WRITER_TARGET=live (بأمر المالك فقط)»*.
- **ده بالظبط مصدر الإحساس بالانفصام:** الوكلاء بيكتبوا في `_sandbox` أو بصول على `pos_data.db` القديم في الجذر، بينما النظام الحي بيكتب في `G:\ai\Elnagar POS`. حتى `.env` عندهم مضبوط صح (`LIVE_DB_PATH`) — لكن الأدوات الافتراضية + النسخة القديمة في الجذر بتخلّي القراءة تروح لمكان تاني.
- فيه أيضًا `scripts\parity_watchdog.py` — «حارس التطابق» اللي المالك عمله بنفسه في 13/10 لمقارنة الحي بالمرآة؛ تقريره الأخير «مطابق» (13/10 16:11) — يعني كان في وعي بالمشكلة ومحاولة حل.

### 8.4 `G:\ai\Elnagar POS\Backups` = 59 جيجا
ملاحظة من `STUDY_INDEX.md`: `firebase_importer_loop.py` بيكتب نسخة DB كل ~12 ثانية في نفس المجلد (303,653 ملف). **دي ليست مصدر بيانات** — ديه نسخ مكرّرة، ولازم تتجاهل في أي جرد.

---

## 9) الخريطة النهائية (مين يقرأ من مين)

```
        ┌──────────────────────────────── النظام الحي ────────────────────────────────┐
        │  pythonw PID 3788 (بدأ 17/10 23:57)                                        │
        │  Eel → :8888 (واجهة المتصفح)      Flask → :7777 (API الموبايل)              │
        │  database.py : DB_NAME = "pos_data.db" (نسبي)                               │
        └───────────────┬────────────────────────────────────────────────────────────┘
                        │ قراءة/كتابة
                        ▼
        G:\ai\Elnagar POS\pos_data.db   ← ★ المصدر الوحيد للحقيقة ★
        (56 عميل | 58 طلب | 44 حركة | مديونيات = 1040 ج.م)
                        │
        ┌───────────────┼─────────────────────────────┐
        │ مشتقات للقراءة فقط                           │
        ▼                                             ▼
  Supabase (مرآة، آخر دفع 17/10 21:45)      Google Sheets (Realtime حتى #334)
                        ▲
                        │ LIVE_DB_PATH = "G:\ai\Elnagar POS\pos_data.db"
        G:\ai\Naggar Print POS Agent
        ├── pos_data.db .................. ❌ نسخة مجمّدة (52 عميل، تنتهي 03/09) — الفخ
        ├── _sandbox_pos_writer\pos_data.db ❌ هدف الكتابة الافتراضي للأدوات
        └── mcp/pos-writer, laptop_sync, parity_watchdog ... كلهم بيشاوروا على الحي

        محور منفصل تمامًا (ميت):
        G:\ai\codex\LayanStoreERP  ──X──▶  jdbc:postgresql://localhost:5432/layan_erp
        (آخر commit 25/09 | لا java شغّال | لا 18080 | 11 عميل | مديونيات = 0 | آخر بيانات 24/09)
```

---

## 10) توصيات فورية (بدون أي كتابة في الأنظمة)

1. **أي وكيل يتعامل مع أرقام الورشة لازم يقرأ من `G:\ai\Elnagar POS\pos_data.db`** (أو يستخدم `LIVE_DB_PATH` من `.env`) — **لا** من `pos_data.db` في جذر مساحة الوكلاء.
2. **`pos_data.db` في جذر `Naggar Print POS Agent` لازم يتعلّم (mark) كملف قديم/غير حي** أو ينقل لأرشيف — وجوده في الجذر هو سبب لبس «الـ workspace».
3. **القرار في `LayanStoreERP`:** إما يُستأنف الترحيل (خطة الصفحة-بالصفحة موجودة) وإما يُعلن أرشيفًا صريحًا. حاليًا هو **مش حي ولا مصدر بيانات** — مجرد خدمة PostgreSQL شغّالة على الفاضي.
4. **قبل أي تنظيف:** لا تُمس `G:\ai\Elnagar POS\pos_data.db` ولا `Backups` — ده الحي.
5. **ورقة المالك «1040 جنيه» صحيحة 100%** ومصدرها النظام الحي (4 عملاء: 107 و109 و108 و63).

---

## 11) ملحق: أوامر الفحص المُستخدَمة (لإعادة التحقق)

```powershell
# 1) مين شغّال على البورتات
Get-NetTCPConnection -State Listen -LocalPort 18080,5432,9090,8888,7777 | Select LocalPort,OwningProcess
Get-Process java,javaw,postgres,pythonw | Select Id,ProcessName,StartTime

# 2) هل الجلسة بتقرأ الحي؟
$r = Invoke-RestMethod 'http://127.0.0.1:7777/api/clients'; $r.customers.Count
($r.customers | Measure-Object total_debt -Sum).Sum      # => 56 , 1040

# 3) PostgreSQL (كلمة المرور تُقرأ من application.properties بلا طباعة)
& 'C:\Program Files\PostgreSQL\18\bin\psql.exe' -U postgres -h localhost -d layan_erp -c "\dt"

# 4) الـ SQLite (قراءة فقط)
python -c "import sqlite3;print(sqlite3.connect(r'file:G:\ai\Elnagar POS\pos_data.db?mode=ro',uri=True).execute('SELECT COUNT(*),SUM(balance) FROM clients').fetchone())"
```

**قيود التزمت بها:** لم أطبع كلمة مرور ولا مفتاح؛ لم أعدّل أي ملف داخل `LayanStoreERP` (قراءة فقط)؛ كل الأرقام أعلاه مقيسة في هذه الجلسة من ملفات/خدمات فعلية.