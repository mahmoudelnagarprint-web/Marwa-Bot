# تحقق مستقل — «إجمالي المديونيات الحية = 1040 جنيه»

**المحققة:** سلمى (task-3) — محقق مستقل، الشك المنهجي.
**التاريخ/الوقت:** 2026-10-18، ~00:14 → 00:35 (Africa/Cairo).
**القاعدة المتبعة:** لم أقرأ أي تقرير لمروة ولا فيجن ولا الـ lead قبل إنتاج رقمي. كل رقم أدناه أعدت إنتاجه بنفسي من المصدر الخام.

---

## 1. الحكم النهائي

> **الرقم 1040 جنيه صحيح ومُعاد إنتاجه بالكامل — لكن بشرطين لابد أن يُقالا صريحًا:**
>
> 1. **مصدره الوحيد** هو `G:\ai\Elnagar POS\pos_data.db` (عمود `clients.balance`)، وهو مصدر **حيّ فعلًا** (عملية شغّالة تخدمه الآن)، لكن **بياناته متجمدة عند 16/10/2026** — مفيش أي حركة بتاريخ 17/10 ولا 18/10. فالوصف الدقيق: «الرصيد الحالي في المصدر الحيّ = 1040»، وليس «مديونيات اليوم».
> 2. **1040 = المديونيات (الآجل)** بتعريف المستحقات على العملاء. لكن **نفس التطبيق الحيّ يعرض رقمًا آخر (3155) تحت اسم «إجمالي الديون»** على نفس الشاشة — انظر القسم 6. فلو حد شاف كارت «إجمالي الديون» هيقول 3155، ولو شاف «إجمالي الآجل» هيلاقي 1040.

**الفرق عن 1040 = صفر.** 240 + 350 + 250 + 200 = **1040 بالظبط**.

**لم أستطع تأكيد:** أن أي رقم من دي يعكس حركة **17/10 أو 18/10** — لأن مفيش أي حركة بالتواريخ دي في أي مصدر محلي.

---

## 2. أين اشتغلت ومن أين قرأت (المصادر)

| # | المصدر | النوع | الحالة |
|---|--------|------|--------|
| S1 | `G:\ai\Elnagar POS\pos_data.db` | SQLite (تطبيق Python حيّ) | ✅ قراءة مباشرة read-only |
| S2 | `http://127.0.0.1:7777` (API التطبيق الحيّ) | HTTP حيّ | ✅ استعلام مباشر |
| S3 | `G:\ai\Naggar Print POS Agent\pos_data.db` | SQLite قديم | ✅ قراءة مباشرة read-only |
| S4 | PostgreSQL `localhost:5432/layan_erp` | Spring Boot backend | ✅ psql مباشر (الـ backend نفسه متوقف) |

الأدوات: `psql` من `C:\Program Files\PostgreSQL\18\bin\psql.exe` + Python 3.11 (`Vision-Lab\.venv`) بـ `sqlite3` و`urllib`.
**كلمة مرور Postgres** قُرئت آليًا من `application.properties` → `$env:PGPASSWORD` داخل نفس الأمر. **لم تُطبع في أي مخرج ولا في هذا التقرير** (أي إشارة إليها هنا `***`).

---

## 3. تعريف «المديونية» — من الكود الفعلي، لا من الافتراض

لم أفترض اسم العمود. رجعت للكود الحيّ وطلعت التعريف الحقيقي:

**التعريف الرسمي (عمود `clients.balance`):**

- `app.py:169-180` — نقطة النهاية `GET /api/clients`:
  ```python
  clients = db.get_all_clients()
  customers_data = [{ 'id': c['id'], 'name': c['name'], 'phone': c['phone'],
                      'type': c['type'], 'total_debt': c['balance'] } for c in clients]
  ```
- `database.py:501-513` — `get_all_clients()` = `SELECT * FROM clients` ثم `c_dict['balance'] = (c_dict['balance'] or 0)`
  (لاحظ التعليق في `database.py:508` بيقول «Add Under Prep Value to Balance for Display» — **الكود لا يضيف أي شيء**، بس `or 0`. ده تعليق مضلل.)
- `database.py:2955-2967` — `get_customers_stats()`: `total_debt = sum(c.get('balance', 0) for c in clients)`
- `database.py:1697` — نسخة مكررة: `SELECT COALESCE(SUM(balance), 0) FROM clients`
- `app.py:1713` — `total_receivables` في `/api/dashboard-summary`:
  `(SELECT IFNULL(SUM(balance),0) FROM clients WHERE balance > 0)`

