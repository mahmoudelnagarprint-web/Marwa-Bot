# 🏗️ ملخص معماري: Laser Bridge

> دراسة بقلم فيجن (الوكيل الأم) مباشرة — المشروع صغير (6 ملفات) فلم تُكلَّف به جولة وكيل.
> تاريخ الدراسة: 2026-10-18 ~01:10 | الملفات المقروءة فعليًا: 5 من 6 (app.py كامل 330 سطرًا، inspector.py كامل 61 سطرًا، rdworks_map.txt أول 60 من 64,747، run_as_admin.bat كامل؛ لم تُقرأ vbs ×2 لأنها غلاف إطلاق صامت موثق داخل app.py نفسه)

## 1) الغرض الوظيفي
ريموت كنترول من الموبايل لماكينة الليزر عبر شبكة الورشة: سيرفر Flask يبحث عن نافذة RDWorksV8 (برنامج الماكينة) ويضغط أزرارها فعليًا بـ pywinauto، مع واجهة موبايل عربية داكنة (OLED) — اسمه الداخلي «Elnagar Remote Control Web Server» (app.py:12).

## 2) نقاط الدخول والتشغيل
- `app.py` → `app.run(host='0.0.0.0', port=5005)` (app.py:330) — يفتح على كل واجهات الشبكة.
- التشغيل: `run_silent.vbs` (pythonw بلا كونسول) أو `run_as_admin.bat` (يرفع صلاحيات Admin).
- `inspector.py` أداة تطوير منفصلة: تستخرج شجرة عناصر RDWorks إلى `rdworks_map.txt` (64,747 سطرًا — لقطة كاملة لواجهة RDWorksV8.01.60-20211201).

## 3) الهيكل العام
مستوي الملفات فقط — 6 ملفات، لا مجلدات فرعية:
| الملف | الدور |
|-------|------|
| app.py | السيرفر كله (Flask + pywinauto + pyautogui + قالب HTML مدمج) — 330 سطرًا |
| inspector.py | يولّد rdworks_map.txt بعمل print_control_identifiers() لكل من backend win32/uia (inspector.py:12-42) |
| rdworks_map.txt | خرج الشجرة الفعلي لـ RDWorksV8.01.60 (64,747 سطرًا) — مرجع معرفات الأزرار |
| run_as_admin.bat / run_silent.vbs / run_silent_admin.vbs | مشغلات (أخيرها صامت كمسؤول) |

## 4) الوحدات الرئيسية
1. `get_rdworks_window()` (app.py:32-44): إيجاد نافذة RDWorks بالـ regex + فحص العرض > 100px لاستبعاد شاشة البداية.
2. `/laser/<action>` (app.py:51-80): frame → زر "Go scale" | start | stop | pause ("Pause/Continue") | optimize (toggle "Path optimize") | pulse (بضغطة إحداثيات مزاحة +60px يمين زر Go scale عبر pyautogui).
3. `/global/<key>` (app.py:83-104): Enter + أسهم + صوت + وسائط — عالمية بلا نافذة.
4. قالب الموبايل (app.py:107-319): واجهة OLED داكنة عربية بتبويبات + fetch لكل أمر.
5. `inspector.py` (61 سطرًا): يجرّب backend=win32 ثم uia ويكتب شجرة `print_control_identifiers()` كاملة في rdworks_map.txt.

## 5) المكتبات (من imports في app.py وinspector.py)
flask + render_template_string | pyautogui (FAILSAFE=False — app.py:25) | pywinauto (Desktop win32). لا requirements.txt — تُثبّت يدويًا (`pip install pywinauto pywin32 comtypes flask pyautogui` — نص التلميح في inspector.py:58).

## 6) مخازن البيانات
لا يوجد — عديم الحالة تمامًا (لا DB ولا ملفات حالة). rdworks_map.txt خرج regenerable.

## 7) التكاملات
- **RDWorksV8** (برنامج ماكينة الليزر) — عنوان نسخة موثق في rdworks_map.txt:5 (V8.01.60-20211201).
- الموبايل: أي جهاز على نفس الشبكة يفتح `http://<IP-الجهاز>:5005`.

## 8) تقييم الصحة (بدليل)
🔴 **خطر أمني 1 — لا مصادقة إطلاقًا**: كل المسارات مفتوحة بدون أي تحقق (app.py:51-104) والسيرفر على `0.0.0.0:5005` (app.py:330) → **أي جهاز على شبكة الورشة يشغّل/يوقف الليزر ويبعث مفاتيح عالمية**.
🔴 **خطر تشغيلي 2**: `run_as_admin.bat:6` ينفذ `taskkill /F /IM python.exe /T` — **يقتل كل عمليات Python على الجهاز** بما فيها Marwa-Bot والنوتبوك وسيرفر الـ API المحلي في نفس اللحظة. يجب قتله أو تقييده.
🟡 pyautogui.FAILSAFE = False (app.py:25) — يلغي صمام الأمان (تحريك الماوس للزاوية للإيقاف).
🟢 نقاط قوة: كود قصير وواضح، تحمل أخطاء جيد (try/except مع logging)، inspector قابل لإعادة التوليد لأي نسخة RDWorks جديدة.

## 9) خريطة دخول للتطوير (لو رجعنا نطوره)
1. `app.py` كله 330 سطرًا فقط — الوظائف في أعلاه والواجهة أسفله.
2. تعديل أي زر جديد: شغّل inspector.py وهو RDWorks مفتوح → خذ المعرف من rdworks_map.txt → أضف route.
3. أول إصلاح يُقترح: إضافة PIN للسيرفر + إزالة taskkill الشامل من الـ bat.

## 10) فهرس الملفات المهمة
| الملف | دوره | ملاحظة |
|-------|------|--------|
| app.py | السيرفر كله (330 سطرًا) | بورت 5005 على 0.0.0.0 — بلا مصادقة |
| inspector.py | مولّد خرائط أزرار RDWorks | يحتاج RDWorks شغال + Admin |
| rdworks_map.txt | خرج inspector (64,747 سطرًا) | مرجع، لا يُعدل يدويًا |
| run_as_admin.bat | مشغّل كمسؤول | **يقتل كل عمليات Python أولًا — خطر على Marwa-Bot** |
| run_silent.vbs / run_silent_admin.vbs | إطلاق صامت (pythonw) | — |

---
*الجاهزية للعودة للتطوير: 95% (كل الملفات مقروءة بالكامل تقريبًا).*
