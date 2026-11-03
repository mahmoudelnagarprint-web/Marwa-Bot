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

## التشغيل عبر HTTP (LobeChat على الخادم — وخصوصاً داخل Docker)

```bash
# نفس الجهاز (الوضع القديم)
POS_READER_HTTP=1 POS_READER_PORT=8777 python server.py
# → http://127.0.0.1:8777/mcp

# داخل حاوية، ومع حاويات أخرى على نفس شبكة compose (LobeChat في Docker)
POS_READER_HTTP=1 POS_READER_HOST=0.0.0.0 POS_READER_PORT=8777 python server.py
# → http://pos-reader:8777/mcp  (أو host.docker.internal:8777 من الشبكة المضيفة)
```

### ثلاث نقاط لازمة وإلا يفشل الاتصال من LobeChat

1. **`POS_READER_HOST=0.0.0.0`**: الافتراضي `127.0.0.1` يعني loopback داخل الحاوية نفسها فقط، فأي حاوية أخرى تحصل على `ECONNREFUSED`.
2. **`POS_READER_ALLOWED_HOSTS`**: FastMCP يُشغّل حماية DNS-rebinding تلقائياً عندما يُبنى على host محلي، فيرد **421 Misdirected Request** على أي `Host` غير مسموح (مثل `pos-reader:8777`). الافتراضي يسمح بـ `127.0.0.1 / localhost / [::1] / host.docker.internal / pos-reader` — أضف أي اسم آخر هنا مفصولاً بفاصلة.
3. **قاعدة بيانات WAL تحتاج مجلداً قابلاً للكتابة**: قراءة `mode=ro` على قاعدة WAL تحتاج إنشاء `pos_data.db-shm` بجانب الملف، وتركيب المجلد بـ `:ro` يعطي `unable to open database file`. الاتصال نفسه يبقى قراءة فقط في الكود.

## مدخل cordis.patch.yml المقترح (قيد الانتظار — لا يُعدَّل قبل موافقة المالك)

انظر في نهاية التقرير — لم يُطبَّق بعد.
