# التقرير المعماري — المرحلة 0 (الأكتشاف)
**النسخة**: 1 — **تاريخ**: 2026-10-13 — **المرحلة**: 0 (اكتشاف بيئة العمل، قراءة فقط)
**الهدف**: فهم البنية الحالية لنظام «النجار برنت» قبل الانطلاق إلى بناء المنسق العام (Phase 1).

---

## 1. الخلاصة التنفيذية
البنية الحالية تعمل بأربع طبقات متراصة: **قاعدة SQLite محلية** (قلب برنامج الورشة/N0 تدخل في نقطة البيع — `pos_data.db`)، **قاعدة Supabase سحابية** (مرآة + طابور أوامر)، **جسر elnagarprint** (تليجرام مستقل لا يُمَس)، **بوت البرنامج** `telegram_bot/bot.py` (متوقف مؤخرًا بقرار المالك — النسخة السحابية Webhook ستستقبل رسائل البوت حصريًا أثناء إغلاق المحل). لا يوجد «main.py» لوجستكي موحّد — `main.py` هو عميل الجوال (Flet). المهم أن البنية غير متسقة باسم الملفات والمسارات الثلاث المتوازية، ومهمة المنسق ستُبنى كطبقة رابعة لا تستبدل أيًا منها.

---

## 2. خرائط البنية المعمارية

### 2.1 المكوّنات الرئيسية (خريطة النص البصري)
```
                     ┌──────────────────────────────────────────────────┐
                     │            تيليجرام  (@Marwty_bot — @@)           │
                     └───────────────┬──────────────────────┬───────────┘
                                     │ Webhook (سحابة)       │ (متوقف محليًا)
          ┌──────────────────────────▼───────────┐  ┌────────▼──────────────────┐
          │  cloud/cloud_webhook_server.py (Replit)│ │  telegram_bot/bot.py (Poller)│
          │  - يحقق المالك (OWNER_TELEGRAM_ID)      │  │  - /neworder, /client, ...    │
          │  - ذاكرة = مرآة Supabase                │  │  - sheets_queue → Sheets    │
          │  - يكتب في commands (pending)         │  └─────────────────────────────┘
          └──────────────────┬────────────────────┘
                  ┌──────────▼──────────────┐
                  │   Supabase  (Cloud-Aa)   │
                  │  clients/products/orders │
                  │  order_items/transactions│
                  │  commands (طابور)        │
                  └────┬─────────┬───────────┘
                       │ push_mirror (LOCAL→CLOUD)
                       │ pull_queue (CLOUD→LOCAL, تنفيذ محلي)
          ┌────────────▼─────────▼───────────────────────────┐
          │   cloud/supabase_sync.py (HermesSyncManager)     │
          │   start_sync.bat (دايمون 60 ثانية)               │
          └───────────────────────┬───────────────────────────┘
                                  │ (مسارات رسمية: database.py)
          ┌───────────────────────▼───────────────────────────┐
          │   pos_data.db (SQLite محلي)  +  برنامج الورشة      │
          │   app.py (Eel 7777) / desktop_sidebar (8888)        │
          │   mobile_local_api_server (7788) / firebase       │
          └──────────────────────────────────────────────────────┘
```

### 2.2 قاعدة البيانات المحلية (`pos_data.db` / SQLite)
الجداول الخمسة الأساسية (+ non-core: staff, security_tokens, settings — **يمنع قراءتها** بقرار المالك):
| الجدول | أعمدة محلية (المدخل المعتمد) |
|---|---|
| `clients` | id, name, phone, type, balance, notes |
| `products` | id, name, category, price_wholesale, price_retail, stock_qty, sort_order, stock, last_cost_price |
| `orders` | id, client_id, total_amount, status, date, local_image_path, image_url, unique_hash, notes, source_path, synced, delivery_date, custom_notes |
| `order_items` | id, order_id, product_id, product_name, qty, price, total |
| `transactions` | id, client_id, type, amount, notes, date, category, user, related_ref, is_verified, is_savings, material_cost_recovery, net_profit_portion, expense_type |