**الخلاصة:** المديونية = `SUM(clients.balance)`، والأرصدة كلها موجبة أو صفر (لا سالب)، فـ `SUM(balance)` و`SUM(balance WHERE >0)` بيدّوا **نفس الرقم**. ده التعريف الصحيح لأنه هو اللي الكود بيعرضه في `/api/clients` و`/api/dashboard-summary` و`get_customers_stats` — يعني هو اللي المستخدم بيشوفه.

---

## 4. الحِسبة المستقلة — ثلاث طرق مختلفة، نفس الرقم

### الطريقة 1: قراءة SQLite مباشرة (read-only URI)
```python
sqlite3.connect("file:G:/ai/Elnagar POS/pos_data.db?mode=ro", uri=True)
```
| المقياس | القيمة |
|---|---|
| عدد العملاء | 56 |
| `SUM(balance)` | **1040.0** |
| `SUM(balance) WHERE balance > 0` | **1040.0** |
| `SUM(balance) WHERE balance < 0` | 0 |
| عدد العملاء ذوي رصيد موجب | 4 |

العملاء الأربعة بالاسم والرقم الخام:

| id | الاسم | balance | النوع |
|---|---|---|---|
| 63 | زينب | 240.0 | Wholesale |
| 107 | +20 10 90357093 | 350.0 | Retail |
| 108 | اسراء هلال | 250.0 | Wholesale |
| 109 | 201096899777 | 200.0 | Retail |
| | **المجموع** | **1040.0** | |

### الطريقة 2: API الحيّ `/api/clients`
جمعت بنفسي قيم `total_debt` لكل الـ 56 عميل:
```
count: 56
SUM(total_debt) = 1040.0
nonzero count = 4
   (107, '+20 10 90357093', 350.0, 'Retail')
   (109, '201096899777', 200.0, 'Retail')
   (108, 'اسراء هلال ', 250.0, 'Wholesale')
   (63, 'زينب ', 240.0, 'Wholesale')
```

### الطريقة 3: API الحيّ `/api/dashboard-summary`
```json
{"dashboard_summary":{"clients_count":56,"debt_clients_count":4,
 "total_receivables":1040.0,"orders_total":58,"products_count":105,
 "delivered_count":52,"delivered_value":15718.5,
 "under_preparation_count":6,"under_preparation_value":2115.0,
 "orders_today":0,"daily_revenue":0,"ready_count":0}, "success":true}
```

**الطرق الثلاث اتفقت على 1040.0 حرفيًا، وعدد المدينين 4 في الثلاثة.**
وأتأكد إن الـ API فعلًا قرأ نفس الملف S1 بدليل تطابق البصمة: `clients_count=56`، `orders_total=58`، `products_count=105` — ودي أرقام `pos_data.db` بتاع Elnagar بالظبط (S3 عندها 52/50/106، فمستحيل يكون هو).

### إثبات إن العملية الحيّة فعلًا على 8888/7777
- PID **3788** = `pythonw.exe`، بدأ **2026-10-17 23:57:01**، يملك المستمع على `127.0.0.1:8888` و`0.0.0.0:7777`.
- `GET http://127.0.0.1:7777/index.html` → HTTP 200، 284,341 بايت من HTML.
- `GET http://127.0.0.1:8888/` → HTTP 200، 293,066 بايت.
- `backend_crash.log` آخر سطر: `GET /api/dashboard-summary HTTP/1.1" 200` بتاريخ 2026-10-18 00:23:12 — يعني API شغّال بيُخدِم الآن.

---

## 5. إثبات تجمّد SQLite عند 16/10 (الادعاء المضاد)

### S1 — `G:\ai\Elnagar POS\pos_data.db` (المصدر الحيّ)
| المقياس | القيمة الخام |
|---|---|
| حجم الملف | 245,760 بايت |
| **mtime للملف** | **2026-10-16 23:39:36** |
| آخر طلب | **#334 — 2026-10-16 16:22:56** (Delivered، 150.0) |
| مدى الـ orders | id من 262 إلى 334، عدد 58 |
| آخر حركة مالية | **2026-10-16 20:39:12** (`Income 150.0`, "Delivery Order #334 - Cash") |
| آخر سطر operation_logs | 2026-10-16 20:39:25 |
| الحالة | Delivered 52 (15,718.50) / Under Preparation 6 (2,115.00) |
| **عدد الطلبات بتاريخ 17/10 أو 18/10** | **صفر** |

