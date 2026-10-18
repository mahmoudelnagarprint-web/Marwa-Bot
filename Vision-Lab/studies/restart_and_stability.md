# إعادة تشغيل النظام الحي — تقرير التشغيل والاستقرار

**التاريخ:** 2026-10-18 ~01:52–01:59 (Africa/Cairo)
**نفّذه:** الـ lead (كانت المهمة لفيجن لكن الوكيل توقف قبل التنفيذ — نُفّذ يدويًا بالصلاحية الممنوحة من المالك)
**قرار المالك:** صلاحية كاملة لإعادة تشغيل `G:\ai\Elnagar POS` والتحقق من عودة البورتات وقراءة 1040.

---

## 1) الحالة قبل التشغيل (بازلاين مقيّس)

| البورت | قبل | ملاحظة |
|---|---|---|
| 7777 (Backend API) | ✖ غير مستمع | العملية القديمة PID 3788 ماتت عند 00:48:19 بلا traceback |
| 8888 (واجهة Eel) | ✖ غير مستمع | |
| 7788 (Mobile API) | ✔ مستمع (PID 15848) | **كود قديم** قبل إصلاح الإشارة (مهم جدًا لِما بعده) |
| 8100 (Notebook) | ✔ مستمع (PID 7916) | خدمات خارج نطاق مديرخدمات Elnagar — لم تُمَسّ |

ملفّات pid: `backend.pid=7700` (ميت/قديم)، `local_mobile_api.pid=15848` (حيّ)، `telegram_bot.pid=14488` (حيّ)، `firebase_importer.pid=392` (حيّ).

**سبب فشل الأمر الصريح الأول:** `start_elnagar_all_silent.vbs` يشغّل `py -3.11 elnagar_service_manager.py start`، وأمر `start` **يتخطّى** أي خدمة تعمل بالفعل (`start_service` يرجع فورًا إذا `get_pid` موجود). ولم يظهر أي سطر في `service_manager.log` بتاريخ 18/10 من تشغيل الـ vbs — أي أن الـ vbs لم يصل فعلًا للمدير. **الحل:** تشغيل `elnagar_service_manager.py restart` مباشرة بالقارئ الأساسي (venv pythonw)، لأن `restart` = `stop_all` ثم `start_all` فيرفع الخدمات الميتة ويعيد تشغيل الحيّة بالكود الجديد مرة واحدة.

## 2) ماذا شُغّل بالضبط

```
G:\ai\Elnagar POS\.venv\Scripts\pythonw.exe elnagar_service_manager.py restart
```

سُجّل في `runtime_logs\service_manager.log`: `[2026-10-18 01:55:20] Action: restart`.
نطاق `restart` محصور في مديرخدمات Elnagar الأربعة فقط: `backend` · `telegram_bot` · `local_mobile_api` · `firebase_importer` (لا يمسّ notebook/8100 أو غيره).

## 3) الحالة بعد التشغيل (فورًا + بعد 30 ثانية)

| البورت | بعد | PID المستمع |
|---|---|---|
| 7777 | ✔ مستمع | 10656 |
| 8888 | ✔ مستمع | 10656 (نفس عملية backend.py: Flask+Eel معًا) |
| 7788 | ✔ مستمع | 13736 (local_mobile_api **بكود الإصلاح الجديد**) |

ملفّات pid الجديدة كلها حيّة: `backend.pid=3484`, `local_mobile_api.pid=12540`, `telegram_bot.pid=14156`, `firebase_importer.pid=1932` — والفرق عن أرقام المستمعين هو عملية أب (Popen) تلد عملية المستمع، وهي طبيعية.

**استقرار:** أُعيد فحص البورتات بعد ~30 ثانية ثم بعد ~دقيقتين ⇒ لا سقوط. التشغيل الجديد في `backend.log` سطر سليم:

```
* Running on http://127.0.0.1:7777
Starting Elnagar POS in Independent Window...
Chrome not found, trying Edge...
Edge launch failed or not supported (fallback to default)...
GET /index.html 200
```

**لا `WinError 10048` ولا traceback جديد في التشغيل الحالي** — كل الـ Traceback الثلاثين في الملف عند أسطر ≤ 3121 (قديمة، قبل جلسة اليوم)، بينما سطور التشغيل الجديد عند ~7560+.

