# 📐 عقد ترقية «أفكاري / فوفا» — Notebook v2

> مكتوب من **الـLead** قبل أي كتابة كود. أي تعديل على الواجهات المجمّدة هنا
> يمرّ من الـLead أولًا. الغرض: فيجن وراصد يشتغلوا على ملفات منفصلة بلا تصادم.

## 0) الهوية المستهدفة

| | القيمة |
|---|---|
| اسم النظام | **أفكاري** (Afkary) |
| الدلع | **فوفا** / «يا أفكار» |
| البوت | `@Afkary22Bot` (المالك الوحيد `561770354`) |
| العقدة الحالية | `WORKSHOP` — `G:\ai\Naggar Print POS Agent` |

## 1) أدلة حيّة اتجمعت قبل الكتابة (مش تخمين)

| # | الدليل | الرقم الحقيقي |
|---|---|---|
| E1 | `db.stats()` — 10 استعلامات متتالية على pooler سحابي | **6.5 ثانية** لكل تحميل لوحة |
| E2 | `ai_router.route("هاي")` كامل | **16.9 ثانية** |
| E3 | `captures` فيها «هاي» (id=4) كنوت، و«لا حطها فى ملف باسم فكرنى» (id=3) كتذكير | الباج مؤكّد — كل نص حر يتحفظ |
| E4 | `providers.chat(...)` بنداء مباشر | **ناجح** — 6.4ث، `DeepSeek-V4-Flash-0731`، رد JSON سليم |
| E5 | `settings.default_provider_id=1` و`default_model_id` مضبوطين | الافتراضي **مظبوط فعلًا** |
| E6 | اللوج: `السحابة غير متاحة — قواعد محلية فقط (ProviderError)` | **متقطّع** — مش دايم؛ السبب الحقيقي مجهول لحد ما يتشخّص |
| E7 | `db` مافيهاش أي دالة محادثة (`has_chat_history_fn == []`) | **مفيش ذاكرة محادثة** خالص |
| E8 | جدول `ai_config` فيه مفتاح **نصي غير مشفّر** | ثغرة أمنية — لازم تتشال |
| E9 | `route("فكرني بكرة الساعة 5 أسلم الطلب")` → task + due 2026-10-20 17:00 | الراوتر المحلي شغال صح للالتقاط |

## 2) نطاقات الكتابة — منفصلة تمامًا

### فيجن (تطبيق + واجهة + ذكاء)
```
Vision-Lab/projects/notebook-v2/nb/persona.py      (جديد)
Vision-Lab/projects/notebook-v2/nb/intent.py       (جديد)
Vision-Lab/projects/notebook-v2/nb/bot.py
Vision-Lab/projects/notebook-v2/nb/ai_router.py
Vision-Lab/projects/notebook-v2/nb/providers.py
Vision-Lab/projects/notebook-v2/nb/proactive.py
Vision-Lab/projects/notebook-v2/nb/web.py
Vision-Lab/projects/notebook-v2/nb/bridge.py       (جديد)
Vision-Lab/projects/notebook-v2/nb/templates/*
Vision-Lab/projects/notebook-v2/nb/static/*
Vision-Lab/projects/notebook-v2/scripts/start_node.py
Vision-Lab/projects/notebook-v2/scripts/dsh_bridge.py  (جديد)
```

### راصد (قاعدة + توفر + أداء + تحقق)
```
Vision-Lab/projects/notebook-v2/nb/db.py
Vision-Lab/projects/notebook-v2/nb/ha.py
Vision-Lab/projects/notebook-v2/nb/cache.py        (جديد)
Vision-Lab/projects/notebook-v2/nb/config.py
Vision-Lab/projects/notebook-v2/db/schema_pgvector.sql
Vision-Lab/projects/notebook-v2/db/migrate.py
Vision-Lab/projects/notebook-v2/scripts/health_sync.py
```

### الـLead فقط
```
Vision-Lab/projects/notebook-v2/ARCHITECTURE.md
Vision-Lab/projects/notebook-v2/README.md
Vision-Lab/projects/notebook-v2/.env.example
Vision-Lab/projects/notebook-v2/UPGRADE_CONTRACT.md
Vision-Lab/projects/notebook-v2/DEPLOY_LAPTOP.md     (جديد)
```