✅ **تأكيد مباشر لادعاء الـ lead:** «آخر طلب #334 بتاريخ 16/10» صحيح حرفيًا.
✅ و`google_sheets_sync.log` آخر سطر: `Realtime sync order #334` بتاريخ **2026-10-16 19:23:10** — دليل ثالث مستقل على إن #334 هو آخر طلب.
⚠️ لكن **«اليوم» ≠ 16/10**. دلوقتي 18/10 00:35. العملية الحيّة شغّالة من 17/10 23:57 و**لم تكتب أي صف جديد** في `pos_data.db` (الـ mtime لسه 16/10 23:39). يعني الرقم 1040 هو **بصمة آخر لحظة عمل (16/10)، مش حالة اليوم**.

### S3 — `G:\ai\Naggar Print POS Agent\pos_data.db` (القديم)
| المقياس | القيمة الخام |
|---|---|
| حجم الملف | 86,016 بايت |
| **mtime للملف** | **2026-10-16 22:53:24** ✅ مطابق تمامًا لادعاء «متوقف عند 16/10 22:53» |
| آخر طلب | id **323** — **2026-08-31** |
| آخر حركة مالية | **2026-09-03** |
| عدد العملاء | 52 |
| **`SUM(balance)`** | **0** (كل الـ 52 صفر — مفيش ولا عميل مدين) |
| عدد الطلبات | 50، كلها Delivered |

❗ **تصحيح مهم:** الـ 16/10 22:53 هو **تاريخ تعديل الملف على القرص فقط**، وليس تاريخ بيانات. **أحدث سجل أعمال جوّه هو 2026-09-03** (والطلبات 2026-08-31). يعني بيانات الملف ده أقدم من 16/10 بأسبوعين تقريبًا، ومديونيتها **صفر** — فمستحيل تكون مصدر الـ 1040.

---

## 6. فخاخ اكتشفتها: نفس التطبيق، ثلاث «مديونيات» مختلفة

دي أهم حاجة في التقرير. الاسم `total_debt` مستخدم بأكثر من معادلة في نفس الكود:

| # | المعادلة | المصدر في الكود | الناتج على البيانات الحالية |
|---|---|---|---|
| **أ** | `SUM(balance)` | `database.py:1697`، `database.py:2967`، `app.py:1713` (WHERE >0) | **1040** ✅ |
| **ب** | `SUM(balance) + SUM(orders.total_amount WHERE status='Under Preparation')` | `database.py:1644-1646` | **1040 + 2115 = 3155** ⚠️ |
| **ج** | `SUM(balance) WHERE balance < 0` | `mobile_local_api_server.py:207` و`:341`، `firebase_mirror_from_pos.py:65` | **0** 🐞 |

**إثبات إن ده مش كلام نظري — الرقمين ظاهرين على نفس الشاشة الحيّة:**

- رفعت `http://127.0.0.1:7777/index.html` (**الصفحة المخدومة فعلًا**، 284,341 بايت) ولقيت فيها حرفيًا:
  ```
  createStatCard("إجمالي الديون",  (stats.total_debt || 0)...)   ← stats من eel.py_get_dashboard_stats()
  createStatCard("إجمالي الآجل",   stats.total_debt...)          ← stats من eel.py_get_customers_stats()
  ```
- و`backend.py:559-566` بيعرض الدالتين على Eel: `py_get_dashboard_stats` و`py_get_customers_stats`.
- `py_get_customers_stats` → التعريف **أ** = **1040**. و`py_get_dashboard_stats` → التعريف **ب** = **3155**.
- (تحققت من مكوّن 2115 بشكل مستقل: `SELECT SUM(total_amount) FROM orders WHERE status='Under Preparation'` = **2115.0** على 6 طلبات — والـ API الحيّ نفسه رجّع `under_preparation_value: 2115.0`.)

**يعني:** اللي بيدوّر على «إجمالي المديونيات» في التطبيق الحيّ ممكن يشوف **3155** أو **1040** حسب الكارت اللي بصّ فيه. الرقم المدَّعى 1040 يطابق التعريف الصحيح (المستحقات على العملاء)، و**3155 مبالغ فيه** لأنه بيخلط المستحقات الفعلية بقيمة شغل لسه «تحت التجهيز» (مش دين على عميل).

