# SASA Workshop State — مصطفى (صاصا) | ذاكرة الورشة الحية
> WORKSHOP_PC (NODE_ID: WORKSHOP) — آخر تحديث: 2026-10-17 08:58 — **RPA Phase 1 منفذة ومُتحقق منها لايف** ✅

## 1) الجهاز المضيف (Host)
- مجلد العمل: `G:\ai\Naggar Print POS Agent` | نظام: Windows | IP ثابت: `192.168.1.50` / GW `192.168.1.1`
- بايثون: **3.11.9** (الافتراضي: `C:\Users\mahmo\AppData\Local\Programs\Python\Python311`) + 3.13 ثانوي. **لا يوجد .venv للـ POS** → أدوات الأتمتة تُثبَّت على 3.11.

## 2) مسارات البرامج المؤكدة (مزروعة في system_apps.json)
| البرنامج | الإصدار | المسار | ملاحظة |
|---|---|---|---|
| RDWorks | **8.00.32** | `C:\RDWorksV8\RDWorksV8.exe` | الـ Registry بيقول InstallLocation: `C:\newpr` (مجلد المثبِّت) — عنوان النافذة: `«V8.00.32-[اسم الملف]»` **بدون كلمة RDWorks** |
| Photoshop | 2021 | `C:\Program Files\Adobe\Adobe Photoshop 2021\Photoshop.exe` | كان شغالاً أثناء الفحص |
| CorelDRAW | 2024 | `C:\Program Files\Corel\CorelDRAW Graphics Suite\25\Programs64\CorelDRW.exe` | فيه كمان CorelPP.exe |
| Epson L3250 | — | منفذ USB003 | USB = OK |
| Epson L1800 | — | منفذ USB001 | USB = OK |
| PrintFab (افتراضية) | — | منفذ ZEDONUL | XP3100 + L1800 عبر PrintFab |

> نتيجة مباشرة: أمر «افتح rdworks / فوتوشوب» في `system_worker.py` هيشتغل من دلوقتي بدون طلب المسار من المالك.

## 3) اتصال ماكينة الليزر — **الحكم النهائي (Phase 1)**
| الفحص | النتيجة |
|---|---|
| `ping 192.168.1.100` | ❌ **ميت تماماً** — 4/4 packets lost (100% loss) ولا يظهر في ARP أصلاً |
| `192.168.1.2` (الجهاز الوحيد الحي الآخر) | ✅ حي — لكن يعرض **صفحة login على TCP/80 فقط** (باقي المنافذ مغلقة) → سلوك راوتر/أكسس بوينت، **مش ماكينة ليزر** |
| **Prolific USB-to-Serial (COM3)** | ✅ **Status: OK** — متصل الآن |
| `FTD2XX.dll` داخل `C:\RDWorksV8` | موجودة — RDWorks بيوتّصل للماكينة عبر USB/Serial |

**الاستنتاج الهندسي:** الماكينة متصلة **USB/Serial عبر COM3** (وليست Ethernet على .100). التأكيد النهائي يحتاج Phase 2: قراءة شريط حالة RDWorks بالـ OCR لعرض اسم البوردة (مثل RDCxxxx) وحالة Connected.

## 4) حزمة الأتمتة المثبتة (Python 3.11.9 — 2026-10-17)
`pywinauto 0.6.9` | `pyautogui 0.9.54` | `mouseinfo 0.1.3` | + تبعيات: comtypes, pygetwindow, pyscreeze, pymsgbox, pyperclip, pyrect, pytweening — **IMPORTS OK تم التحقق**

## 5) النموذج الأولي — `pos_system/automation/rdworks_auto.py`
أوضاع التشغيل: `check` | `launch` | `status` (+ `--wait N`)
- اكتشاف المسار: `system_apps.json` ← مسارات مرشحة معروفة ← فحص اختصارات PowerShell — **بصدق، لا مسارات مخترعة**
- كشف النافذة: regex `(rdworks | ^v\d+\.\d+\.\d+-\[)` — **الدرس المكتسب:** العنوان الحقيقي `«V8.00.32-[Blank]»` لا يحتوي كلمة RDWorks
- سلوك آمن: لا يفتح نسخة ثانية إذا كان البرنامج مفتوحاً
- أكواد الخروج: 0 نجاح | 1 المسار غير موجود | 2 فشل الفتح | 3 مهلة النافذة | 4 مكتبات ناقصة
- **الاختبار الحي (08:46→08:57):** فتح بارد حقيقي ناجح → مهلة أولى (bug في المطابقة) → تشخيص بالأدلة (PID 17952 + MainWindowTitle) → إصلاح → **3/3 اختبارات خضراء**. RDWorks متروك مفتوحاً على شاشة الورشة عمداً.

## 6) خريطة شبكة الورشة (2026-10-17)
| IP | الهوية | MAC |
|---|---|---|
| 192.168.1.1 | Gateway/الراوتر الرئيسي | d4-6b-a6-eb-f5-60 |
| 192.168.1.2 | جهاز مجهول بصفحة login (راجتر/AP ثانٍ غالباً) | 0c-80-63-6c-0f-82 |
| 192.168.1.50 | **WORKSHOP_PC** (هذا الجهاز) | — |
| 192.168.1.100 | **لا يوجد جهاز** | — |

## 7) المتبقي — Phase 2 (في انتظار أمر المالك)
1. استيراد ملف `.rd`/`.dxf` إلى RDWorks آلياً (File → Import عبر pywinauto)
2. الضغط على Download/Start — **بأمر صريح فقط** (سلامة الماكينة أولاً)
3. قراءة حالة الماكينة من شريط RDWorks عبر OCR (تأكيد «Connected» + اسم البوردة)
4. الربط الكامل: قائمة إنتاج POS → بطاقة شغل manufacturing_agent → ملف → RDWorks → Start
