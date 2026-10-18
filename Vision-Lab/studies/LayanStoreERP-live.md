# 🏗️ ملخص معماري: LayanStoreERP (الأصل الحي — codex)

> **دراسة معمارية** أعدّها وكيل المذاكرة تحت إدارة «فيجن» — التاريخ: 2026-10-18
> الموقع: `G:\ai\codex\LayanStoreERP` — المستودع المرجعي الوحيد المعتمد للنسخة الحية.
> الحالة الموثقة: مستودع Git نظيف (0 تغييرات، فرع `main`)، آخر commit `04d010f` بتاريخ **2026-09-25**: «WhatsApp Chat Pro real-time sync, Drawer balance radar stats, Accounting & Supplier Ledger V4.0, Procurement replenishment, and Shift hardening» (تحقق مباشر من `git log` + `git status` — قراءة فقط).
> حجم الشيفرة: **226 ملف Java** في `src` (221 رئيسية + 5 اختبارات — إحصاء فعلي)، و**52+ ملف واجهة** في `src/main/resources/web`.
> منهجية: قراءة فقط بلا أي تعديل أو تشغيل؛ كل استنتاج مرتبط بملف قُرئ فعلًا. أسرار المشروع (توكن Telegram، مفاتيح Firebase، كلمات مرور DB، `keystore.jks`، `firebase-key.json`) **لم تُطبع قيمها** — تُذكر كمواقع حساسة فقط.

---

## 1) الغرض الوظيفي

نظام ERP متكامل متعدد الفروع لإدارة نقاط البيع (POS)، المخزون بالمتغيرات (لون/مقاس)، المحاسبة ودفاتر الموردين، والموارد البشرية والحضور والورديات، مع موبايل موظفين (APK) ومرآة سحابية للإدارة. يخدم ثلاث كيانات تجارية: **Marwa Fashion** و**Layan Store** و**Al-Najjar Print** (المصدر: `AGENTS.md` أسطر 4–5).

---

## 2) نقاط الدخول وطريقة التشغيل

المشروع **هجين بوابة مزدوجة** — نقطتا دخول في نفس العملية (المصدر: `pom.xml` + `src/main/java/com/layan/erp/main/ServerApp.java` + `LayanErpApplication.java`):

| طبقة | الملف | المنفذ | الدور |
|---|---|---|---|
| **البوابة القديمة (JDK HttpServer)** | `com.layan.erp.main.ServerApp` | **9090** HTTP + **8443** HTTPS | ~**179 مسارًا مسجلًا يدويًا** في `setupRoutes()` (103 استدعاء `server.createContext` + 76 استدعاء `register()` — عدّها فعليًا) يخدم واجهات POS/المخزون/المحاسبة/الشات legacy من `src/main/resources/web` |
| **Spring Boot الحديث** | `com.layan.erp.LayanErpApplication` | **18080** (`application.properties:7`) | REST controllers حديثة (JPA/PostgreSQL)، تُوَجَّه لها الطلبات عبر `ProxyHandler` المسجّل على `/api/` في نهاية `setupRoutes` (ServerApp سطر 482: «Smart Gateway Reverse Proxy») |

**تسلسل إقلاع `ServerApp.main` (مقروء من الملف):**
1. فرض توقيت القاهرة `Africa/Cairo` لكل عمليات قواعد البيانات والسجلات.
2. «درع انهيار» عام: أي استثناء غير معالَج في أي Thread يُطبع ويُرسل تنبيهًا فوريًا للإدارة عبر Telegram (يعتمد على توكن مكهرب داخل `TelegramController`).
3. `Database.initializeTables()` + `fixAttendanceAndRequests()` + `seedData()`.
4. تشغيل **Spring Boot** في Thread خلفي على 18080.
5. تشغيل محرّك مزامنة Firebase: `FirebaseSyncService.start()` + `FirebaseListenerService.start()`.
6. تشغيل محرّك Telegram Long-Polling: `TelegramController.startPollingEngine()`.
7. رفع `HttpServer` على 9090 و`HttpsServer` على 8443 (عبر `keystore.jks` — بكلمة مرور ثابتة ضعيفة داخل الكود؛ الـHTTPS مطلوب لتفعيل كاميرا الماسح).
8. حلقة `while(true)` تُبقي العملية حية.

**طريقة التشغيل (سطر الأوامر):**
- `run.bat` (مقروء كاملًا): حلقة انتظار حتى يوجد `target\LayanStoreERP-1.0-SNAPSHOT.jar` ثم تشغيله عبر **`tools\jdk21\bin\java -jar`**.
- `_backend.bat` (مقروء كاملًا): تشغيل مباشر من المصدر عبر `apache-maven-3.9.6\bin\mvn.cmd exec:java -Dexec.mainClass=com.layan.erp.main.ServerApp`.
- `mainClass` الموثّق في `pom.xml:127` هو `com.layan.erp.main.ServerApp` مع `spring-boot-maven-plugin` (repackage، Fat JAR).
- متطلبات التشغيل: PostgreSQL محلي `layan_erp` على 5432 + متغير بيئة `DB_PASSWORD` (يوجد fallback ثابت داخل `Database.java:24` و`application.properties:16` — مخاطرة أمنية أدناه). ويشهد `WINDOWS_LOCAL_SETUP_REPORT.md` أن JDK 21 مضمّن في `tools\jdk21` وMaven 3.9.6 في `apache-maven-3.9.6` وأن Maven compile/test نجحا (22 اختبارًا).
- سكربتات تشغيل أخرى في الجذر (وجودها من الجرد دون قراءة كاملة): `start-production.bat`, `build_and_run.bat`, `dev-run.bat`, `mvn_run.bat`, `headless-run.bat`, `Start-LayanERP.bat`, `LayanLauncher.vbs`/`RunSilent.vbs`, `launcher.ps1`.

---

## 3) الهيكل العام