### 2.3 قاعدة Supabase السحابية (مخطط فعلي — تحققت منه قراءةً فقط)
| الجدول | أعمدة السحابة الفعلية |
|---|---|
| `clients` | id, name, type, balance, notes (**لا phone**) |
| `products` | id, name, category, price_wholesale, price_retail, stock_qty, last_cost_price (**لا sort_order/stock**) |
| `orders` | id, client_id, total_amount, status, date, notes, delivery_date, custom_notes (**لا image_path/source_path/synced**) |
| `order_items` | id, order_id, product_id, product_name, qty, price, total (مطابق) |
| `transactions` | id, client_id, type, amount, notes, date, related_ref (**لا category/user/is_verified/material/net_profit/expense_type**) |
| `commands` | id, action, payload(jsonb), status, reason, idempotency_key, created_at |

الخلاصة: **مخطط السحابة أضيق من المحلي** — يجب أن يقرأ المنسق من السحابة بحذر (الأعمدة المتاحة فقط) وأي مجال أوسع يجب تنظيمه في تصميم مستقبلي بموافقة المالك.

### 2.4 طابور الأوامر (`commands`)
- الاتجاه: **سحابة → محلي** (الوكيل المحلي يسحب).
- صيغ `action` المعروضة اليوم: `create_order / create_client / add_product / record_payment / system_command`.
- `system_command` payload: `{"cmd": "screenshot"|"shutdown"|"reboot"}`.
- التنفيذ المحلي: `supabase_sync.py` → `database.py` الرسمية أو `os` (لقطة/إغلاق/إعادة تشغيل) ثم `status=applied|failed` مع `reason`.

---

## 3. جرد الملفات الضرورية (المختارة — لا كل شيء)

### 3.1 نواة تشغيل البرنامج
| الملف | الدور |
|---|---|
| `app.py` | منصة الورشة Eel (7777) — الواجهة + نقاط النهاية (73K) |
| `desktop_sidebar.py` | الشريط الجانبي (8888) |
| `mobile_local_api_server.py` | خادم الجوال (7788) |
| `database.py` | **نواة البيانات** — كل الدوال الرسمية (الحسابات، الطلبات، الحركات، المزامنة) (133K) |
| `financial_engine.py` | المحرّك المالي (الخزينة، الديون، الحوافز) |
| `file_ops_engine.py` | عمليات الملفات/التصميم |
| `laser_engine.py` | حساب الليزر/القص |
| `elnagar_service_manager.py` | مدير الخدمات (bot, api, sidebar, firebase…) |
| `run_app.bat` → `start_silent.vbs` → `elnagar_service_manager.py` | سلسلة الإقلاع |

### 3.2 بوت التليجرام (`telegram_bot/`)
`bot.py` (109K): /start /help /orders_today /client /products /neworder + محادثة + صور | `sheets_queue.py` | `openrouter_client.py` (ذكاء خارجي) | `config.py` (.env.telegram) — **متوقف مؤقتًا حاليًا** (قرار).

### 3.3 طبقة السحابة (جديد 2026-10-12)
| الملف | الدور |
|---|---|
| `cloud/supabase_sync.py` | **HermesSyncManager**: push_mirror / pull_queue / query_* (يعمل، اختُبر حيًا) |
| `cloud/cloud_webhook_server.py` | **مروه السحابية** (Flask/Webhook) — للرفع على Replit (جاهز، لم يُرفع بعد) |
| `start_sync.bat` | دايمون محلي 60 ثانية (غير مشغّل حاليًا) |
| `.env` | أسرار Supabase/Dahl/Telegram (مستثنى .gitignore) — التوكن ميدخَل الآن (اختيار ب) |

### 3.4 المزامنة مع Google Sheets (منظومة قائمة)
- `google_sheet_realtime_sync.py` (دفع حي من DB→Sheet عند حفظ طلب — باهظ `_load_row_cache`).
- `sync_pos_to_sheet.py` (مرآة يدويّة كل 25 تبويب) + `backup_google_sheet.py`.
- `google_api_sync.py` (سحب قديم من نموذج — ليس مربوطًا بالجدول الحالي).
- تقرير تصميم كامل: `memory/reports/report-2026-10-12-google-sheet-sync-design.md`.

---

