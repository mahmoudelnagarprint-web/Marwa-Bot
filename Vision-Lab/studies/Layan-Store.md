# 🏗️ ملخص معماري: Layan Store

> **دراسة وكيل المذاكرة — 2026-10-18** | المسار: `G:\ai\Layan Store`
> **تحذير جوهري:** هذا المجلد **ليس** مشروع الـ Java ERP الكامل. `backend\` يحتوي فقط `pom.xml` + `target\` بقايا بناء **بلا أي src** (تم جردهما بالاسم فقط). المصدر الحقيقي للـ ERP جافا في `G:\ai\LayanStoreERP` (وكيل آخر). ما هنا هو **الطبقة التشغيلية المحلية**: خادم مزامنة Node + SPA كاشير/إدارة + تطبيق موبايل PWA + مخطط قاعدة بيانات مرجعي.

---

## 1) الغرض الوظيفي

نظام نقاط بيع وموارد مؤسسة **Offline-First متعدد الفروع** لمتاجر «ليان ستور» (ملابس): كاشير POS بواجهة عربية، تطبيق موبايل للموظفات لإرسال السلال للكاشير، نظام HR (حضور/رواتب/عمولات)، دردشة Nexus، وكل شيء يعمل بلا إنترنت ويتزامن عبر خادم محلي. (المصدر: `README.md` سطر 1-4، و`sync-server.js` سطر 1-3)

## 2) نقاط الدخول وطريقة التشغيل

| نقطة الدخول | ما تفعله | طريقة التشغيل |
|---|---|---|
| `sync-server.js` (440 سطرًا) | **خادم المزامنة المركزي** — HTTP على `0.0.0.0:3000`، 14 مخزن بيانات في الذاكرة تُحفظ كملفات JSON في `.sync-data/` | يدويًا أو كخدمة Windows (أدناه) |
| `Run-SyncServer.bat` | يشغّل sync-server في نافذة تفاعلية (`node sync-server.js`) — للمزامنة بين الموبايل والـ POS أثناء الاستخدام | نقرة مزدوجة |
| `install-service.js` (37 سطرًا) | يُسجّل sync-server كخدمة Windows اسمها `LayanSyncServer` عبر مكتبة `node-windows`، بخيارات `--harmony --max_old_space_size=4096` | `node install-service.js` (مرة واحدة) |
| `daemon/` | **مخرجات الخدمة المولدة تلقائيًا**: `layansyncserver.exe` (wrapper من node-windows/WinSW) + `layansyncserver.xml` (تشغيل node.exe → sync-server.js، LocalSystem، restart 3، log rotate) + 3 ملفات logs | تُدار من services.msc |
| `Run-Observer-Monitoring.bat` | يشغّل **The Watcher** — خادم Telemetry ثانٍ `frontend/js/engines/observer-server.js` على منفذ **3001** يستقبل سجلات المراقبة الحية من الواجهة (`POST /log`) ويطبعها ملوّنة في الطرفية | نقرة مزدوجة |
| `frontend/index.html` | تطبيق الويب الرئيسي (SPA الكاشير/الإدارة) | عبر VS Code Live Server — الجذر `/frontend` (من `.vscode/settings.json`: `liveServer.settings.root`)، المنفذ الافتراضي 5500 |
| `frontend/mobile.html` | تطبيق الموبايل «Layan Pulse» (PWA بـ Service Worker) | من نفس الخادم الثابت، أو عبر QR من `QREngine` |

**دليل تشغيل فعلي:** سجل `daemon/layansyncserver.wrapper.log` يوثّق إقلاع الخدمة في 2026-05-03 و04 و05 (Started pid 4864/5108/5968) وتوقيفًا عند إغلاق ويندوز 2026-05-05 22:54 — الخدمة كانت تعمل فعليًا كـ daemon صامت. `layansyncserver.out.log` يكرر بانر الإقلاع «V2 Smart Hub is RUNNING! Port: 3000»، و`err.log` فارغ.

## 3) الهيكل العام

```
G:\ai\Layan Store\
├── sync-server.js          ← الخادم المركزي (Node http خام، بلا أي framework)
├── install-service.js      ← مُسجِّل خدمة Windows (node-windows)
├── Run-*.bat              ← مشغّلات تفاعلية (SyncServer / Observer)
├── package.json            ← تبعية واحدة فقط: node-windows
├── README.md               ← توثيق معماري (فيه تضارب مع الواقع — انظر §9)
├── implementation_plan.md  ← خطة admin-branches + branch-hub (عربية)
├── stuf                    ← خطة HR Command Center (ملف بلا امتداد!)
├── .cursorrules            ← إلزام مهارة layan-architect على أي AI editor
├── .agents\skills\         ← 4 مهارات (layan-architect, humanizer, indexeddb-optimization, uiux-designer)
├── .cursor\rules\          ← 4 قواعد .mdc لـ Cursor
├── .sync-data\            ← 9 ملفات JSON = قاعدة بيانات sync-server الفعلية
├── backend\               ← ⚠️ pom.xml فقط + target بلا src (بقايا — الجافا الحية في LayanStoreERP)
├── daemon\                ← خدمة Windows المولدة (exe + xml + logs)
├── database\01_master_schema.sql ← مخطط مرجعي: 26 جدولًا PostgreSQL/SQLite
├── frontend\              ← SPA كامل (بلا build — vanilla JS/CSS)
│   ├── index.html / mobile.html / observer-ui.html / sw.js / manifest.json
│   ├── js\core\           ← 5 ملفات: api-client, teleport (router), state-manager, ui-engine, sidebar-manager
│   ├── js\engines\        ← 8 ملفات: branch, hr, pos, product, observer (محرك+خادم), nexus-chat, qr
│   ├── modules\           ← 9 وحدات UI (pos, branch-hub, admin-branches, branches, inventory, products×2, suppliers, staff, settings) — (+ مجلد orders فارغ)
│   └── mobile\            ← تطبيق الموبايل: app.js + 6 وحدات (auth/catalog/cart/tracking/chat/profile)
├── java-1.8.0-openjdk-... ← نسخة JDK 8 محمولة مضمّنة داخل المشروع (تُتخطى)
└── node_modules\          ← node-windows + 17 تبعية عرضية فقط
```

## 4) الوحدات الرئيسية

### أ) خادم المزامنة `sync-server.js` — «V2 Smart Hub»
خادم HTTP خام (بلا Express). يحمّل 14 مخزنًا من `.sync-data/*.json` عند الإقلاع، ويوفّر REST API بلا مصادقة مع `CORS: *`:
- **Legacy Staff Orders** (موبايل→كاشير): `GET/POST/DELETE /api/staff-orders`
- **HR**: `/api/hr/staff` (CRUD كامل)، `/api/hr/attendance`، `/api/hr/payroll`، `/api/hr/audit` (قص تلقائي 5000)
- **الكتالوج**: `POST/GET /api/products-catalog` (الكاشير يدفع الكتالوج للموبايل)
- **Nexus Chat**: `/api/chat` (polling بترويسة `x-since-timestamp` + قص 10000)، `/api/chat/all`
- **مشتريات**: `POST /api/purchases/bulk-import` — **أهم منطق أعمال في الخادم**: يفجّر الفاتورة إلى منتجات/متغيرات/مخزون في `products_cache/variants_cache/inventory_stock` (يدمج بالاسم والـ SKU، `sell_price` تُصدَّر باسم `price` لتوافق جافا)
- **مرجعية مركزية**: `/api/products`، `/api/products/variants`، `/api/inventory/stock`، `/api/branches`، `/api/suppliers`، `/api/categories`، `/api/supplier-payments`
- **Zero-State Seeder**: يزرع فرعًا رئيسيًا `HQ-MAIN` وموردًا عامًا وفئة «عام» عند أول إقلاع

### ب) محركات الواجهة (Frontend Engines) — كلها Singletons على `window`
| المحرك | الملف | المسؤولية | التخزين |
|---|---|---|---|
| **BranchEngine** | `branch-engine.js` (1002 س) | النواة: سياق HQ/Branch من `localStorage.Layan_Context`، مصادقة بالوكالة عبر HREngine، طابور مزامنة، DNA Tokens (تفعيل الفروع)، heartbeat كل 10 ث | IndexedDB **LayanOfflineDB v10** (15 store) |
| **HREngine** | `hr-engine.js` (709 س) | بوابة الدخول: SHA-256 (بديل Pure-JS للـ HTTP/LAN)، Master PIN، سجل حضور/غياب، رواتب وعمولات 1% آلية، audit، cron يومي | IndexedDB **LayanHRDB v2** (staff/attendance/payroll/audit_log) |
| **POSEngine** | `pos-engine.js` (1076 س) | السلة والوردية وZ-Report والفاتورة **idempotent** (قفل `_isProcessing`)، استرداد سلة بعد الانهيار (snapshot صالح 4 ساعات)، **لا يلمس DOM** (Directive 6) | localStorage: `Layan_POS_Snapshot` + `Layan_POS_Shift` |
| **ProductEngine** | `product-engine.js` (836 س) | فهارس Map في الذاكرة (منتج/متغير/باركود/مخزون)، **Najjar Matrix** (توليد متغيرات ألوان×مقاسات)، استراتيجيات SKU/تسعير قابلة للتسجيل | فهارس من `BranchEngine` + مزامنة مؤجلة بـ `setTimeout(0)` |
| **ObserverEngine** | `observer-engine.js` | صندوق أسود: يلفّ `IDBObjectStore.prototype.put/add/delete` لتسجيل كل كتابة (مع حجب password/pin/token/secret)، sentinel للأخطاء، HUD | store `system_audit_logs` + دفع لخادم 3001 |
| **NexusChat** | `nexus-chat.js` | دردشة قابلة للسحب، polling من sync-server، إرفاق سياق ERP (طلب خصم من فاتورة نشطة) | sync-server `/api/chat` |
| **QREngine** | `qr-engine.js` (73 س) | روابط حضور للموبايل: `mobile.html?v=3` بIP الشبكة المحلية (`Layan_LAN_IP`، fallback 192.168.1.7) + توليد صورة QR من **api.qrserver.com الخارجي** | localStorage |

### ج) نواة الواجهة (`js/core`)
- **api-client.js**: مغلف fetch يفرض غلاف `{success, message, data}` (Directive 2)، timeout 15 ث، **طابور offline ثانٍ** في `localStorage.layan_offline_queue` يعاد إرساله عند online تلقائيًا
- **teleport.js**: Router هاش SPA — `ROUTE_MAP` من 9 مسارات مع **RBAC مساري** (`allowedRoles` + تجاوز كلي لـ ROOT_OWNER)، fallback ديناميكي `modules/<key>/<key>.js`، cache للوحدات، hook `initCurrentView` بعد كل mount
- **state-manager.js**: Pub/Sub مجمّد + سجل تاريخ 50 تغيير + قناة `ui:toast` عامة
- **ui-engine.js**: ThemeController (فاتح/غامق)، ModalStack، ZIndexManager، ClickGuard (قفل أزرار مزدوجة)، RippleEffect، `applyRBACVisibility`

### د) وحدات UI (`modules/`) — نمط موحّد `mount(container)/unmount`
كل وحدة تجلب HTML الخاص بها بـ fetch ثم تربط الأحداث. أبرزها: **pos** (كابينة الكاشير، 49KB HTML + 68KB JS، شاشة مقسومة 70/30)، **settings** (مركز تحكم البيانات: مسح ديناميكي لقاعدتي IndexedDB مع حفظ branches/local_cache، تصفير بكلمة تأكيد «تصفير»، تصدير/استعادة JSON شامل)، **branches** (معالج التأسيس: اختيار HQ أو إدخال DNA Token لتفعيل الفرع).

### هـ) تطبيق الموبايل «Velvet»
`mobile.html` + `sw.js` (cache-first باسم `layan-mobile-v3`) + `manifest.json` («Layan Horizon»). الدورة: CatalogModule يجلب `/api/products-catalog` من sync-server (بfallback تجريبي لجافا `localhost:8080`) → CartModule → `BranchEngine.createStaffOrder` (مع fallback لمخزن IDB المحلي إذا سقط الخادم) → TrackingModule يعرض status بpolling كل 5 ث → الكاشير يسحب الطلب من POS ويحوله لفاتورة عبر `POSEngine.loadStaffOrder`.

## 5) المكتبات (من package.json فعلًا)

| المكتبة | الإصدار | الاستخدام | الدليل |
|---|---|---|---|
| `node-windows` | ^1.0.0-beta.8 | **الوحيدة في package.json** — تسجيل sync-server كخدمة Windows | `package.json` سطر 3، `package-lock.json` |
| (تابعيات عرضية) | yargs, wrap-ansi, cliui, xml… إلخ (17 حزمة) | متطلبات node-windows نفسها | `package-lock.json` + جرد node_modules |

**لا توجد أي مكتبة JavaScript للواجهة** — كل شيء vanilla ES modules. الاعتماديات الخارجية الوحيدة: خطوط Google Fonts (index.html سطر 12)، ماسح `html5-qrcode` من unpkg CDN (mobile.html سطر 14)، وتوليد QR من `api.qrserver.com` (qr-engine.js سطر 2).

## 6) مخازن البيانات

### أ) `.sync-data/` — قاعدة بيانات sync-server (9 ملفات موجودة فعليًا)
`branches.json` (فرع HQ-MAIN تجريبي واحد)، `categories.json`، `suppliers.json`، `products_cache.json` (منتجان: «Test Product» ومدخل تسريبي «ببثص ييي» — بيئة اختبار)، `variants_cache.json`، `inventory_stock.json` (فارغ `[]`)، `purchase_invoices.json` (5.6KB)، `staff.json` (سجل STAFF-MASTER واحد بهاش SHA-256)، `chat_messages.json`. المحركات تحمّل 14 مخزنًا لكن 5 منها (staff_orders/attendance/payroll/audit_log/supplier_payments) لا ملفات لها بعد = لم تُستخدم محليًا بعد.

### ب) IndexedDB — طبقة الـ Offline الحقيقية
- **LayanOfflineDB v10** (`branch-engine.js` سطر 15-104): 15 store — sync_queue, local_cache, branches, sales, products, pick_requests, staff_orders, categories, shifts, invoices, cartHold, system_audit_logs, variants, stock, suppliers, customers — مع **migrations تصاعدية موثقة** (V8 حذف store staff مكرر «Split-Brain Fix»، V9 سجلات المراقبة، V10 متغيرات/مخزون/موردين/عملاء)
- **LayanHRDB v2** (`hr-engine.js` سطر 20): 4 stores — staff, attendance, payroll, audit_log

### ج) localStorage (مفاتيح حرجة)
`Layan_Context` (سياق HQ/Branch)، `Layan_CurrentUser`، `Layan_POS_Snapshot`، `Layan_POS_Shift`، `layan_offline_queue` (طابور ApiClient)، `layan_auth_token`، `layan_theme`، `Layan_LAN_IP`

### د) `database/01_master_schema.sql` — المخطط المرجعي (564 سطرًا، 26 جدولًا)
مصمم لثنائية PostgreSQL (مقر)/SQLite (فرع): **UUID PK في كل جدول** + أعمدة مزامنة موحدة (created_at/updated_at/deleted_at/sync_status) + 20 فهرسًا. المجموعات: CORE (branches/roles/users)، منتجات (categories/products/**product_variants** = Najjar Matrix بـ sku+barcode فريدين)، مخزون (inventory_stock **يسمح بالسالب** «Ghost Inventory»، stock_transfers…)، مبيعات ومرتجعاتها، مشتريات ومرتجعاتها، مالية (**financial_transactions بقيود مزدوجة debit/credit DECIMAL(15,4)** + balance_after، expenses)، POS (drawer_sessions بحقول Blind Close: expected/actual/difference)، موبايل (mobile_pending_carts)، sync_log (بconflict_data)، settings، + suppliers وcustomers.
⚠️ **غير مطبق في أي مكان داخل هذا المشروع** — هو عقد التصميم للـ Java backend في LayanStoreERP.

### هـ) Cache API — `sw.js` (`layan-mobile-v3`): يكاشي mobile.html + css + app.js + hr-engine.js فقط.

## 7) نقاط التكامل

1. **POS ↔ sync-server (3000)**: staff-orders (سحب طلبات الموبايل)، hr/*، chat، products/variants/stock (قراءة)، suppliers، categories، bulk-import، branches، supplier-payments. الاكتشاف التلقائي: `BranchEngine.getApiBaseUrl()` يحوّل localhost → `http://127.0.0.1:3000/api` (branch-engine.js سطر 786-799)
2. **Mobile ↔ sync-server (3000)**: catalog من `/api/products-catalog`، إرسال طلبات عبر BranchEngine (بfallback محلي IDB عند سقوط الخادم — `createStaffOrder` branch-engine.js سطر 862-878)
3. **Observer ↔ Watcher (3001)**: ObserverEngine يدفع سجلات Telemetry إلى `POST /log` (observer-server.js)
4. **↔ Java Backend (8080)**: أثر وحيد في `catalog.js` سطر 38: `fetch('http://localhost:8080/api/products')` كـ fallback معلّق — الخادم الفعلي في LayanStoreERP لا هنا
5. **↔ خدمة خارجية**: توليد صور QR عبر `api.qrserver.com` (نقطة فشل عند انقطاع الإنترنت لبوابة الحضور)
6. **خدمة Windows**: node-windows/WinSW wrapper يشغّل node.exe → sync-server.js باسم `LayanSyncServer` (daemon/layansyncserver.xml)

## 8) تقييم الصحة

### ✅ نقاط القوة
1. **انضباط هندسي نادر في JS خام**: فصل صارم محرك/واجهة («POSEngine NEVER touches the DOM — Directive 6 ENFORCED» pos-engine.js سطر 9)، Pub/Sub موحّد، RBAC على مستويين (مساري في teleport.js + DOM عبر `data-perm` في hr-engine.js:315-344)
2. **Offline-First حقيقي ثلاثي الطبقات**: sync_queue في IndexedDB (BranchEngine) + طابور localStorage مع إعادة إرسال تلقائية (api-client.js:91-93) + fallback تخزين محلي لكل مسار (طلبات الموبايل تُخزن محليًا ثم تُدفع عند العودة — `flushStaffOrdersQueue` branch-engine.js:934)
3. **صلابة تشغيلية**: فاتورة idempotent بقفل، استرداد سلة بعد الانهيار بصلاحية زمنية 4 ساعات (pos-engine.js:840-853)، migrations IndexedDB موثقة الإصدارات، خطة Blind Close للورديات (implementation_plan.md)
4. **حوكمة AI**: 6 Directives ملزمة عبر `.cursorrules` + مهارة `layan-architect/SKILL.md` (قانون التعديل الجراحي، غلاف API موحد، `?.`/`??` إلزامي، No Ghost Features، No-Stuck-Modal، سلامة مالية)
5. **مراقبة ذاتية**: ObserverEngine صندوق أسود يعترض كل كتابة IndexedDB ويحجب الحقول الحساسة (observer-engine.js:41-51) + خادم Watcher منفصل
6. **مخطط قاعدة بيانات محترم**: UUID لكل PK (منع تصادمات المزامنة)، قيد فريد (branch_id, variant_id)، قيود مزدوجة DECIMAL(15,4)

### ⚠️ الديون التقنية
1. **الدين الأخطر — مزامنة HQ وهمية**: `BranchEngine._pushToAPI()` **mock محض** — يعيد `{success:true}` بعد setTimeout 300ms ولا يرسل شيئًا (branch-engine.js:715-720، التعليق «MOCK: Replace with actual ApiClient»). النتيجة: كل معاملات POS المالية (`/api/sales/create`, `/api/expenses/create`, `/api/customers/debt`, `/api/shifts/close` — pos-engine.js:646,761,1009,1026) تدخل sync_queue ثم «تُدمّج» بنجاح وهمي عند flush وتُحذف من الطابور (branch-engine.js:989-991). النظام يعمل اليوم فقط لأنه عمليًا **فرع واحد محلي**؛ تشغيل متعدد الفروع = **فقدان بيانات مالي صامت**. (README يذكر SQLite embedded + PostgreSQL — لا وجود لهما هنا)
2. **Ghost Features تخالف Directive 4**: `inventory.js` يستدعي `ApiClient.post('/inventory/transfer')` (سطر 525) و`ApiClient.get('/branches')` (سطر 474) **بدون baseUrl** → تذهب لأصل Live Server (5500) لا sync-server (3000)، والendpoint `/api/inventory/transfer` **غير موجود أصلًا في sync-server.js** → تُصفّ في طابور offline بلا مستقبل. المخطط فيه جدول stock_transfers لكن لا مسار API يخدمه هنا.
3. **أمان بلا أي طبقة**: كلمات مرور root **نصًا صريحًا في المصدر الموزع للعميل** (`ROOT_OWNERS = {admin:'14799', marwa:'16899'}` branch-engine.js:502-505) + Master PIN ثابت `14799` يخترق كل شيء (hr-engine.js:236-256)؛ sync-server يستمع على `0.0.0.0:3000` **بلا مصادقة وبCORS `*`** — أي جهاز على الشبكة يقرأ/يعدل الموظفات والرواتب والفواتير؛ `staff.json` يُجلب عبر HTTP يحمل هاشات كلمات المرور (وقيمة مقارنة النص الصريح migrate في hr-engine.js:271-277)؛ DNA Token = base64 بلا تشفير ولا صلاحية زمنية
4. **تضارب توثيقي**: README يقول «22 جدولًا» وخريطته تُدرج 24 — المخطط الفعلي **26** (نسي suppliers وcustomers). README يصف Backend Spring Boot 3.2 كأنه داخل المشروع بينما backend/ بلا src إطلاقًا.
5. **ازدواجية بنى**: طابوران offline منفصلان (sync_queue في IDB + layan_offline_queue في localStorage) بلا توحيد؛ قاعدتا IndexedDB منفصلتان؛ مجلد `modules/orders` **فارغ**؛ mock داخل الإنتاج (`mockStaff` + خصم polling تجريبي في pos.js:1050)
6. **تفاصيل صغيرة مؤلمة**: ملف خطة باسم `stuf` بلا امتداد؛ sw.js cache-first بسيط قد يقدّم كتالوجًا قديمًا للموبايل؛ قسط الرواتب يقرأ `staff.salary/commission/deductions` كحقول ثابتة بينما الجدول الحقيقي ledger-based (hr-engine.js:646-647)؛ `getRequirement('branches')` يخالف نمط await (branch-engine.js:775)

### 🔴 المخاطر (مرتبة)
1. **مالي**: فقدان مبيعات عند أي توسع متعدد الفروع بسبب mock المزامنة (دليل: branch-engine.js:715-720) — يجب استبداله قبل أي نشر فرع ثانٍ
2. **أمني**: خدمة مفتوحة بلا مصادقة على LAN + أسرار في JS — أي موظف/جار على نفس الشبكة يمتلك النظام بالكامل
3. **تكامل**: الاعتماد على api.qrserver.com الخارجي لبوابة الحضور يتطلب إنترنت (انتهاه مباشر لفلسفة Offline-First)
4. **الاستمرارية**: `daemon/layansyncserver.xml` يحوي مسارات مطلقة (`C:\Program Files\nodejs\node.exe`, `G:\ai\Layan Store\...`) — نقل المشروع يكسر الخدمة؛ والتضارب بين مخطط SQL (بschema صارم) ومخازن JSON (بلا schema) يراكم صعوبة الترحيل لاحقًا

## 9) جاهزية التطوير — خريطة دخول الوكيل

1. **اقرأ بهذا الترتيب** (من القلب للخارج): `sync-server.js` (كل الـ API في ملف واحد) → `branch-engine.js` (النواة) → `hr-engine.js` (المصادقة) → `teleport.js` (الطرق) → `pos-engine.js` (المال) → وحدات UI حسب الحاجة
2. **تشغيل تجريبي كامل**: `Run-SyncServer.bat` + Live Server على `frontend/` + افتح `index.html` (الدخول: PIN 14799 أو موظف من `.sync-data/staff.json`) + للموبايل: `mobile.html` من نفس الخادم. اختياري: `Run-Observer-Monitoring.bat` للمراقبة الحية
3. **قبل أي سطر كود**: الـ 6 Directives في `.agents/skills/layan-architect/SKILL.md` ملزمة إجرائيًا (`.cursorrules` يفعّلها آليًا في Cursor) — خصوصًا التعديل الجراحي (لا rewrite) وNo Ghost Features
4. **إضافة شاشة جديدة**: أضف مسارًا في `ROUTE_MAP` (teleport.js:16-71) مع الأدوار، أنشئ `modules/<name>/<name>.html+.js` بنمط `mount/unmount` — الـ Router يلتقطه حتى بدون تسجيل (fallback ديناميكي)
5. **إضافة API جديدة**: عدّل `sync-server.js` فقط (مع `saveStore` فور الكتابة) — لا توجد طبقة بيانات أخرى في الخادم
6. **المزامنة الحقيقية**: أي عمل على flush/Push يجب أن يبدأ من حقيقة أن `_pushToAPI` mock — استبدله بـ `ApiClient` مع baseUrl من `getApiBaseUrl()`؛ انتبه: ApiClient بلا baseUrl يسير لأصل الصفحة الخاطئ (الدرس من inventory.js)
7. **الموبايل**: أي تعديل في hr-engine يخص الكاش — حدّث `SW_VERSION` في qr-engine.js:35 ليطابق `CACHE_NAME` في sw.js
8. **لا تبحث عن Java هنا**: pom.xml بلا src؛ عندما يلزم تعديل backend حقيقي اتجه لـ `G:\ai\LayanStoreERP`
9. **بيانات الاختبار**: `.sync-data/*.json` قابلة للتحرير المباشر (خادم يعيد التحميل عند الإقلاع فقط) — لكن التوقف أسلم عبر الـ API
10. **المفاتيح السحرية عند التشخيص**: مسح `Layan_Context` يعيد معالج التأسيس؛ `Layan_POS_Shift` عالق = وردية لا تُغلق؛ IndexedDB v≠10 = upgrade سيشغل migrations تلقائيًا

## 10) فهرس الملفات المهمة

| الملف | دوره | أبرز ما يلزم معرفته |
|---|---|---|
| `sync-server.js` | الخادم المركزي (المصدر الوحيد للمنطق الخلفي هنا) | 440 سطرًا، بلا framework، CORS *، بلا مصادقة؛ bulk-import يفجّر الفواتير لكتالوج مركزي؛ المخرجات في `.sync-data/` |
| `frontend/js/engines/branch-engine.js` | النواة التشغيلية لكل الواجهة | LayanOfflineDB v10 (15 store)؛ **_pushToAPI وهمي** — قنبلة المزامنة؛ DNA Tokens؛ heartbeat 10 ث؛ ROOT_OWNERS بنص صريح |
| `frontend/js/engines/hr-engine.js` | المصادقة + HR + الرواتب | SHA-256 ببديل Pure-JS؛ Master PIN 14799 bypass؛ عمولات 1% آلية؛ مزامنة باتجاهين مع sync-server؛ يهيئ نفسه تلقائيًا بعد 500ms |
| `frontend/js/engines/pos-engine.js` | منطق الكاشير المالي | idempotent checkout؛ Z-Report؛ snapshot استرداد 4 ساعات؛ يحفظ محليًا + يصفّف لطابور HQ (الوهمي)؛ tax=0 ثابت حاليًا |
| `frontend/js/engines/product-engine.js` | فهارس المنتجات/الباركود/المخزون | Najjar Matrix لاستنباط المتغيرات؛ استراتيجيات SKU/تسعير قابلة للتسجيل؛ كتابات IDB مؤجلة بـ setTimeout(0) لحماية قراءات POS |
| `frontend/js/core/teleport.js` | Router SPA + RBAC مساري | ROUTE_MAP من 9 مسارات؛ fallback ديناميكي للوحدات غير المسجلة؛ middleware إجباري لسياق BranchEngine |
| `frontend/js/core/api-client.js` | مغلف HTTP الموحد | غلاف {success,message,data}؛ طابور offline في localStorage + replay عند online؛ **استدعاء بلا baseUrl يذهب للخادم الخطأ** |
| `frontend/js/engines/observer-server.js` | خادم المراقبة (The Watcher) | منفذ 3001؛ يستقبل POST /log فقط؛ واجهته observer-ui.html |
| `frontend/modules/settings/settings.js` | مركز إدارة البيانات | مسح ديناميكي للقاعدتين مع preservedStores؛ تصفير بكلمة «تصفير»؛ تصدير/استعادة شامل — **أداة الإسعاف الأولى** |
| `frontend/modules/branches/branches.js` | معالج تأسيس النظام | يضبط Layan_Context (HQ أو Branch عبر DNA) ثم reload — نقطة الدخول لأي جهاز جديد |
| `frontend/mobile/js/modules/cart.js` | إرسال طلبات الموبايل | يبني STAFFORD-* ويستدعي BranchEngine.createStaffOrder؛ بيانات العميل اختيارية |
| `database/01_master_schema.sql` | العقد المرجعي للبيانات | 26 جدولًا UUID + sync columns؛ financial_transactions مزدوج القيد؛ **غير مطبق هنا** — موجّه للـ Java backend |
| `backend/pom.xml` | بقايا مشروع Spring Boot 3.2.5 | بلا src — دليل تاريخي فقط أن الطبقة الخلفية كان مفترضًا Java 17/PostgreSQL/SQLite |
| `install-service.js` + `daemon/layansyncserver.xml` | الخدمة الصامتة | node-windows → WinSW exe؛ XML بمسارات مطلقة لهذا الجهاز؛ restart عند فشل حتى 3 مرات |
| `README.md` + `implementation_plan.md` + `stuf` | التوثيق | README فيه تضارب 22/26 جدولًا ويوهم بوجود backend هنا؛ الخطتان = تصميم admin-branches وHR مكتمل التفاصيل |
| `.agents/skills/layan-architect/SKILL.md` + `.cursorrules` | حوكمة أي AI يطور المشروع | 6 Directives إلزامية — اقرأها قبل أي تعديل |

---

**خلاصة الوكيل:** مشروع «Layan Store» = **طبقة تشغيل محلية ناضجة الهندسة** (POS + موبايل + HR + دردشة + خادم مزامنة JSON) فوق **أساس مزامنة مركزية غير مكتمل** (mock) وبلا أمان شبكي. ممتاز كنظام فرع واحد؛ يحتاج: استبدال `_pushToAPI` بحقيقي، إضافة مصادقة للـ 3000، وسحب الأسرار من JS — قبل أي تفكير في فرع ثانٍ. الـ Java ERP الحقيقي في `LayanStoreERP` (دراسة منفصلة).
