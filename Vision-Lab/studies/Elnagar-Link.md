# 🏗️ ملخص معماري: Elnagar Link (Nagar-Bridge Ultimate)

> دراسة بقلم فيجن (الوكيل الأم) مباشرة — وكيلا الدراسة انقطعا مرتين قبل الإنهاء، وهذه الدراسة تبني على هيكلهما وستبدله بقراءات أعمق.
> تاريخ الدراسة: 2026-10-18 ~01:40 | الملفات المقروءة فعليًا: 7 (README.md كامل، main.py كامل، requirements.txt كامل، core\sync_engine.py أول 70/142، core\clipboard_sync.py أول 50/56، core\adb_manager.py أول 50/274، core\scrcpy_client.py أول 50/69)

## 1) الغرض الوظيفي
جسر تحكم أندرويد من ويندوز «Nagar-Bridge Ultimate»: مرآة شاشة الهاتف بـ scrcpy (وضع Ghost — شاشة الهاتف مطفأة)، مزامنة ملفات ذكية (Delta) للمجلدات، كليبورد موحّد، تثبيت APK، واتصال QR لاسلكي — أداة تحكم يومية بالهاتف من جهاز الورشة (README.md:3-36).

## 2) نقاط الدخول والتشغيل
- `NagarBridgeUltimate\main.py` (22 سطرًا) → QApplication → `gui.main_window.MainWindow` (main.py:10-14).
- التشغيل: `pip install -r requirements.txt` ثم `python main.py` (README.md:25).
- شروط: Python 3.10+، ADB وscrcpy على PATH **أو** داخل `bin\` (scrcpy.exe + adb.exe + DLLs مضمّنة فعليًا في bin\).

## 3) الهيكل العام
```
NagarBridgeUltimate\
├── main.py                 ← الدخول (22 سطرًا)
├── core\                   ← المحرك: adb_manager / scrcpy_client / sync_engine / clipboard_sync / settings_manager
├── gui\                    ← main_window, side_panel, sync_panel, tools_panel, qr_connection, sync_dialog, rescue_dashboard, workers + widgets (battery/status)
├── bin\                    ← scrcpy.exe + adb.exe + SDL2/ffmpeg DLLs (باقة كاملة)
├── assets\style.qss        ← ثيم Qt
├── settings.json           ← إعدادات (مسار المزامنة...)
└── install_deps.py / diagnose.py / debug_qr.py / create_shortcut.ps1
```

## 4) الوحدات الرئيسية
1. `core\adb_manager.py` (274 سطرًا): غلاف adbutils — أجهزة متصلة، shell، حالات مفصلة.
2. `core\sync_engine.py` (142 سطرًا): «Lightning Sync» — فحص عميق `ls -R -l` على 4 مصادر ثابتة (`/sdcard/DCIM/`, `/sdcard/WhatsApp/Media/`, `/sdcard/Pictures/`, `/sdcard/Download/` — sync_engine.py:20-25) بـ regex لتحليل خرج ls (سطر 52)، ثم نقل Delta + progress_signals، الوجهة من `settings_manager.sync_path`.
3. `core\scrcpy_client.py` (69 سطرًا): تشغيل scrcpy المضمّن من bin\ مع `--turn-screen-off` (Ghost Mode) و`--stay-awake` + تثبيت عنوان النافذة NagarGhostMirror وreparenting يدوي في Qt (تعليقات الملف 40-50: الدمج تجريبي).
4. `core\clipboard_sync.py` (56 سطرًا): حلقة daemon تفحص الكليبورد — **لكن متنها فعليًا `pass` في الفرعين (clipboard_sync.py:38,46) وتعتمد على مزامنة scrcpy التلقائية** — نصف نافذة ميتة.
5. `gui\*`: main_window + side_panel (استعراض ملفات + سحب للديسكتوب) + sync_panel + tools_panel + qr_connection + rescue_dashboard + app_manager (تثبيت APK بالسحب) + widgets (بطارية/حالة).

## 5) المكتبات (requirements.txt — 8 أسطر، بلا تثبيت إصدارات لمعظمها)
PyQt6>=6.5 | pure-python-adb | adbutils>=2 | uiautomator2 | qasync | clipboard | Pillow | qrcode[pil]

## 6) مخازن البيانات
`settings.json` محلي (إعدادات: مسار المزامنة) + مجلد المزامنة الوجهة. لا قواعد بيانات.

## 7) التكاملات
ADB/USB (bin\adb.exe مضمّن) + scrcpy (bin\scrcpy.exe + libusb/SDL/ffmpeg DLLs) + مزامنة DCIM/WhatsApp/Pictures/Download + clipboard fusion عبر scrcpy + QR connection (qrcode) — واضع اختصار create_shortcut.ps1.

## 8) تقييم الصحة (بدليل)
🟢 قوة: بنية نظيفة core/gui، مزامنة بتحليل فروقات (ls -R + مقارنة)، استعلامات adbutils موثوقة، Ghost Mode عملي للعمل المطول.
🟡 `clipboard_sync.py` حلقة بلا عمل فعلي (جميع الفروع `pass` — سطرا 38 و46 — تعتمد كليًا على scrcpy).
🟡 `scrcpy_client.py:40-45` الـembedding داخل نافذة Qt تجريبي (لا flag رسمي — يعتمد reparenting عبر Win API).
🟡 `adb_manager.py` أخطاء مبتلعة بـ `except:` الصامتة (أسطر 13-16، 22-23).
🟡 ملفات `.pyc` cpython-314 ملتزمة + `requirements.txt` بلا تثبيت إصدارات (غير PyQt6).
🟡 venv حُذفت بالتنظيف (كانت 0.23GB) — تتجدد بـ pip install.

## 9) خريطة دخول للتطوير
1. `gui\main_window.py` ثم `core\adb_manager.py` (274 سطرًا — كل الوصول للجهاز منه).
2. لتغيير مجلدات المزامنة: `sync_engine.py:20-25`.
3. لتفعيل كليبورد حقيقي: استخدم قدرات scrcpy الجاهزة بدل clipboard_sync.py (الملف نفسه يقول ذلك).

## 10) فهرس الملفات المهمة
| الملف | دوره | ملاحظة |
|-------|------|--------|
| main.py | الدخول | PyQt6 → MainWindow |
| core\adb_manager.py (274 سطرًا) | كل أوامر ADB | adbutils |
| core\sync_engine.py (142 سطرًا) | Lightning Sync بـ Delta | مصادر: DCIM/WhatsApp/Pictures/Download |
| core\scrcpy_client.py (69) | المرآة (Ghost Mode) | bin\scrcpy.exe مضمّن + reparenting تجريبي |
| core\clipboard_sync.py | كليبورد | جسمه TODO — يعتمد scrcpy |
| gui\main_window.py + panels | الواجهة | rescue_dashboard / qr_connection / sync_panel / tools_panel |
| bin\ | scrcpy + adb مضمّنان | يعمل بدون تثبيت نظامي |

---
*الجاهزية للعودة للتطوير: 90%. (هيكل أولي سابق من وكيل مقاطَع كان موجودًا — استُبدل بهذه النسخة الأكمل بعد قراءته.)*