## 3) الواجهات المجمّدة — راصد بيبنيها، فيجن بيستهلكها

> **ممنوع** تغيير الأسماء أو شكل الإرجاع من غير موافقة الـLead.

### `nb/cache.py` (راصد)
```python
def get_or_set(key: str, ttl: int, producer: Callable[[], Any]) -> Any
def invalidate(prefix: str = "") -> int      # يرجع عدد المفاتيح اللي اتشالت
def stats() -> Dict[str, Any]
```

### `nb/db.py` — إضافات جديدة (راصد)
```python
def dashboard(ttl: int = 45) -> Dict[str, Any]
    # مفتاح واحد للوحة القيادة، TTL افتراضي 45ث
    # المفاتيح المضمونة: stats, captures, due, late, need_help,
    #                    projects, radar, events, ws_stats
def log_message(chat_id: int, role: str, content: str, meta: dict | None = None) -> int
def recent_messages(chat_id: int, limit: int = 12) -> List[Dict[str, Any]]
    # الأقدم الأول (newest last) — جاهزة للتحويل لـ messages[]
def count_messages(chat_id: int) -> int
```

### `nb/db.py` — دوال موجودة **مجمّدة** (نفس التوقيع ونفس المفاتيح)
```
stats() due_reminders() overdue_captures() list_captures(...)
add_capture(a)  set_capture_status(cid, status)  snooze_capture(cid, minutes)
get_setting(key, default)  set_setting(key, value)
q(...)  x(...)  scalar(...)  connect()  utcnow()  now_local_date()
```
> `stats()` لازم تفضل بنفس الـ 10 مفاتيح بالظبط — فيجن بيقراها في الويب.

### `nb/ha.py` — **مجمّدة بالكامل** (راصد يحسّن الداخل فقط)
```
heartbeat()  try_acquire_lease() -> bool  status() -> dict  release()
set_bot_state(key, value, bot)  get_bot_state(key, default, bot)
```
> مفاتيح `status()` المضمونة: `node_id, device_name, role, i_am_leader, leader, nodes, web_port`

### إعدادات جديدة في `settings` (راصد يزرعها مرة واحدة)
```
persona_name          = "أفكاري"
persona_nick          = "فوفا"
cache_ttl_seconds     = 45
chat_memory_limit     = 12
```

### جدول جديد `conversations` (راصد)
```
id BIGSERIAL PK, chat_id BIGINT, role TEXT, content TEXT,
meta JSONB DEFAULT '{}', created_at TIMESTAMPTZ DEFAULT now()
INDEX (chat_id, id DESC)
```

### جدول `outbox` — **مافيش تغيير سكيمة**
`kind` بيشيل نوع الرسالة، والبوت بيترجمها لكيبورد:
`plain | reminder | task | briefing | squad | pomodoro`
> كده الأزرار تتضاف من غير أي عمود جديد ولا تصادم.

## 4) الواجهات اللي فيجن بيبنيها

### `nb/intent.py` (جديد)
```python
def gate(text: str, chat_id: int, history: List[Dict] | None = None) -> Dict[str, Any]
    # {"intent": "chat"|"capture"|"command",
    #  "reply": str | None,        # للرد الحواري
    #  "analysis": dict | None,    # تحليل الالتقاط لو intent=capture
    #  "routed_by": str, "reason": str}
```
**قاعدة حاكمة:** الافتراضي = `chat`. الالتقاط **بس** لو فيه دليل صريح.
كلمات محادثة (`هاي`، `ازيك`، `صباح الخير`، `شكرا`، سؤال بعلامة استفهام،
جملة < 15 حرف بلا فعل طلب) → `chat` وممنوع تُحفظ.
كلمات التقاط (`فكرني`، `نوت`، `سجل`، `اعمل`، `اطلب`، `محتاج`، `ميعاد`،
`بكرة`، `النهاردة`، `حطها في ملف`) → `capture`.

### `nb/persona.py` (جديد)
```python
NAME = "أفكاري"
NICK = "فوفا"
def system_prompt(history: List[Dict] | None = None) -> str
def greeting() -> str
def reply(text, history) -> str       # رد حوار حر بنداء المزود
```