## 4) استجابة الـ API الحرفية

`GET http://127.0.0.1:7777/api/dashboard-summary` (01:56:20 ثم 01:58:52 للتأكيد):

```json
{"dashboard_summary":{
  "clients_count":56, "orders_total":58, "products_count":105,
  "debt_clients_count":4, "total_receivables":1040.0,
  "under_preparation_count":6, "under_preparation_value":2115.0,
  "delivered_count":52, "delivered_value":15718.5,
  "orders_today":0, "daily_revenue":0, "weekly_revenue":1505.0},
 "success":true}
```

⇒ **1040.0 جنيه / 4 عملاء** مطابقة، والنظام مستقر.

## 5) أثر إصلاح الإشارة على مسار الموبايل (الدليل الأهم)

`GET http://127.0.0.1:7788/api/dashboard-summary` ⇒ `debt_clients_count=4`, `total_receivables=1040`, `clients_count=56`.
`GET http://127.0.0.1:7788/api/clients` ⇒ 4 عملاء بـ `balance > 0` مجموعها **1040**:

| id | الرصيد |
|---|---|
| 107 | 350 |
| 108 | 250 |
| 109 | 200 |
| 63 | 240 |

قبل الإصلاح (شرط `balance < 0`) كان هذا المسار يُرجع **صفر** مدينين. الآن يطابق `app.py:1655/1712` الرسمي.

## 6) ملاحظات صريحة

- نافذة Eel حاولت Edge ثم `fallback` — هذا سلوك التطبيق نفسه، لم يؤثر على الخدمة (الواجهة تُخدم على 8888 والاستعلامات تعمل).
- `orders_today=0` لأن آخر حركة في القاعدة **16/10** (لا حركة 17/10–18/10) — راجع تقرير التحقق.
- **لم يُعدَّل أي كود أو أي `.db` في هذا التقرير** — تنفيذ فقط.

## 7) اكتشاف مهم أثناء المراقبة — توقّف Backend متكرّر وصامت

**ما حدث (بالدليل):** بعد `restart` الساعة 01:55، ظلّ الـ backend يخدم (آخر طلب ناجح 01:58:52) ثم **توقّف صامتًا** في ~02:02–02:03 — بدون traceback وبدون سطر إغلاق، ونفس البصمة تمامًا لتوقّف 00:48:19 الأصلي. بقيت الخدمات الأخرى حيّة (mobile 7788، telegram، firebase). أعدتُ تشغيل الـ backend وحده عبر `elnagar_service_manager.py start` عند **02:09:40**، ومنذ ذلك الحين مستقر:

| البورت | الحالة الأخيرة (02:15) |
|---|---|
| 7777 + 8888 | مستمعان، PID 9260 (يشغّله الـ backend.pid=11720) |
| 7788 | مستمع، PID 13736 |

**السبب الجذري المرجّح (بدرجة عالية):** الـ backend هو **عملية واحدة** تشغّل Flask (7777) **وواجهة Eel (8888) معًا**، وبدء Eel يفتح «نافذة مستقلة» بمتصفح — سجلّ التشغيل يقول: `Chrome not found, trying Edge... Edge launch failed... falling back to default`. في طريقة تشغيل Eel، **إغلاق نافذة المتصفح يُنهي عملية Python** (توقف صامت بلا أخطاء). هذا يفسّر: التوقّف الأصلي 00:48، وتوقّف 02:03، ولماذا ينجو 7788 (FastAPI مستقل عن Eel).

**لم نُغيّر العلة** (سلوك Eel في `backend.py`/`app.py` هو كود واجهة — يتطلب قرار المالك). **توصية الإصلاح الجذري (بموافقتك فقط):** ضبط استدعاء `eel.start(...)` — مثل `close_callback` لا يوقف العملية، أو تشغيل بـ `mode=...`/`block=False`، أو ضبط `'mode': 'chrome'` بمسار متصفح ثابت — عشان الـ backend ما يقعش عند غلق النافذة. البديل العملي الأقل تدخّلًا: watchdog يشغّل `start` تلقائيًا إذا مات 7777.