```
codex\LayanStoreERP\
├── pom.xml                     ← Maven + Spring Boot 3.2.0 (Java 17)
├── src\main\java\com\layan\erp\
│   ├── LayanErpApplication.java (نقطة Spring) + RunSQL.java
│   ├── main\ServerApp.java        (بوابة JDK — 14,811 سطرًا)
│   ├── config\ (6)  : GlobalExceptionHandler, NgrokLifecycleManager, SystemAdminBootstrap, WebConfig, WebSocketConfig, ZeroDB
│   ├── controller\(54): مسارات HTTP قديمة (HttpHandler) + REST حديثة
│   ├── service\ (24) : Firebase*, Procurement, SupplierFinancial, PosSale, Attendance, Gemini, Sentinel...
│   ├── entity\ (39) / repository\ (40) : طبقة JPA كاملة
│   ├── dto\ (~47 في 10 حزم فرعية: auth, barcode, customer, mobile, procurement, purchase, security, staff, supplier)
│   ├── db\ (3)      : Database (HikariCP/PostgreSQL), CheckDB, DbDiagnose
│   └── utils\ (4)   : BarcodeEngine, MigrationUtils, SecurityUtils, Utils
│   ⚠️ + ملف شارد `TelegramController.java` (171 سطرًا) في جذر src\main\java بلا حزمة (بقايا legacy مكررة لنسخة الحزمة) + ملف .fxml
├── src\main\resources\ : application.properties (+application_new.properties), db\migration (V11, V12 SQL), web\ (52+ ملف HTML/CSS/JS)
├── src\test\java\      : 5 اختبارات (MobileRestControllerTest, AttendanceServiceTest, HrRequestServiceTest, MobileAuthServiceTest, StaffCrudServiceTest)
├── cloud-mirror\       ← مرآة سحابية Next.js (تفصيل أدناه)
├── tools\              : jdk21 (JDK 21 مضمّن) + db (سكربتات backup/check/restore لـ PostgreSQL) + سكربتات عزل تنظيف
├── layan-erp---staff-edition\ : مشروع أندرويد (Gradle Kotlin DSL، حزم com.example.data/ui/utils) لتطبيق الموظفين
├── layan-staff-v4.apk  (47MB في الجذر) + مجلد "Layan ERP apk" (نسخة متداخلة كاملة بمصادر — ثنائي المصدر)
├── backups\postgres\   : نسخ SQL احتياطية (أدوات tools\db)
├── uploads\, lib\gson.jar, ngrok.exe (32MB), firebase-key.json ⚠️, keystore.jks ⚠️ (مكوّنان حساسان — لم يُقرأ محتواهما)
└── بيئات بناء مضمّنة: apache-maven-3.9.6, java-1.8.0-openjdk (قديم), .m2, .maven-user-home, .userhome, .userprofile, .qwen, .agents, target, bin, lib, scratch, maestro-main, .mvn, .github, .vscode
```

