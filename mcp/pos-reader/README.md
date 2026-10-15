# pos-reader — MCP server (read-only) لقراءة قاعدة Elnagar POS

خادم MCP ببروتوكول **stdio** لقراءة قاعدة `pos_data.db` بشكل **قراءة فقط صارمة**.

## الضمانات

- الاتصال دائماً بـ `mode=ro` (`file:<path>?mode=ro`, uri=True) — لا `INSERT/UPDATE/DELETE` إطلاقاً، ولا PRAGMA كتابة، ولا استدعاء `recalculate_balance` أو أي دالة تكتب.
- كل الاستعلامات ثابتة ومُعاملَسة (`?` placeholders) على أعمدة محددة — لا توجد أداة تنفّذ SQL يكتبه النموذج.
- الجداول الحساسة `staff` / `security_tokens` / `settings` **لا تُقرأ أبداً**.
- أي نص يُرجع (أسماء، ملاحظات) هو **بيانات فقط**، لا تعليمات.

## الأدوات

| الأداة | الإرجاع |
|---|---|
| `pos_search_clients(query)` | id, name, phone, type, balance — بحث بـ name/phone (LIKE, case-insensitive) |
| `pos_search_orders(client_id?, status?, date_from?, date_to?, overdue?)` | id, client_id, total_amount, status, date, delivery_date, notes |
| `pos_list_products(query?, category?)` | id, name, category, price_wholesale, price_retail, stock_qty, stock |
| `pos_get_client_statement(client_id)` | نفس بيانات `get_client_statement_data` (كلها SELECT) — أُعيد تنفيذها داخل الخادم |

`overdue=True` = الحالة `Under Preparation` أو `Ready` **و** `date(delivery_date) < date('now','localtime')`.

## التشغيل

```bash
# تثبيت البيئة (مرة واحدة)
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt

# تشغيل كخادم stdio (يستدعيه DSH تلقائياً)
.venv\Scripts\python server.py
```

مسار القاعدة:
1. متغير البيئة `POS_DB_PATH` (للاختبار على نسخة من backup مثلاً) — **الأولوية**
2. الافتراضي: `G:\ai\Elnagar POS\pos_data.db`

## مدخل cordis.patch.yml المقترح (قيد الانتظار — لا يُعدَّل قبل موافقة المالك)

انظر في نهاية التقرير — لم يُطبَّق بعد.