**والفخ الثالث أخطر ميدانيًا:** مسار الموبايل (`mobile_local_api_server.py`) ومسار مزامنة Firebase (`firebase_mirror_from_pos.py`) بيجمعوا **الأرصدة السالبة** (`balance < 0`) ويسمّوها `total_receivables`. على البيانات الحالية الناتج **صفر** — يعني أي تطبيق موبايل أو أي مزامنة سحابية مبنية على المسار ده هتقول **«مفيش مديونيات»** وهي غلط. **ده اللي ممكن يخلي رقم 1040 يختفي من قدام المالك.**

---

## 7. PostgreSQL `layan_erp` — الناتج 0، مش 1040

`G:\ai\codex\LayanStoreERP` → `spring.datasource.url=jdbc:postgresql://localhost:5432/layan_erp`. اتصلت مباشرة بـ psql:

| الاستعلام | الناتج |
|---|---|
| `select count(*) from customers` | 11 (منهم 6 غير محذوفين) |
| `select coalesce(sum(current_balance),0) from customers` | **0** |
| `SUM(current_balance) WHERE current_balance > 0 AND is_deleted=false` ← **نفس تعريف `AccountingController.java:166`** | **0** |
| `SUM(current_balance) WHERE current_balance < 0` | 0 |
| `select count(*), max(date) from transactions` | 8 صفوف، آخرها **2026-09-24 18:57:41** |
| `select transaction_type, count(*), sum(amount) from customer_ledger group by 1` | **CASH_PURCHASE فقط** — 8 صفوف، 2080.00 |
| المديونية بتعريف الـ backend نفسه (`CustomerController.java:59-74`) = `SUM(CREDIT_PURCHASE - PAYMENT - RETURN)` من `customer_ledger` | **0 لكل الـ 11 عميل** |

كل الـ 8 فواتير نقدية (`Cash`، `paid_amount = total_amount`)، ومفيش ولا عملية `CREDIT_PURCHASE` واحدة في الـ ledger — فمفيش دين أصلًا.

**قاعدة `layan_erp` بياناتها أقدم من المصدر الحيّ (24/09 مقابل 16/10) وأرصدتها صفر. لو أي حد حسب 1040 من هنا فهو غلط.**

---

## 8. هل الـ Backend الحي (18080) شغّال؟ — لا

| الفحص | الناتج |
|---|---|
| `Get-NetTCPConnection -LocalPort 18080 -State Listen` | **فاضي** (مفيش مستمع) |
| `Get-Process java, javaw` | **فاضي** (مفيش أي عملية Java) |
| `Invoke-WebRequest http://127.0.0.1:18080/` | ❌ رفض الاتصال |
| `Invoke-WebRequest http://localhost:18080/` | ❌ timeout |

✅ **تأكيد مباشر لادعاء الـ lead:** Spring Boot متوقف فعلًا. **فمفيش «API حيّ» على 18080 أقارن بيه** — المقارنة الحيّة الوحيدة الممكنة كانت على 7777/8888 (تطبيق Python)، وهي اللي عملتها في القسم 4.

---

## 9. إيه اللي **لم** أتحقق منه (بصراحة)

