# 🏗️ ملخص معماري: LayanStoreERP (snapshot أبريل)

> دراسة بقلم فيجن (الوكيل الأم) مباشرة — وكيلا المذاكرة انقطعا مرارًا على هذا المشروع الكبير (هيكل هذا الملف استُبدل بنسخة مبنية على قراءات فيجن).
> تاريخ: 2026-10-18 ~03:00 | الملفات المقروءة فعليًا: 7 (pom.xml أول 45/148، جرد كامل 149 ملف Java بـ glob، QuickInvoiceInboxController أول 50/576، CommandRouter أول 50/320، PendingInvoiceView أول 30/48، PendingInvoiceItemView أول 30/114) + إحالة لدراسة الأصل الحي.

## 1) الغرض الوظيفي
نسخة أبريل 2026 من ERP ليان (Spring Boot 3.2.0 + Java 17 — pom.xml:8-19) — **مرجع تاريخي** لسلسلة تطوير النسخة الحية في `codex\LayanStoreERP` (الدراسة الكاملة: [LayanStoreERP-live.md](LayanStoreERP-live.md)). قيمتها: تثبيت مرحلة تطوير + 4 ملفات فريدة (تجربة سطح مكتب JavaFX وموجه أوامر تليجرام عربي).

## 2) نقاط الدخول والتشغيل
- `pom.xml`: Spring Boot 3.2.0 + Java 17 + SQLite (3.42) + PostgreSQL (42.6) + Gson + **JavaFX 17.0.2 كخاصية** (pom.xml:21) — دليل على تجارب واجهة ديسكتوب.
- نقطة الدخول Spring: `com.layan.erp.LayanErpApplication` (نفس الأصل الحي).
- **حزمة موازية**: `com.layanerp` (بلا نقطة بين layan وerp!) + `TelegramController.java` بجذر java — تطوير جانبي لم يكتمل.

## 3) الهيكل العام (مقيس)
```
G:\ai\LayanStoreERP\  (snapshot أبريل 2026)
├── pom.xml (148 سطرًا)
├── src\main\java\com\layan\erp\     ← شجرة النسخة الحية نفسها (149 ملف Java مقيسة هنا)
│   ├── controller\ (Procurement/Product/Accounting/Auth/Branch/Category/Chat/
│   │   ChatMedia/Communication/Customer/Discount/HR/Inventory/Invoices/
│   │   Ledger/Mobile/Notification/Print + ...)
│   ├── entity\ (~35 كيانًا: SaleInvoice, PurchaseInvoice, SupplierLedger,
│   │   StockTransfer, PickRequest, MobileOrder, PendingInvoice(+Item),
│   │   CashRegister, ShiftLog, AttendanceLog, StaffDeduction, Obligation, ...)
│   ├── repository\ (~40) + dto (Permissions/PermissionsMatrix/ApiResponse)
│   ├── utils\ (CommandRouter + BarcodeEngine) + service (FirebaseSyncService,
│   │   SecurityService) + db (Database)
│   └── TelegramController.java (في جذر java — خارج الحزم!)
└── src\main\java\com\layanerp\      ← ⭐ حزمة تجريبية فريدة (JavaFX Desktop)
    ├── controller\QuickInvoiceInboxController.java (576 سطرًا)
    └── model\PendingInvoiceView.java + PendingInvoiceItemView.java
```

## 4) الوحدات الرئيسية
1. **شجرة الويب `com.layan.erp`**: نفس بنية الأصل الحي (controllers/entities/repositories/dto/config/utils/service) لكن بحجم أصغر (149 مقابل 226 ملف Java في الحية — فالحية أضافت ~77 ملفًا: WhatsApp sync، Procurement وغيره).
2. **الموجة الفريدة 1 — «صندوق الفواتير السريع» على سطح المكتب (JavaFX)**: `QuickInvoiceInboxController` (576 سطرًا، FXML): جدولان (فواتير معلقة مورد/فرع/تاريخ + أصناف كمية/تكلفة/هامش ربح/سعر بيع) مع تعديل خلايا مباشر + أزرار موافقة/رفض/مصفوفة توزيع، على JDBC خام (QuickInvoiceInboxController.java:1-50).
3. **الموجة الفريدة 2 — `CommandRouter` (320 سطرًا)**: سجل 13 أمرًا تليجرام عربيًا: يومية/رصيد/خزينة/مصروفات/عن/نواقص/جرد/حضور/خصم/سلفة/رسالة/مزامنة/حالة (CommandRouter.java:14-35) بتوجيه بادئات عربية (44-50) ورد عبر BiConsumer — بذرة مساعد تليجرام العربي الذي تطور لاحقًا في الحية.
4. **الموجة الفريدة 3 — Models الفريدة**: `PendingInvoiceView` (48 سطرًا: id/supplier/branch/createdAt كـFX properties) و`PendingInvoiceItemView` (114 سطرًا: كمية/تكلفة/هامش/سعر محسوب + علم `⚠️ مطلوب توزيع` للكمية>1 — PendingInvoiceItemView.java:27).