### `nb/bridge.py` + `scripts/dsh_bridge.py` (جديد)
CLI بيدخل/يخرج JSON (`--json`) — بيقرا ويكتب **نفس** جداول المنظومة:
```
python scripts/dsh_bridge.py add "فكرني بكرة الساعة 5" --json
python scripts/dsh_bridge.py chat "هاي" --json
python scripts/dsh_bridge.py list [--status open|all] [--kind task] [--limit 20] --json
python scripts/dsh_bridge.py today --json
python scripts/dsh_bridge.py done <id> | snooze <id> <min> | category <id> <cat> | delete <id>
python scripts/dsh_bridge.py search "ليزر" --json
python scripts/dsh_bridge.py stats --json
python scripts/dsh_bridge.py status --json
```
> ممنوع أي إرسال لتليجرام من الـbridge إلا بأمر صريح `send` + تأكيد.

### `nb/web.py` — إضافات
```
GET  /api/chat?text=...        # نفس بوابة النوايا — بلا تليجرام
POST /api/chat
GET  /api/dashboard            # كاش 45ث
POST /api/capture/<id>/action  # body: {action: done|snooze|category|delete, value: ...}
```

## 5) قواعد سلامة إلزامية

1. **العقدة شغّالة حيّة دلوقتي** (PID 19956، بورت 8110، البوت بيعمل polling).
   **ممنوع** تقتل العملية أو تعمل restart من غير موافقة الـLead.
   للاختبار: شغّل Flask على بورت تاني (`NB2_PORT=8111`) أو استورد الموديولات مباشرة.
2. **ممنوع** تبعت أي رسالة تليجرام لـمحمود أثناء التطوير — إلا بتصريح صريح.
3. **ممنوع** تكتب أو تطبع أي مفتاح/توكن في أي رد أو ملف أو لوج.
   (في `ai_config` مفتاح نصي — راصد يشيله بلا ما يطبعه).
4. قاعدة POS الخاصة بالمحل **قراءة فقط** — ممنوع أي كتابة.
5. أي `print` لعربي على كونسول ويندوز (cp1252) لازم يمر من
   `json.dumps(..., ensure_ascii=True)` — غير كده `UnicodeEncodeError`.
6. بايثون: `Vision-Lab\projects\notebook-v2\.venv\Scripts\python.exe`
   (فيه flask + psycopg2 + cryptography، **مفيش** requests/PIL/playwright).
7. السقوط للقواعد المحلية **مسموح فقط** لما كل المزودين السحابيين يفشلوا فعلًا،
   ولازم يتسجّل **سبب الفشل الحقيقي** (نوع + نص الاستثناء).

## 6) تسلسل التسليم

```
راصد: طبقة db/cache/سكيمة  ──┐
                              ├─► فيجن: بوت/نوايا/شخصية/ويب/bridge
                              │
                              └─► راصد: تحقق نهائي (باريتي + HA + أداء)
                                          └─► الـLead: دمج + قبول + تقرير
```

## 7) معايير القبول (الـLead بيقيسها بنفسه)

| # | المعيار | القياس |
|---|---|---|
| A1 | «هاي» متتحفظش | `count(captures)` ما يزيدش + رد حوار من فوفا |
| A2 | «فكرني بكرة الساعة 5 أسلم الطلب» تتحفظ | صف جديد kind=task + due صحيح |
| A3 | `db.stats()` | < 1.5ث (كانت 6.5ث) |
| A4 | تحميل اللوحة | < 1.0ث مع كاش |
| A5 | ذاكرة محادثة | «حطها في ملف فكرني» تُفهم كإحالة على الرسالة اللي قبلها |
| A6 | المزود | `routed_by` يبدأ بـ `llm:` للالتقاط، وسبب الفشل مسجّل لو فشل |
| A7 | أزرار تليجرام | كل تذكير معاه 5 أزرار inline + كيبورد سفلي ثابت |
| A8 | bridge | `dsh_bridge.py list --json` يرجّع **نفس** صفوف الويب والبوت |
| A9 | HA | الإيجار بيتجدّد كل 15ث، والسقوط ≤ 45ث، و`nodes` فيها العقدة alive |
| A10 | السكيمة | `migrate.py --check` نضيف + FK بتحرس المراجع المفقودة |