1. **مصادر سحابية/Firebase/Supabase:** ملف `cloud\supabase_sync.log` آخر تعديل 17/10 22:45 — **لم أفحص محتواه ولا محتوى السحابة**. لو فيه بيانات هناك بعد 16/10، رقم الـ 1040 المحلي ممكن يكون ناقص. (ملاحظة: مسار `firebase_mirror_from_pos.py` نفسه فيه باج الإشارة الموصوف في القسم 6، فالثقة في مرآة Firebase منخفضة أصلًا.)
2. **مفيش أي حركة بتاريخ 17/10 أو 18/10 في أي مصدر محلي** — فلا أستطيع إثبات أو نفي إن المالك حصّل أو باع حاجة في اليومين دول. **«اليوم» في ادعاء المالك غير مُثبت؛ المثبت هو حالة 16/10.**
3. **أرصدة الـ 4 مدينين مبنية على عمود محفوظ (`clients.balance`) مش محسوبة من الطلبات.** الكود عنده دوال إعادة احتساب (`database.py:1024-1043` "Clear old/delivered debt"، و`:1144-1147` `theo_balance`) — **لم أشغّلها ولا أعدت احتساب الأرصدة من الطلبات والمدفوعات**، لأن ده كان هيعدّل بيانات الإنتاج. فمش أقدر أشهد إن الـ 240/350/250/200 مطابقة 100% لسجل الطلبات والدفعات لكل عميل.
4. **لم أراجع** `database.py.bak-*` ولا النسخ الاحتياطية (١٥٠+ نسخة في `Backups\`) — استخدمت الملف الحيّ فقط.
5. **لم أقرأ تقارير مروة/فيجن** (التزامًا بالتعليمات، وكانت غير موجودة وقت إنتاج رقمي أصلًا).

---

## 10. كيف تعيد إنتاج كل رقم بنفسك

```powershell
# 1) المديونية من SQLite الحيّ (بدون أي كتابة)
$py = "G:\ai\Naggar Print POS Agent\Vision-Lab\.venv\Scripts\python.exe"
$env:PYTHONIOENCODING='utf-8'
$py -c "import sqlite3; c=sqlite3.connect('file:G:/ai/Elnagar POS/pos_data.db?mode=ro',uri=True); print(c.execute('select coalesce(sum(balance),0), count(*) from clients where balance>0').fetchall()); print(c.execute('select max(date) from orders').fetchone()); print(c.execute('select max(date) from transactions').fetchone())"

# 2) المديونية من الـ API الحيّ
(Invoke-WebRequest http://127.0.0.1:7777/api/dashboard-summary -UseBasicParsing).Content

# 3) مفيش كتابة في أي قاعدة بيانات — كل الاتصالات read-only / GET فقط.
```

```powershell
# 4) PostgreSQL (الباسورد لا يُطبع: يُقرأ ثم يوضع في متغير بيئة داخل نفس الأمر)
$p = "G:\ai\codex\LayanStoreERP\src\main\resources\application.properties"
$line = (Get-Content $p) | Where-Object {$_ -match '(?i)^\s*spring\.datasource\.password\s*='} | Select-Object -First 1
$val = ($line -split '=',2)[1].Trim()
if ($val -match '^\$\{([^:}]+)(:([^}]*))?\}$') { $e=[Environment]::GetEnvironmentVariable($Matches[1]); $val = if($e){$e}else{$Matches[3]} }
$env:PGPASSWORD = $val
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -h localhost -d layan_erp -c "SELECT COALESCE(SUM(current_balance),0) FROM customers WHERE current_balance > 0 AND is_deleted = false;"
```

---

## 11. ملحق: سجل الأدلة الخام

| # | الدليل | القيمة |
|---|---|---|
| E1 | `pos_data.db` (Elnagar) mtime | 2026-10-16 23:39:36 |
| E2 | `pos_data.db` (Elnagar) last order | #334 @ 2026-10-16 16:22:56, Delivered, 150.0 |
| E3 | `pos_data.db` (Elnagar) last transaction | 2026-10-16 20:39:12 |
| E4 | `pos_data.db` (Naggar) mtime | 2026-10-16 22:53:24 |
| E5 | `pos_data.db` (Naggar) last business record | 2026-09-03 (transactions) / 2026-08-31 (orders) |
| E6 | `pos_data.db` (Naggar) `SUM(balance)` | 0 |
| E7 | `layan_erp` last transaction | 2026-09-24 18:57:41 |
| E8 | `layan_erp` `SUM(current_balance)` | 0 |
| E9 | Live `GET /api/dashboard-summary` | `total_receivables: 1040.0`, `debt_clients_count: 4` |
| E10 | Live `GET /api/clients` | جمع `total_debt` = 1040.0 على 56 عميل |
| E11 | العملية الحيّة | PID 3788 `pythonw.exe`, بدأت 2026-10-17 23:57:01, تخدم 7777 + 8888 |
| E12 | آخر مزامنة Google Sheets | order #334 @ 2026-10-16 19:23:10 |
| E13 | Spring Boot 18080 | مفيش مستمع، مفيش عملية java |
| E14 | `get_dashboard_stats()` (ب) على البيانات الحالية | 1040 + 2115 = 3155 |
| E15 | الصفحة المخدومة `index.html` | فيها كارت «إجمالي الديون» (ب) وكارت «إجمالي الآجل» (أ) معًا |

---

**التوقيع:** سلمى — محقق مستقل. لم أعدّل أي ملف غير هذا التقرير، ولم أكتب في أي قاعدة بيانات (كل الاتصالات read-only / GET).