## 4. اكتشافات وملاحظات سلامة & اتساق (مهمة)
1. **`main.py` ليس البوت**: هو عميل الجوال (Flet, mobile.db). بوت التليجرام الحقيقي في `telegram_bot/bot.py`. إذا كانت نية الخطة أن «main.py» هو نقطة الدخول، فيجب توضيح ذلك لتجنّب خطأ التوجيه في المراحل التالية.
2. **تعارض بيئة العمل المذكورة في الخطة**: الخطة تذكر «خادم اتصال Long Polling يعمل» — الحالة الراهنة: **الـ Poller متوقف بقرار المالك (17:07)** والـ Webhook السحابي هو المستقبل الوحيد أثناء إغلاق المحل. هذا ليس خطأ بل قرارُك — يردّ به التقرير الوضع الحقيقي.
3. **مخطط السحابة أضيق من المحلي** → أي sync لا يرفع `phone/stock/sort_order/صور الأوامر/أعمدة المصاريف`؛ إن احتاج المنسق مثل هذه البيانات، يجب توسعة مخطط Supabase (قرار المالك) أو قراءتها محليًا فقط.
4. **ملفات أسرار متعددة**: `.env` + `.env.telegram` + OAuth `token.json/credentials.json` — كلها مستثناة في `.gitignore` (تحققت: `.env`, `.env.*`, `credentials*`, `token*`, `*.pickle`, `firebase_service_account.json`).
5. **تناثر النسخ الاحتياطية**: multiple `*.bak-2026-10-12*`, `Backups/`, `SAFE_BACKUP_BEFORE_REPAIR/`, `_quarantine_unused_*/` — وفيرة وتستهلك مساحة؛ مقترح أن يعمل «المدقق» على تنظيمها (أرشيف مضغوط) بموافقة المالك.
6. **`backend_crash.log` 636KB** (13/10/2026 08:14) — تشير إلى سجل إنهيارات ضخم يستحق نظرة في Phase 2 (طبيب البيانات).

---

## 5. خارطة الطريق المقترحة (من نص الخطة — تُنفَّذ بالترتيب وبموافقة)
| المرحلة | الوحدة | المدخل | المخرجات |
|---|---|---|---|
| **0** | اكتشاف ✓ (هذا التقرير) | القراءة | اعتماد التقرير |
| **1** | المنسق العام (Orchestrator) | Webhook + DSH | توجيه نية المستخدم → الوكيل المختص |
| **2** | طبيب البيانات + حارس التطابق | routine صباحي | فحص أسعار/ملفات/أرصدة + سياسة تسعير (+30%) |
| **3** | CRM & SCM | سجلات & حالات الطلبات | أنماط العملاء + تنبيهات الجاهزية المتأخرة |
| **4** | CFO (Ledger) | خزينة/ديون/طرق دفع | تقارير مستحقات + هوامش + تسعير ديناميكي (بموافقة) |
| **5** | التسويق (Bundles) | منتجات راكدة | باقات بخصومات مقترحة |
| **6** | الإنتاج (Production) | خامات/ماكينات | تسعير دقيق + تجميع طلبات الروتين الصباحي |
| **7** | النظام/الكودر | أوامر نظام + مراجعة بايثون | تنفيذ أوامر + تحديثات آمنة |

**ملاحظة الحرّاس**: لا تنفيذ ولا كتابة بلا موافقة صريحة — لا في المرحلة 1 ولا بعدها (عدا ما أذن به المالك صراحةً).

---

## 6. ماذا بعد (للمالك)
- **اعتماد** هذا التقرير (أو طلب تعديلاته) لبدء المرحلة 1 — بناء المنسق العام.
- قرار مطلوب مبكرًا: هل نكتب `cloud_webhook_server.py` (مروه السحابية) باعتباره قاعدة المنسق، أم نبني المنسق داخل المحيط المحلي عبر `database.py`/DSH؟ (مع تذكير: القرار ب ربط Webhook جاهز للرفع على Replit — بيدك).
- قرار: هل نوسّع مخطط Supabase ليشمل `phone/stock/صور الطلبات/أعمدة المصاريف` الآن أم نكتفي بالمخطط الحالي؟