## 5) المكتبات (من pom.xml المقروء)
spring-boot-starter-parent 3.2.0 | sqlite-jdbc 3.42 | postgresql 42.6 | Gson 2.10.1 | JavaFX 17.0.2 (خاصية pom:21) | Java 17.

## 6) مخازن البيانات
SQLite + PostgreSQL (pom.xml:26-37) — نفس عائلة النسخة الحية (layan_erp). بدون فتح قواعد.

## 7) التكاملات
Firebase (FirebaseConfig + FirebaseSyncService مستوردة في CommandRouter.java:4) • Telegram (TelegramController + CommandRouter) • JavaFX تجريبي.

## 8) تقييم الصحة (بدليل)
🟢 قيمة تاريخية: لقطة نظيفة لمرحلة وسطى — pom أبسط (بدون إضافات لاحقة) وتجارب JavaFX لم تكمل في الحية.
🟡 **الفرع ميت تشغيليًا** — إثبات من [live_db_architecture.md](live_db_architecture.md): بياناته متجمدة عند 24/09 وقاعدة PostgreSQL لا تعمل.
🟡 حزمتان متوازيتان (`com.layan.erp` و`com.layanerp`) + TelegramController بشاذ في جذر java — فوضى تنظيمية نموذجية لمرحلة تجريبية.
🟡 JavaFX معلن في pom بلا module setup واضح — تجربة نصف مكتملة.

## 9) الملفات الفريدة ×4 + علاقة النسخ الثلاث
| الملف | دوره (بدليل) |
|-------|--------------|
| QuickInvoiceInboxController.java (576 سطرًا) | شاشة JavaFX لصندوق فواتير الشراء المعلقة: موافقة/رفض/مصفوفة توزيع أسعار بتحرير مباشر للتكلفة والهامش (FXML + JDBC خام) |
| PendingInvoiceView.java (48) | موديل صف فاتورة (مورد/فرع/تاريخ) لجدول JavaFX |
| PendingInvoiceItemView.java (114) | موديل صنف: تكلفة/هامش/سعر محسوب + حالة توزيع آلية للكمية>1 (سطر 27) |
| CommandRouter.java (320 سطرًا) | موجّه أوامر تليجرام عربي (13 أمرًا: يومية/رصيد/خزينة/عن/نواقص/حضور/خصم/سلفة/مزامنة/حالة…) |

**النسخ الثلاث:** `codex\LayanStoreERP` = الأصل الحي (Git، 226 ملف Java، مُدرس بالكامل) → **هذه (snapshot أبريل، 149 ملفًا)** = أرشيف مرحلة وسطى تحفظ 4 ملفات فريدة أعلاه → `Layan Store\backend` = بقايا بناء بلا src. الملفات الفريدة أعلاه هي المرشحة للنقل/الحفظ عند الأرشفة إلى `_archive\LayanStoreERP-snapshot-2026-04`.

## 10) فهرس الملفات المهمة
| الملف | دوره | ملاحظة |
|-------|------|--------|
| pom.xml | Spring Boot 3.2.0 + Java 17 + JavaFX | 148 سطرًا |
| com\layanerp\QuickInvoiceInboxController (576) | تجربة سطح مكتب JavaFX لصندوق الفواتير | فريدة في الـsnapshot |
| com\layan\erp\utils\CommandRouter (320) | موجّه أوامر تليجرام عربي (13 أمرًا) | تطور لاحقًا في الحية |
| TelegramController.java (جذر) | تليجرام خارج البنية القياسية | بشاذ — موضع مراجعة |

---
*الجاهزية للعودة للتطوير: 85% (جرد كامل + الملفات الفريدة مقروءة؛ أعماق controllers متاحة عند الطلب).*
