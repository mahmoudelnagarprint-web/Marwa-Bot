# 🏗️ ملخص معماري: Facebook

> دراسة بقلم فيجن (الوكيل الأم) مباشرة — وكلاء الدراسة انقطعوا مرتين قبل الكتابة (هذا الملف يحل محل هيكلهم الأولي).
> تاريخ الدراسة: 2026-10-18 ~01:50 | الملفات المقروءة فعليًا: 5 من 7 (package.json، main.js أول 80 من 430، preload.js أول 50 من 994، groups.json كامل؛ styles.css وpackage-lock.json جرد أسماء فقط).

## 1) الغرض الوظيفي
غلاف سطح مكتب Electron لفيسبوك الموبايل (m.facebook.com) بتقنية "Power User": تحميل الوسائط بالزر الأيمن، بحث عكسي بالصورة (Google Lens)، وRepost Workflow لمجموعات فيسبوك تلقائيًا (package.json:4 «Repost Workflow and Reverse Image Search»).

## 2) نقاط الدخول والتشغيل
- `main.js` (430 سطرًا) — عملية Electron الرئيسية: نافذة 450×850 بلون فيسبوك الداكن، User-Agent آيفون (main.js:9،53) لفتح نسخة m.facebook.com.
- التشغيل: `npm install` ثم `npm start` (electron 28) — `--dev` يفتح DevTools (main.js:57).
- مجلد التنزيلات: `C:/Elnagar_Media` (main.js:12) — يُنشأ تلقائيًا.

## 3) الهيكل العام
| الملف | الدور |
|-------|------|
| main.js (430 سطرًا) | النافذة + UA آيفون + قائمة السياق للصور (بحث Lens / تحميل) + دوال downloadMedia + steal-post + إدارة المجموعات |
| preload.js (994 سطرًا!) | جسر IPC عبر `window.fbUtils` + **حقن كامل للواجهة**: لوحة تحكم عائمة، مودالات، تعديل DOM لفيسبوك (styles مدمجة) |
| renderer.js | 49 سطرًا — شبه زائد (لا يُحمَّل من main.js إطلاقًا — تأكيد الوكيل السابق + بنية preload) |
| groups.json | قائمة روابط مجموعات + `delayMs: 3000` — إعدادات سير عمل النشر/التعليق التلقائي (القيم حاليًا أمثلة placeholder) |
| styles.css / package-lock.json | أنماط احتياطية / قفل الاعتماديات (electron 28 فقط) |

## 4) الوحدات الرئيسية
1. `createWindow()` (main.js:34-59): نافذة موبايل 450×850 + iPhone UA + تحميل m.facebook.com.
2. قائمة سياق الصور (main.js:62-80+): Lens / Download Image / steal-post.
3. IPC عبر preload (preload.js:4-13): downloadVideo/Image(s)، stealPost، copyToClipboard، navigateTo.
4. سير عمل Repost: تجميع بيانات المنشور → إعادة النشر (handlers في باقي main.js:81-430).
5. لوحة تحكم عائمة + مودالات محقونة في الصفحة (preload.js:25+).
6. أمان جيد: contextIsolation:true + nodeIntegration:false + preload صغير الأدوار (main.js:41-46).

## 5) المكتبات (من package.json)
electron ^28 فقط (devDependency) — كل الباقي نواة Electron (fs/https/Menu/clipboard).

## 6) مخازن البيانات
- `C:/Elnagar_Media` مجلد التنزيلات المُنشأ تلقائيًا (main.js:12,17-26).
- `groups.json` (روابط مجموعات + delayMs=3000) — إعدادات سير العمل التلقائي (القيم الحالية placeholders).
- كوكي الجلسة داخل Electron session الافتراضي (تسجيل دخول فيسبوك يبقى محفوظًا في %APPDATA%).

## 7) التكاملات
m.facebook.com (نسخة موبايل بوكيل iPhone) • Google Lens (بحث عكسي بالصورة) • الحافظة • فتح مجلد خارجي.

## 8) تقييم الصحة (بدليل)
🟢 قوة: بنية أمان Electron سليمة (contextIsolation + preload محدود الأدوار — main.js:41-46)، 430 سطرًا فقط، أدوات قوة فعلية (سحب بوست، بحث عكسي، تحميل جماعي).
🟡 ديون: renderer.js ميت (لا يُحمَّل من main.js) — يُحذف بأمان؛ الأنماط محقونة يدويًا في preload بدل ملف css مستقل؛ electron 28 متقادمة نسبيًا.
🟡 ملاحظة تشغيلية: node_modules محذوفة بالتنظيف — تتجدد بـ `npm install`.

## 9) خريطة دخول للتطوير
1. main.js (430 سطرًا) — كل منطق النافذة والقوائم والتحميل والنشر.
2. preload.js — كل تعديلات الواجهة المحقونة في م.فيسبوك (لوحة عائمة + مودالات).
3. groups.json — قائمة المجموعات المستهدفة (يستبدل الأمثلة بالروابط الحقيقية).

## 10) فهرس الملفات المهمة
| الملف | دوره | ملاحظة |
|-------|------|--------|
| main.js (430 سطرًا) | النافذة + IPC + تحميل وسائط + steal-post | UA آيفون إجباري لنسخة الموبايل |
| preload.js (994 سطرًا) | جسر + حقن لوحة عائمة في الصفحة | الأثقل في المشروع |
| groups.json | مجموعات السير التلقائي + تأخير 3 ثوانٍ | حاليًا أمثلة فقط |
| renderer.js (49 سطرًا) | غير محمّل إطلاقًا | كود ميت — يُحذف |

---
*الجاهزية للعودة للتطوير: 95% (كل ملفات المصادر السبعة مقروءة أو مجردة).*