**cloud-mirror** (من `cloud-mirror/package.json` + `CLOUD_MIRROR_AUDIT.md`): مشروع **Next.js 16.2.3 (App Router) + React 19.2.4 + firebase-js 12.12 + Tailwind 4 + TypeScript**، بهيكل `src/app/admin/*` يضم **15 صفحة إدارية** (accounting, branches, customers, discounts, inbox, messages, payroll, procurement, products, promotions, reports, settings, staff, suppliers, transactions) + `src/lib/firebase.ts` (تهيئة Firestore من طرف العميل) + `NotificationCenter.tsx` + مجلد `out\` (تصدير ثابت يُرفع إلى Firebase Hosting حسب وثيقة التدقيق).

---

## 4) الوحدات الرئيسية (بالأدلة)

1. **POS والمبيعات والدرج**: `PosSaleService`, `PosInvoiceRestController`, `PosShiftRestController`, `PosDiscountRestController`, `SalesController`, `ShiftController`, `InvoicesController` + واجهات `pos.html/pos.js` — إصلاح درج الرصيد موثق في `POS_STOCK_SALE_DRAWER_FULL_FIX.md` (12/5/2026): كشف أن المخزون الحقيقي في `branch_stock` لا في `product_variants.stock`، وإصلاح تكرار `toggleDrawerBalance()`.
2. **المخزون متعدد الفروع**: `InventoryController/RestController`, كيان `InventoryStock` (البديل الإلزامي لـBranchStock المحظور بحكم `AGENTS.md:58-59,85-88`), `StockTransferController` (إنشاء/شحن/استلام تحويلات — ServerApp أسطر 188-194), `ShortagesController` + `ShortageRestController`.
3. **المشتريات والتموين (Procurement)**: `ProcurementService` (563 سطرًا — مقروء): اقتراحات إعادة تعبئة ذكية (نواقص PENDING أولًا ثم أصناف مخزونها ≤2) عبر `ReplenishmentSuggestionDTO`، دورة حياة أوامر الشراء (`V12__purchase_orders_and_replenishment.sql` يضيف order_status/expected_delivery_date + فهارس)، `PurchaseService` + مسار `/api/v2/purchases/bulk-import` في ServerApp.
4. **الموردون ودفاترهم — Supplier Ledger V4.0**: `SupplierFinancialService` (مقروء): إحصاءات عالمية (إجمالي دين، أكبر مورد، دفعات متأخرة >7 أيام) بـ`BigDecimal` و`@Transactional`؛ دفتر مزدوج INVOICE/PAYMENT بلقطات رصيد ومنع تكرار أرقام الفواتير — موثق ومختبر في `PURCHASE_SUPPLIER_LEDGER_VERIFICATION.md` (mvn test: 22 اختبارًا ناجحًا) + كيان `SupplierLedger` + `dto\supplier` (3 DTOs) + `SupplierLedgerRepository`.
5. **المحاسبة والخزينة (Ledger V4.0)**: `AccountingController/RestController`, `LedgerController` (Master Daily Ledger & Shift Engine V4.0: summary/generate/history/drilldown/shift-open/shift-close/eod-close/monthly-export — ServerApp أسطر 242-251), `FinancialEngine`, كيانات `DailyLedger/CashRegister/Savings/Obligation`, هجرة `V11__accounting_engine_pg_sync.sql` (petty_cash_log + أعمدة daily_ledgers + خزائن MAIN_SAFE/PETTY_CASH/BANK).
6. **الموارد البشرية والورديات**: `HRController/HRRestController/StaffRestController`, `AttendanceService` بقفل تشاؤمي وتسجيل حضور idempotent («تم تسجيل حضورك مسبقًا اليوم») وحساب ساعات عمل بالعربية — وثيقة `STAFF_ATTENDANCE_SHIFT_HARDENING.md` (1/5/2026) تسرد 14 ملفًا معدلًا، و`AttendanceServiceTest` موجود فعليًا في src\test.
7. **الدردشة الداخلية «WhatsApp Chat Pro» (أحدث commit)**: خلفية مزدوجة — `ChatRestController` (Spring REST للـinbox والعدادات — مقروء) و`ChatController/ChatMediaController` القداميان (ServerApp أسطر 289-330)؛ واجهة `chat-widget.js` **V6.0 WhatsApp Pro** (قائمة محادثات بعدّادات غير المقروء + رسائل صوتية بمؤقّت ومشغل مخصص) و`chat-widget.css`، وتبويب شات بنمط WhatsApp في `mobile.html` — وأحدث ملفات الشجرة (2026-09-25).
8. **الموبايل وحضور QR**: `MobileController/MobileRestController`, `MobileAuthService` (PIN/QR)، `AttendanceMobilePageController` + `/r?token=`، صفحات `mobile.html` و`attendance-mobile.html` — توثق `MOBILE_SYSTEM_AUDIT.md` حالة المسارات أثناء الهجرة (كثير منها كان 500 على Spring ثم أُعيد ربطه لاحقًا).
9. **Telegram**: `TelegramController` (1,547 سطرًا — مقروء جزئيًا): محرّك long-polling دائم (يمسح الويب هوك عند الإقلاع) + webhook + صندوق موافقة فواتير (`/api/telegram/inbox|approve|reject`) + سجل المالكين في `authorized_owners.txt` + تنبيه أعطال عالمي من `ServerApp`. ⚠️ **توكن البوت مدمج ثابتًا في السطر 19** (لم تُطبع قيمته).
10. **Firebase**: `FirebaseConfig` (يحمّل `firebase-key.json` من جذر التشغيل — لم يُقرأ الملف نفسه)، `FirebaseSyncService` (مقروء): طابور `Sync_Queue` يُسحب كل 5 ثوانٍ + تدقيق كل 30 دقيقة، تراجع تصاعدي حتى 10 محاولات، حذف ناعم بمستندات `B1_<table>_<id>` (افتراض الفرع 1 — موثق كـ«Future refactor»)، مع `FirebaseListenerService` و`FirebaseMigrationTool`.
11. **الباركود والطباعة**: `ProductBarcodeService` + `utils\BarcodeEngine` (ZXing): باركود حتمي من اسم عربي بنقل صوتي لاتيني + رموز قصيرة `ABC-0001` — موثق في `PRODUCT_BARCODE_ENGINE.md`؛ طباعة `/api/print` و`/api/print-batch` + `html5-qrcode.min.js` + `RemoteScannerController` (اقتران كاميرا هاتف كماسح POS) + 6 DTOs باركود.
12. **الأمان والصلاحيات**: `SecurityController/Service`, `PermissionsMatrix`, `SystemAdminBootstrap` (ينشئ حساب مدير نظام افتراضيًا عند أول تشغيل — مخاطرة أدناه), `ZeroDB` (تنظيف شامل TRUNCATE للجداول المالية — منفذ صيانة خطر)، مسارات `/api/security/*` في ServerApp (أدوار/صلاحيات/اقتران جهاز/تحقق إجراء).
13. **إضافات**: `GeminiService` (تكامل AI — بالجرد)، `SentinelService`, `NotificationService`, `WebConfig`, `GlobalExceptionHandler`.

---

## 5) المكتبات (من `pom.xml` — مقروء كاملًا)

- **الأساس**: `spring-boot-starter-parent 3.2.0` — إصدار `com.layan.erp:LayanStoreERP:1.0-SNAPSHOT`، Java 17، UTF-8.
- **Starters**: `spring-boot-starter-web`, `data-jpa`, `validation`, `websocket`, `test`.
- **قاعدة البيانات**: `org.postgresql:postgresql:42.6.0` (**لا يوجد sqlite-jdbc** — الهجرة اكتملت في pom؛ خلاف ما ذكرته وثيقة POSTGRES_MIGRATION_FINALIZATION.md في مرحلتها السابقة).
- **سحابة**: `com.google.firebase:firebase-admin:9.2.0` + `com.google.http-client:google-http-client-gson:1.43.3`.
- **JSON**: `gson 2.10.1` + `jackson-databind` (مدار من الأب).
- **باركود**: `com.google.zxing:core + javase 3.5.3`.
- **Lombok** (optional) + `spring-boot-starter-test`.
- بناء: `maven-compiler-plugin 3.15.0` (Java 17) + `spring-boot-maven-plugin` (Fat JAR، mainClass = `com.layan.erp.main.ServerApp`).
- ملاحظة دقيقة: `<javafx.version>17.0.2</javafx.version>` معرَّف في الخصائص لكن **لا توجد تبعيات JavaFX فعلًا** في pom الحالي — بقايا نسخة سطح مكتب JavaFX (التي عاشت في الـsnapshot بفئات com.layanerp).

---

## 6) مخازن البيانات

| المخزن | الدور | الدليل |
|---|---|---|
| **PostgreSQL `layan_erp`** (localhost:5432) | المخزن الأساسي: Spring JPA (`application.properties`: HikariCP 20 اتصالًا، `ddl-auto=update`، توقيت Africa/Cairo، JSON بـSNAKE_CASE) + JDBC مباشر بـHikariCP في `Database.java` (تجمع 20/5) | قراءة الملفين + `POSTGRES_MIGRATION_FINALIZATION.md` |
| هجرات SQL يدوية | `db/migration/V11__accounting_engine_pg_sync.sql` (petty_cash_log + أعمدة daily_ledgers + سجلات cash_registers) و`V12__purchase_orders_and_replenishment.sql` (order_status/expected_delivery_date + فهارس) — تُنفَّذ أيضًا برمجيًا من `Database.initPostgresAccountingTables()` | قراءة الملفين |
| **Firebase Firestore** | مرآة سحابية: طابور `Sync_Queue` كل 5 ثوانٍ + تدقيق كل 30 دقيقة، مستندات `B1_<table>_<id>` وحذف ناعم `is_deleted`، حتى 10 محاولات بتراجع تصاعدي | `FirebaseSyncService.java` + `FirebaseConfig.java` (يحمّل `firebase-key.json` أو `firebase-service-account.json` من جذر التشغيل — **حساس، لم يُقرأ**) |
| **SQLite (تاريخي)** | اختفى من النسخة الحية: `Database.initializeTables()` يتجاوز هجرات SQLite صراحة (`isPostgres = true`)، ولا `layan_erp.db` في جذر الحي (موجود في الـsnapshot فقط، 413KB)، وpom الحالي بلا `sqlite-jdbc` | `Database.java:56-65` + pom.xml الحالي + مقارنة قائمتي الجذرين |
| ملفات مساعدة | `uploads/` (وسائط الشات — `DiskFileHandler`)، `backups/postgres/` (أدوات `tools\db`: backup/check/restore)، `authorized_owners.txt` (مستلمو تنبيهات Telegram) | `ServerApp.java` + `DATABASE_BACKUP_TO_PROJECT_FOLDER.md` + `TelegramController.java` |

---

## 7) نقاط التكامل

1. **Telegram Bot** (استراتيجية مزدوجة): Long-Polling دائم يمسح الويب هوك عند الإقلاع + مسار `/api/telegram/webhook` + صندوق موافقات فواتير (`/api/telegram/inbox|approve|reject` — ServerApp أسطر 473-479) + إشعار أعطال عالمي من `ServerApp`؛ المالكون في `authorized_owners.txt`.
2. **WhatsApp Chat Pro (المزامنة الحية)**: دردشة داخلية بواجهة WhatsApp (قائمة محادثات بعدّادات غير مقروء + رسائل صوتية بمؤقّت ومشغل مخصص) في `chat-widget.js` **V6.0 WhatsApp Pro** عبر `/api/chat/*` (Spring `ChatRestController` + خلفية HttpServer) مع WebSocket STOMP (`/ws`, `/ws-stomp`, `/ws/notifications` — `WebSocketConfig.java`) + تبويب شات في `mobile.html`.
3. **Firebase (مرآة سحابية)**: ثلاث خدمات Java (Sync/Listener/Migration) عبر `firebase-key.json` + **cloud-mirror**: Next.js + React 19 يقرأ Firestore مباشرة (`cloud-mirror/src/lib/firebase.ts`، projectId `layan-erp`) ويصدّر إلى `out/` لـFirebase Hosting (`CLOUD_MIRROR_AUDIT.md`)، بـ15 صفحة admin.
4. **ngrok (نفق للإنترنت)**: `NgrokLifecycleManager` يشغّل `start-tunnel.ps1` تلقائيًا عند `ApplicationReadyEvent` ويقتل العملية عند الإيقاف (`@PreDestroy` + taskkill)، مع `ngrok.exe` (32MB) في الجذر و`_ngrok.bat` و`start-tunnel.ps1`.
5. **APK طاقم العمل**: `layan-staff-v4.apk` (47MB في الجذر) مبني من `layan-erp---staff-edition` (Gradle Kotlin DSL، بنية `com.example.data/models|network + ui + utils`؛ `metadata.json`: «نظام ليان لإدارة نقاط البيع والمخزون والعملاء والموردين والورديات للموظفين مع تزامن محلي فوري» + إمكانية Gemini API). واجهات الموبايل الويب: `mobile.html/js` (كاتالوج/سلة/شات/حضور) و`attendance-mobile.html` (حضور QR عبر `/r?token=`).
6. **الطباعة والباركود**: `/api/print` + `/api/print-batch` (`PrintController`)، توليد باركود ZXing بنقل صوتي عربي→لاتيني حتمي + رموز `ABC-0001` (`PRODUCT_BARCODE_ENGINE.md` + `dto/barcode` + `barcode-engine-ui.js`)، قراءة QR متصفح (`html5-qrcode.min.js`، `qrcode.min.js`)، ماسح هاتف مقترن بـPOS (`RemoteScannerController`: pair/scan/poll)، وإعادة تصميم ملصقات حرارية موثقة في `THERMAL_BARCODE_LABEL_REDESIGN.md`.
7. **إدارة العمليات**: نسخ احتياطي PostgreSQL بأدوات `tools/db/*.ps1` (backup/check/restore) مع مجلد `backups/postgres/` — موثقة في `DATABASE_BACKUP_TO_PROJECT_FOLDER.md`؛ قواعد جدار نار للمنفذ 9090 في `WINDOWS_LOCAL_SETUP_REPORT.md`.
8. **ذكاء اصطناعي**: `GeminiService.java` (واحدة من 24 خدمة) — بالاسم في الجرد.

---

## 🔗 علاقة النسخ الثلاث (قسم إلزامي)

| # | النسخة | الدور | الدليل |
|---|---|---|---|
| 1 | `G:\ai\codex\LayanStoreERP` | **الأصل الحي الوحيد** — مستودع Git نشط، فرع `main`، آخر commit `04d010f` 2026-09-25، شجرة نظيفة (porcelain = 0)، PostgreSQL، 226 ملف Java، ويضم cloud-mirror وAPK وStaff Edition وtools | `git log/status` فعلي + أحدث ملفات src بتاريخ 2026-09-25 |
| 2 | `G:\ai\LayanStoreERP` | **snapshot أبريل قديم** — أحدث ملف مصدر فيه **2026-04-22**، يحمل بقايا مرحلة ما قبل الهجرة: `layan_erp.db` (SQLite، 413KB)، سجلات أخطاء بناء (`build_errors.log` 70KB)، حزمة JavaFX القديمة `com.layanerp`، و`utils\CommandRouter.java` المحذوف من الحي | مقارنة أزمنة الملفات + جذر الـsnapshot يحوي db وlogs لا وجود لها في الحي؛ Git له ملكية Windows مختلفة (فشل قراءة اللوج بأذونات المستخدم الحالي — دون تعديل أي إعداد) |
| 3 | `G:\ai\Layan Store\backend` | **بقايا بناء بلا src**: المجلد موجود ويحتوي `pom.xml` واحدًا فقط (3,983 بايت) — لا `src` ولا أي ملف Java (0 ملف) | فحص فعلي للمسار |

**الأصول الفريدة في snapshot أبريل (أصول محفوظة قبل أرشفة الـsnapshot — قُرأت الأربعة):**

1. **`src\main\java\com\layanerp\controller\QuickInvoiceInboxController.java`** (576 سطرًا):
   - متحكم JavaFX (FXML) لشاشة «صندوق الفواتير السريعة» القديمة: جدول فواتير شراء معلّقة (مورد/فرع/تاريخ) + جدول بنود قابل للتحرير المباشر (كمية/تكلفة/هامش ربح → سعر بيع يُعاد حسابه).
   - يحتوي مصفوفة توزيع `itemMatrixData` لتوزيع الكميات على المتغيرات (لون-مقاس) قبل الاعتماد، وأزرار اعتماد/رفض/مصفوفة.
   - يعمل بـJDBC مباشر (عصر SQLite) — هو النسخة المكتبية الأصل التي خلفها اليوم صندوق Telegram + واجهة Procurement في الحي.
2. **`src\main\java\com\layanerp\model\PendingInvoiceView.java`** (48 سطرًا):
   - نموذج JavaFX Property لصف الفاتورة المعلّقة: `id / supplierName / branchName / createdAt`.
   - رابط TableView عبر `PropertyValueFactory` فقط — بلا منطق أعمال.
   - قيمته الأرشيفية: تسمية الحقول المرجعية لواجهة الصندوق (supplierName/branchName/createdAt).
3. **`src\main\java\com\layanerp\model\PendingInvoiceItemView.java`** (114 سطرًا):
   - نموذج JavaFX لبنود الفاتورة (المنتج، الكمية، التكلفة، هامش الربح، سعر البيع المحسوب) مع `recalculateSellPrice() = cost + profit`.
   - يحمل منطق «⚠️ مطلوب توزيع» تلقائيًا عندما تكون الكمية > 1 — بذرة فكرة التوزيع على الفروع التي تطورت لاحقًا في وحدة التموين الحية.
   - يعمل بـ`double` للمال (مخالف لقواعد BigDecimal الحالية في AGENTS.md) — قيمته تاريخية كوثيقة تصميم فقط، لا كود لإعادة الاستخدام مباشرة.
4. **`src\main\java\com\layan\erp\utils\CommandRouter.java`** (320 سطرًا):
   - راوتر أوامر عربية لـTelegram من عصر ما قبل Spring: سجل `COMMAND_REGISTRY` (يومية، رصيد، خزينة، مصروفات، عن، نواقص، جرد، حضور، خصم، سلفة، رسالة، مزامنة، حالة) ببادئة مطابقة + مطابقة ضبابية Levenshtein (≤2).
   - يستدعي `Database.connect()` مباشرة (SQLite وقتها) و`FirebaseSyncService` للمزامنة اليدوية — نفس الأوامر الآن مدمجة داخل `TelegramController` الحي (1,547 سطرًا).
   - **`AGENTS.md:56` يحظر صراحة إعادة تقديم معمارية CommandRouter** — لذا قيمته أرشيفية (مرجع لأوامر البوت العربية الأصلية) لا معمارية قابلة للإرجاع.

---

## 8) تقييم الصحة: قوة / ديون تقنية / مخاطر

### ✅ نقاط القوة (بأدلة)
- **حوكمة توثيقية نادرة**: `AGENTS.md` يفرض عقد API موحد (`{success, message, data}`)، قواعد مال صارمة (BigDecimal إلزامي + `@Transactional` لكل عمليات المال والمخزون)، قواعد مخزون (InventoryStock لكل فرع، منع البيع الزائد)، ومنع إرجاع كيانات JPA مباشرة (أسطر 45–129).
- **مالية محصّنة بعد V4.0**: دفتر مورد مزدوج (INVOICE/PAYMENT) بلقطات رصيد + منع تكرار الفواتير + اختبارات (22 اختبارًا موثقة في `PURCHASE_SUPPLIER_LEDGER_VERIFICATION.md`، و5 ملفات اختبار فعلية في src\test).
- **أتمتة تشغيل ممتازة**: JDK21 + Maven مضمّنان داخل المشروع (`WINDOWS_LOCAL_SETUP_REPORT.md`)، ngrok تلقائي (`NgrokLifecycleManager`)، أدوات نسخ/استرجاع PostgreSQL جاهزة (`tools\db`).
- **تزامن متعدد الطبقات**: Sync Queue كل 5 ثوانٍ + تدقيق نصف ساعي + «Poke» فوري (`triggerSync`) + WebSocket STOMP للإشعارات + long-polling للموبايل.
- **حضور محصّن**: قفل تشاؤمي + idempotency موثقة في `STAFF_ATTENDANCE_SHIFT_HARDENING.md` مع اختبار فعلي `AttendanceServiceTest`.

### 🧱 الديون التقنية (بأدلة)
- **معمارية مزدوجة موازية**: بوابة JDK يدوية (~179 مسارًا في `ServerApp.setupRoutes`؛ الملف 14,811 سطرًا) موازية لـ54 متحكم Spring — التوجيه عبر `ProxyHandler` على `/api/` ثقيل ويجب فهمه قبل أي تعديل مسار.
- **ملفات شاردة/مكررة**: `src/main/java/TelegramController.java` (بلا حزمة، 171 سطرًا) جنبًا إلى جنب مع نسخة الحزمة الكاملة (1,547 سطرًا) + ملف `.fxml` بلا مشروع JavaFX نشط + `javafx.version` في pom بلا تبعيات.
- **تعارض دستور**: `SKILL.md` (سطر 10) يفرض أوامر SQLite (`PRAGMA table_info`) و«بيع بمخزون سالب» بينما `AGENTS.md` استقر على PostgreSQL وInventoryStock — دستوران متعارضان سيربكان أي وكيل.
- **وثائق قديمة مرحليًا**: `POSTGRES_MIGRATION_FINALIZATION.md` و`MOBILE_SYSTEM_AUDIT.md` يصفان حالة وسيطة (sqlite-jdbc في pom، أخطاء 500 على /api/mobile) لم تعد صحيحة كليًا الآن — تُقرأ بوعي تاريخي.
- **فوضى جذر**: `pom_new.xml/pom_temp.xml/dependency-reduced-pom.xml`، مخرجات تشغيل نصية (`run_output*.txt`, `server_log.txt`, `backend_test.txt`, `spring_boot_probe.*`)، `lib\gson.jar` (التبعية الآن عبر Maven)، JDK 1.8 مضمّن بلا استخدام، ملف `'Proceed'` غامض، وسجل محادثة 367KB (`HR Module Enhancements Complete.md` — 8,117 سطرًا من لقطات محادثة يشير لمسار قديم «Layan Store»).
- **نمط `catch(Exception ignored){}`** منتشر في `Database.java` و`ServerApp.java` — يبتلع الأخطاء بصمت.

### ⚠️ المخاطر (بأدلة — دون طباعة القيم)
- **أسرار مكهربة**: توكن Telegram ثابت في `TelegramController.java:19`؛ كلمة مرور DB احتياطية في `Database.java:24` و`application.properties:16`؛ `DATABASE_BACKUP_TO_PROJECT_FOLDER.md` يذكر كلمة مرور postgres نصًا صريحًا؛ حساب مدير نظام افتراضي بكلمة مرور ثابتة (`SystemAdminBootstrap.java:34`)؛ `keystore.jks` بكلمة مرور ضعيفة مكهربة (`ServerApp.java:101`)؛ `firebase-key.json` في الجذر (حساس، لم يُقرأ).
- **نقاط تدمير بيانات**: `/api/admin/clean-slate` و`/api/admin/secure-wipe` يفرغان الجداول المالية (`ZeroDB.executeCleanSlate` = TRUNCATE لـ14 جدولًا ماليًا) — خطر تشغيلي حتى لو كان مقصودًا للصيانة.
- **CORS مفتوح بالكامل** (`Access-Control-Allow-Origin: *` في `ServerApp.wrap()` و`@CrossOrigin("*")` في `ChatRestController`) مع HTTPS بكلمة keystore افتراضية.
- **`ddl-auto=update` في الإنتاج** (`application.properties:21`) — مخالف لنفس قواعد `AGENTS.md:123-124` (Flyway/Liquibase) رغم وجود `db/migration`.
- **ثقل مستودع**: JDK8 + Maven + ngrok.exe + APK (47MB) داخل الشجرة — نسخ مستودع بطيئة وخطر تسريب ثنائيات.
- **ثنائي المصدر**: مجلد «Layan ERP apk» نسخة متداخلة شبه كاملة من المشروع — سينتج بناء قديم إن شُغّل بالخطأ.

---

## 9) جاهزية التطوير — خريطة دخول للوكيل لو رجع يطوّره بكرة

1. **اقرأ بالترتيب**: `AGENTS.md` (العقد والقواعد) ← `MIGRATION_PAGE_BY_PAGE_PLAN.md` (خريطة حالة كل مسار: SPRING_READY/LEGACY_SQLITE/MIXED_BRIDGE + جدول الصفحات) ← `SKILL.md` **بحذر** (قديم SQLite — تجاهل أوامر PRAGMA).
2. **التشغيل**: PostgreSQL `layan_erp` + `DB_PASSWORD` ثم `run.bat` (بعد بناء الجرّ) أو `_backend.bat` (تشغيل مباشر). المنافذ: 9090 بوابة، 18080 Spring، 8443 HTTPS.
3. **إضافة ميزة جديدة**: المسار الحديث = متحكم Spring في `controller` → `service` (@Transactional) → `repository` → DTOs مع مغلف `ApiResponse` (`{success, message, data}`)؛ المسارات القديمة تُسجَّل يدويًا في `ServerApp.setupRoutes()` — **لا تضف مسارًا جديدًا إلا في طبقة Spring** واترك `ProxyHandler` يمرره.
4. **مواقع حرجة لا تُلمس باستخفاف**: `PosSaleService` (checkout)، `ProcurementService`، `SupplierFinancialService`، `AttendanceService` (قفل تشاؤمي)، `FirebaseSyncService` (طابور المزامنة)، `ZeroDB` (لا تُستدعى من ميزة).
5. **قواعد غير قابلة للتفاوض** (من AGENTS.md): BigDecimal للمال، `@Transactional`، لا CommandRouter ولا BranchStock ولا raw SQL بلا مبرر، مغلف JSON موحد، DTOs مع `@Valid`.
6. **الاختبار**: 5 ملفات في `src\test` (AttendanceServiceTest, HrRequestServiceTest, MobileAuthServiceTest, StaffCrudServiceTest, MobileRestControllerTest) — توسيعها أسرع شبكة أمان.
7. **أماكن الألم المعروفة**: توجيه `ProxyHandler` في نهاية `setupRoutes` (ServerApp:482)، افتراض الفرع 1 في الحذف السحابي (`FirebaseSyncService:83` — «Future refactor»)، تناقض واجهة/طريقة في بعض المسارات (وثّقته `MOBILE_SYSTEM_AUDIT.md`: GET مقابل POST مثالًا).
8. **الأولوية المنطقية للتطوير القادم** (مستخلصة من `MIGRATION_PAGE_BY_PAGE_PLAN.md`): إكمال نقل مسارات POS/الفواتير/المحاسبة من ServerApp إلى Spring بحذر مالي، وتوحيد الدستور (SKILL.md مقابل AGENTS.md)، ونقل الأسرار إلى متغيرات بيئة، وإخراج JDK/Maven/APK الثقيلة من الشجرة.

---

## 9) تقييم الصحة — خلاصة مصنّفة

| البعد | الحكم | أساس الحكم |
|---|---|---|
| بنية معمارية | 🟡 هجينة عاملة لكنها ثقيلة | ServerApp (14,811 سطرًا) + Spring موازيان بجسر ProxyHandler |
| مالية | 🟢 محصّنة نسبيًا | BigDecimal + دفتر مزدوج + 22 اختبارًا (وثيقة التحقق) |
| توثيق | 🟡 غني لكن مزدحم بتواريخ متعارضة | ~44 ملف MD في الجذر بينها وثائق مرحلية قديمة |
| أمن الأسرار | 🔴 ضعيف | توكن/كلمات مرور/keystore مكهربة (المواقع ذُكرت أعلاه) |
| قابلية التشغيل | 🟢 ممتازة محليًا | JDK/Maven مضمّنان + ngrok تلقائي + أدوات نسخ احتياطي |
| الاختبارات | 🟡 مبدئية | 5 ملفات اختبار فقط على 226 ملف Java |

---

## 10) جاهزية التطوير — خريطة دخول للوكيل لو رجع يطوّره بكرة

1. **اقرأ بالترتيب**: `AGENTS.md` (العقد والقواعد) ← `MIGRATION_PAGE_BY_PAGE_PLAN.md` (خريطة حالة كل مسار: SPRING_READY/LEGACY_SQLITE/MIXED_BRIDGE + جدول الصفحات) ← `SKILL.md` **بحذر** (قديم SQLite — تجاهل أوامر PRAGMA).
2. **التشغيل**: PostgreSQL `layan_erp` + `DB_PASSWORD` ثم `run.bat` (بعد بناء الجرّ) أو `_backend.bat` (مباشر من المصدر). المنافذ: 9090 (بوابة) و18080 (Spring) و8443 (HTTPS).
3. **إضافة ميزة جديدة**: المسار الحديث = متحكم Spring في `controller` → `service` (@Transactional) → `repository` → DTOs مع مغلف `ApiResponse` (`{success, message, data}`)؛ المسارات القديمة تُسجل يدويًا في `ServerApp.setupRoutes()` — **أضف الجديد في طبقة Spring** واترك `ProxyHandler` يمرره.
4. **مواقع حرجة لا تُعدَّل بلا فهم**: `PosSaleService` (checkout)، `ProcurementService`، `SupplierFinancialService`، `AttendanceService` (قفل تشاؤمي)، `FirebaseSyncService` (طابور المزامنة)، `ZeroDB` (لا تستدعِه من ميزة إطلاقًا).
5. **قواعد غير قابلة للتفاوض** (من AGENTS.md): BigDecimal للمال، `@Transactional`، لا CommandRouter ولا BranchStock ولا raw SQL بلا مبرر، مغلف JSON موحد، DTOs مع `@Valid`.
6. **الاختبار**: 5 ملفات في `src\test` — توسيعها أسرع شبكة أمان قبل أي تغيير مالي.
7. **أماكن الألم المعروفة**: جسر `ProxyHandler` (ServerApp:482)، افتراض الفرع 1 في الحذف السحابي (`FirebaseSyncService:83`)، تناقضات GET/POST المتبقية (`MOBILE_SYSTEM_AUDIT.md`).
8. **أولويات مقترحة للتطوير القادم** (مستخلصة من `MIGRATION_PAGE_BY_PAGE_PLAN.md` + هذه الدراسة): إكمال نقل مسارات POS/الفواتير/المحاسبة من ServerApp إلى Spring بحذر مالي، توحيد الدستور (SKILL.md مقابل AGENTS.md)، نقل الأسرار إلى متغيرات بيئة، إضافة Flyway فعلي بدل ddl-auto=update.

---

## 10) فهرس الملفات المهمة

| الملف | دوره | أبرز ما يلزم معرفته |
|---|---|---|
| `pom.xml` | تعريف Maven الكامل | Spring Boot 3.2.0، Java 17، PostgreSQL 42.6.0، firebase-admin 9.2.0، ZXing 3.5.3، Gson، Lombok؛ Fat JAR mainClass=ServerApp؛ **بلا sqlite-jdbc**؛ `javafx.version` بقايا معطلة |
| `run.bat` | تشغيل الإنتاج | ينتظر `target\LayanStoreERP-1.0-SNAPSHOT.jar` ثم يشغّله بـ`tools\jdk21\bin\java` |
| `_backend.bat` | تشغيل التطوير | `apache-maven-3.9.6\bin\mvn.cmd exec:java` للـServerApp مباشرة |
| `ServerApp.java` (com.layan.erp.main) | البوابة القديمة — 14,811 سطرًا | ~179 مسارًا يدويًا، إقلاع كل المحركات، HTTPS 8443 بـkeystore.jks، ProxyHandler إلى Spring، درع أعطال Telegram، `seedData()` |
| `LayanErpApplication.java` | نقطة Spring | توقيت القاهرة + banner «PostgreSQL layan_erp» |
| `application.properties` | إعدادات Spring | منفذ 18080، PostgreSQL layan_erp، HikariCP 20، ddl-auto=update، JSON SNAKE_CASE |
| `db\Database.java` | طبقة JDBC + هجرات | HikariCP→PostgreSQL، يتجاوز هجرات SQLite صراحة، ينشئ جداول المحاسبة ويركّب أعمدة يدويًا (1,551 سطرًا) |
| `AGENTS.md` | دستور الوكيل | عقد API `{success,message,data}`، BigDecimal، @Transactional، حظر CommandRouter/BranchStock، قواعد حذف وصلاحيات |
| `SKILL.md` | دستور قديم (عصر SQLite) | أوامر PRAGMA وبيع سالب المخزون — قديم جزئيًا؛ تعارض مع AGENTS.md |
| `TelegramController.java` | بوت Telegram الكامل (1,547 سطرًا) | Long-polling + webhook + صندوق موافقات؛ توكن مكهرب سطر 19؛ ملف authorized_owners.txt |
| `TelegramController.java` (جذر src\main\java) | بقايا شاردة بلا حزمة | مكرر قديم — مرشّح حذف آمن بعد الموافقة |
| `service\FirebaseSyncService.java` | محرك المزامنة السحابية | Sync_Queue كل 5 ثوانٍ، تدقيق 30 دقيقة، 10 محاولات، حذف ناعم `B1_<table>_<id>` |
| `service\FirebaseConfig.java` | تهيئة Firebase Admin | يبحث عن firebase-key.json / firebase-service-account.json في جذر التشغيل |
| `service\SupplierFinancialService.java` | Supplier Ledger V4.0 | BigDecimal + @Transactional، إحصاءات عالمية، دفتر INVOICE/PAYMENT |
| `service\ProcurementService.java` | التموين وإعادة التعبئة | اقتراحات ذكية من النواقص والمخزون ≤2؛ 563 سطرًا |
| `config\NgrokLifecycleManager.java` | نفق تلقائي | يشغّل start-tunnel.ps1 عند الإقلاع ويقتله عند الإيقاف |
| `config\WebSocketConfig.java` | إشعارات حية | STOMP على /ws + SockJS + broker /topic |
| `config\ZeroDB.java` | تنظيف شامل (خطر) | TRUNCATE لـ14 جدولًا ماليًا + إعادة التسلسلات — صيانة فقط |
| `config\SystemAdminBootstrap.java` | إنشاء حساب أول | admin افتراضي بكلمة مرور ثابتة + فرع رئيسي افتراضي |
| `db\migration\V11__accounting_engine_pg_sync.sql` | هجرة محاسبة | petty_cash_log + أعمدة daily_ledgers + خزائن MAIN_SAFE/PETTY_CASH/BANK |
| `db\migration\V12__purchase_orders_and_replenishment.sql` | هجرة تموين | order_status/expected_delivery_date + item_name/color/size + فهارس |
| `AGENTS.md` | دستور المشروع الحاكم | الجذر النشط codex، عقد API، قواعد مال/مخزون/اختبار، حظر CommandRouter/BranchStock |
| `SKILL.md` | دستور قديم (SQLite) | PRAGMA، بيع بمخزون سالب، بروتوكول تنفيذ صارم — قديم جزئيًا |
| `POSTGRES_MIGRATION_FINALIZATION.md` | توثيق الهجرة (مرحلي) | أدلة PostgreSQL + قائمة بقايا SQLite وقتها — تاريخي |
| `MIGRATION_PAGE_BY_PAGE_PLAN.md` | خريطة هجرة المسارات | تصنيف كل مسار: SPRING_READY / LEGACY_SQLITE / MIXED_BRIDGE + ترتيب هجرة مقترح |
| `PURCHASE_SUPPLIER_LEDGER_VERIFICATION.md` | تقرير Supplier Ledger V4.0 | BigDecimal، دفتر مزدوج، منع تكرار، 22 اختبارًا ناجحًا |
| `STAFF_ATTENDANCE_SHIFT_HARDENING.md` | تحصين الحضور (2026-05-01) | قفل تشاؤمي، idempotency، عرض 12 ساعة عربي، worked_hours |
| `POS_STOCK_SALE_DRAWER_FULL_FIX.md` | إصلاح POS/الدرج (2026-05-10) | الحقيقة: branch_stock هو المخزون الحقيقي؛ إصلاح درج POS ومشاكل النوافذ |
| `DATA_DISAPPEARANCE_AUDIT.md` | تدقيق اختفاء بيانات (2026-05-01) | البيانات سليمة في PostgreSQL؛ المشكلة كانت سيرفرًا يعمل من مسار آخر (LayanStorFinal) بمسارات غير مطابقة |
| `CLOUD_MIRROR_AUDIT.md` | تدقيق cloud-mirror | Next.js حقيقي + Firebase Hosting يشير إلى cloud-mirror/out — ليس مجرد كاش |
| `MOBILE_SYSTEM_AUDIT.md` | تدقيق نظام الموبايل | جرد مسارات /api/mobile و/api/chat وصفحات الموبايل وحالة ملكية كل مسار وقت الهجرة |
| `PRODUCT_BARCODE_ENGINE.md` | محرك الباركود | ZXing، نقل صوتي عربي→لاتيني، رموز ABC-0001، بلا هجرة schema |
| `DATABASE_BACKUP_TO_PROJECT_FOLDER.md` | دليل النسخ الاحتياطي | أدوات tools\db + مجلد backups/postgres + خطوات الاسترجاع بعد إعادة تثبيت ويندوز (يذكر كلمة مرور postgres نصًا — أمنيًا يجب تعميمها) |
| `WINDOWS_LOCAL_SETUP_REPORT.md` | تقرير إعداد جهاز (2026-05-07) | JDK21 في tools\jdk21، Maven 3.9.6 مضمّن، PostgreSQL 18، تعارض كلمة مرور postgres وقتها |
| `STAFF_ATTENDANCE_SHIFT_HARDENING.md` | تحصين الحضور | قفل تشاؤمي، idempotency، worked_hours، 14 ملفًا معدلًا |
| `PURCHASE_SUPPLIER_LEDGER_VERIFICATION.md` | تحقق Supplier Ledger V4.0 | دفتر مزدوج + منع تكرار + 22 اختبارًا ناجحًا |
| `cloud-mirror\package.json` + `src\lib\firebase.ts` | مرآة سحابية | Next 16 + React 19 + firebase-js 12؛ Firestore مباشرة؛ 15 صفحة admin؛ out/ للاستضافة |
| `layan-erp---staff-edition\metadata.json` | هوية تطبيق الموظفين | «تزامن محلي فوري» + إمكانية Gemini API؛ بنية com.example.data/ui/utils |
| `firebase-key.json` / `keystore.jks` | مكوّنان حساسان | **ممنوع قراءتهما/طباعتهما** — تُدار كمفاتيح إنتاج (موجودان في الجذر) |

---

## خلاصة التنفيذية (3 أسطر)

1. **النسخة الحية في `codex\LayanStoreERP` سليمة ومستقرة** (Git نظيف، commit 2026-09-25) بعد هجرة كاملة إلى PostgreSQL/Spring JPA مع بوابة JDK قديمة موازية تُخدم عبر وكيل عكسي — أي تطوير قادم يجب أن يستهدف طبقة Spring ويترك البوابة القديمة تتقلص.
2. **أعلى قيمة الآن**: نقل الأسرار من الكود والتوثيق إلى متغيرات بيئة، وتوحيد الدستورين (AGENTS.md ضد SKILL.md)، وإخراج JDK/APK الثقيلة من المستودع.
3. **النسختان الأخريان**: snapshot أبريل (`G:\ai\LayanStoreERP`) أصبح أرشيفًا تاريخيًا تُحفظ منه 4 أصول فريدة موثقة أعلاه (JavaFX inbox + CommandRouter)، و`Layan Store\backend` مجرد pom يتيم — يمكن أرشفة كليهما بأمان بعد التصديق.
