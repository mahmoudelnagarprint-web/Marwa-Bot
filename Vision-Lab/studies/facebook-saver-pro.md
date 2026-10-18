# 🏗️ ملخص معماري: facebook-saver-pro

> دراسة معمارية مبنية على القراءة الفعلية لكل ملفات المشروع (3 ملفات — قراءة كاملة).
> قاعدة الدراسة: قراءة فقط، الاستنتاج من المحتوى المقروء. لا توجد أي توكنات أو مفاتيح في الكود ولا تُطبع.

## 1) الغرض

إضافة كروم (Chrome Extension — **Manifest V3**) باسم **"Facebook Image Saver Pro"** إصدار **3.0**، ووصفها في الـ manifest: «حفظ ونسخ صور فيسبوك بأقوى طريقة ممكنة».

الوظيفة الفعلية كما يظهر من الكود:
- **كشف الصور** في صفحات فيسبوك المفتوحة تلقائيًا (بمعدد selectors + MutationObserver + مسح دوري).
- **حقن زرّين عائمان فوق كل صورة كبيرة** عند مرور المؤشر: 💾 تحميل، 📋 نسخ للحافظة.
- **التحميل** عبر الـ background service worker إلى مجلد `FacebookSaverPro/` داخل مجلد التنزيلات، بأسماء فريدة `fb_image_<timestamp>.<ext>`.
- **النسخ للحافظة** بثلاث استراتيجيات متتالية (fetch مباشر ← fetch عبر بروكسي ← canvas).
- **محاولة «رفع الجودة»**: اختيار آخر مصدر من `srcset` وتنظيف معاملات الحجم من روابط fbcdn/scontent.

## 2) نقاط الدخول (Entry Points)

| نقطة الدخول | النوع | التفاصيل |
|---|---|---|
| `facebook-saver.js` | Content Script | يُحقن في `facebook.com` (بكل نطاقاته) **وفي `<all_urls>`**، عند `document_start`، في كل الفريمات (`all_frames: true`) |
| `background-pro.js` | Service Worker (خلفية MV3) | يستقبل رسالة `facebook_download` من سكربت المحتوى وينفّذ `chrome.downloads.download` |
| — | Popup / Options / Action | **غير موجودة**: لا صفحة منبثقة ولا خيارات ولا زر شريط؛ التفاعل كله من داخل صفحة فيسبوك مباشرة |

يُحمَّل من مجلد غير مضغوط عبر `chrome://extensions` (وضع المطوّر) — لا حزمة CRX ولا متجر.

## 3) الهيكل العام (Structure)

```
G:\ai\facebook-saver-pro\            ← مجلد الجذر
└── facebook-saver-pro\              ← مجلد الإضافة نفسه (متداخل بنفس الاسم)
   ├── manifest.json                 (49 سطرًا)  تعريف MV3
   ├── facebook-saver.js             (676 سطرًا) سكربت المحتوى — كل منطق الواجهة
   └── background-pro.js             (160 سطرًا) Service Worker — التحميل والإشعارات
```

- **بنية مسطحة تمامًا**: لا مجلدات فرعية، لا أيقونات، لا `_locales`، لا اختبارات.
- **معمارية من طبقتين** يتواصلان بـ Message Passing:
  1. **طبقة العرض والالتقاط** (Content Script): كشف الصور → أزرار → إشعارات داخل الصفحة.
  2. **طبقة التنفيذ** (Service Worker): تحميل الملفات + إشعارات نظام + مراقبة اكتمال التحميلات.
- جسر الاتصال: `chrome.runtime.sendMessage` (من المحتوى) ↔ `chrome.runtime.onMessage` (في الخلفية).

## 4) الوحدات والطبقات (Modules/Layers)

كل منطق المحتوى داخل **IIFE واحدة** في `facebook-saver.js`:

| الوحدة/الدالة | الدور |
|---|---|
| `injectPowerfulStyles()` | حقن `<style>` واحد بكل CSS: أزرار (45px، زجاجية)، إشعارات منزلقة، مؤشر «Active»، تحسينات موبايل |
| `showActiveIndicator()` | «توست» يظهر عند التحميل ثم يختفي بعد 3 ثوانٍ |
| `findFacebookImages()` | بحث بـ 11 selector متدرّجًا (`scontent`، `fbcdn`، `data-src`، `[role="img"]`، `data-testid`… وحتى `img` كخيار أخير) — الدمج في `Set` |
| `isValidFacebookImage()` | فلترة: لا أصغر من 80×80، تجاهل `data:`/`blob:`/`chrome-extension:`، تجاهل الأفاتارات الصغيرة (<120px مع alt يحوي profile/avatar) |
| `addButtonsToFacebookImage()` | يلفّ الصورة في `div.fb-saver-container` + overlay + زرّان (تحميل/نسخ) مع منع فقاعة الأحداث |
| `downloadFacebookImage()` | يبني الاسم، يستدعي `getHighestQualityUrl`، يرسل `facebook_download` للخلفية ويعرض النتيجة |
| `copyFacebookImage()` + `copyImageWithMultipleStrategies()` | تجربة 3 استراتيجيات نسخ بالترتيب حتى ينجح الأولى |
| `copyWithFetch()` / `copyWithProxyFetch()` / `copyWithCanvas()` | الاستراتيجيات الثلاث (الوسطى عبر `cors-anywhere.herokuapp.com`) |
| `getHighestQualityUrl()` | آخر عنصر من `srcset` + 5 أنماط regex لتنظيف معاملات الحجم من روابط فيسبوك |
| `generateUniqueFilename()` | `fb_image_YYYY_MM_DD_HH_mm_ss_mmm.<ext>` مع استخراج الامتداد من المسار |
| `showPowerfulNotification()` | إشعارات داخل الصفحة (تُزال بعد 5 ثوانٍ، واحد فقط في اللحظة) |
| `processFacebookImages()` + `startPowerfulObserver()` | معالجة أولية بعد 2 ثانية، MutationObserver بتأخير 500ms، ومسح دوري كل 5 ثوانٍ |
| `initFacebookSaverPro()` | التهيئة: ستايلات ← مؤشر ← معالجة ← مراقبة ← مؤقّت دوري |

في `background-pro.js`:

| الوحدة | الدور |
|---|---|
| `onMessage` handler | يستقبل `facebook_download` فقط، ويعيد `true` للاستجابة غير المتزامنة (صحيح) |
| `handleFacebookDownload()` | تحميل إلى `FacebookSaverPro/<domain>/<filename>` مع `uniquify`، ومحاولة احتياطية بدون مجلد عند الفشل |
| `createSuccessIcon()` | أيقونة 48×48 مرسومة على `OffscreenCanvas` (تعيد Promise — انظر الملاحظات) |
| `downloads.onChanged` | إشعار «اكتمل/فشل» للتحميلات داخل `FacebookSaverPro` بأيقونات SVG inline (data URI) |
| مؤقّت مراقبة ذاكرة | `setInterval` كل 60 ثانية يستدعي `chrome.runtime.getMemoryInfo` (غير متوفر في MV3) |

## 5) المكتبات والتقنيات (Libraries/Stack)

- **صفر مكتبات خارجية** — لا jQuery ولا أي CDN؛ JavaScript خالص.
- **واجهات المتصفح المستخدمة**: DOM + CSS، `MutationObserver`، `fetch`/`Blob`/`ClipboardItem`، `<canvas>`/`OffscreenCanvas`، `URL`/`srcset` parsing.
- **Chrome APIs**: `chrome.runtime` (مراسلة)، `chrome.downloads` (تنزيل + `onChanged` + `search`)، `chrome.notifications`.
- **الهدف**: إضافة كروم/إيدج MV3 (Service Worker background) — لا Node ولا بناء ولا أدوات تطوير.

## 6) مخازن البيانات (Data Stores)

- **لا توجد مخازن بيانات على الإطلاق** — لا IndexedDB، ولا `chrome.storage` (رغم أن صلاحية `storage` مُعلنة في الـ manifest ولا يُستخدمها أي ملف)، ولا localStorage.
- الحالة كلها **مؤقتة في الذاكرة**: `processedImages` (Set لعناصر الصور المعالجة)، `isActive`، `buttonCount`.
- **الإخراج الوحيد**: ملفات صور تُحفَظ في مجلد التنزيلات تحت `FacebookSaverPro/facebook.com/fb_image_<timestamp>.<ext>` (الامتداد يُستنتج من URL، وافتراضيًا jpg).

## 7) التكاملات الخارجية (Integrations)

- **فيسبوك** (الهدف الرئيسي): صفحات `facebook.com` و CDN الصور `fbcdn.net`/`scontent` — إعادة بناء الروابط بتنظيف معاملات الحجم (`oh`/`oe`، لواحق `_s/_m`، مسارات الحجم، سلاسل `_nc_`).
- **بروكسي خارجي**: الاستراتيجية الثانية للنسخ ترسل رابط الصورة إلى `https://cors-anywhere.herokuapp.com/<url>` — خدمة عامة طرف ثالث (تسريب عناوين الصور الموقّعة إليها، وتتطلب تفعيلًا يدويًا في خدمتها، وهي عمليًا موثوقيتها ضعيفة).
- **منظومة كروم**: `chrome.downloads` (التحميل الفعلي)، `chrome.notifications` (إشعارات البدء/الاكتمال/الفشل)، `chrome.runtime` (رسائل).
- **الأمان**: لا يوجد أي توكن/مفتاح/سر في الكود إطلاقًا — التكامل كله يمر عبر جلسة المتصفح نفسها (الكوكيز غير مُرسلة صراحة: `credentials: 'omit'` في الاستراتيجية الأولى).

## 8) تقييم الصحة والجودة (Health Assessment)

**إيجابيات:**
- عزل نطاق سليم: IIFE + `'use strict'` في سكربت المحتوى.
- كشف صور متعدد المحددات مع فلترة حقيقية (حجم، أيقونات، أفاتارات) — يقلّل الضجيج.
- مسار تحميل مزدوج (رئيسي + احتياطي) و`conflictAction: uniquify` — أسماء لا تتصادم.
- التعامل الصحيح مع `chrome.runtime.lastError` في الإشعارات، و`return true` للاستجابة غير المتزامنة.

**مشاكل ومخاطر (مرتبة بالخطورة):**

1. **صلاحيات مفرطة جدًا** (الأخطر): `host_permissions` تشمل `https://*/*` و`http://*/*`، وسكربت المحتوى يُحقن في `<all_urls>` بكل الفريمات، و`web_accessible_resources: *` لكل المواقع — لوظيفة محصورة في فيسبوك هذا تضخّم سطح الهجوم ويُرجَّح رفضه في متجر كروم.
2. **تعديل DOM فيسبوك مباشرة**: لفّ الصورة داخل container جديد يتعارض مع إدارة React لشجرة الصفحة — هشاشة وتكسير تخطيط محتمل عند إعادة الرسم.
3. **إعادة بناء الرابط قد تكسره**: حذف كل معاملات `_nc_` من روابط scontent يُسقط توقيع الوصول → أخطاء 403/404 محتملة لجزء من الصور.
4. **البروكسي الخارجي**: `cors-anywhere.herokuapp.com` غير موثوق عمليًا (يتطلب تفويضًا يدويًا)، ويرسل روابط الصور الموقّعة لطرف ثالث.
5. **`createSuccessIcon()` معطّل منطقيًا**: تعيد Promise لكن الاستدعاء يمرّرها مباشرة كـ `iconUrl` في `chrome.notifications.create` — سيُرفض الإشعار الأول (يُطمره كود `lastError`)؛ الإشعارات اللاحقة تستخدم SVG data-URI صحيح.
6. **Service Worker ومؤقّت دائم**: `setInterval` كل دقيقة + `chrome.runtime.getMemoryInfo` (غير موجودة في MV3) — الـ SW يُقتل بعد الخمول فالمؤقّت لا يستمر، وإن استمر يرمي خطأ كل دقيقة (استدعاء غير موجود). عديم الفائدة هنا.
7. **كثرة الإشعارات داخل الصفحة**: إشعار «تم اكتشاف صور جديدة» عند كل مسح مثمر + مسح كل 5 ثوانٍ + لكل إطار (`all_frames`) → ضجيج بصري متكرر.
8. تفسير `srcset` بافتراض «الأخير = الأكبر» غير مضمون دائمًا، و`User-Agent` مخصص في fetch يُتجاهل من المتصفح (header محظور) وقد يسبب preflight إضافي.

**الحكم العام**: إضافة صغيرة عاملة للاستخدام الشخصي (v3.0 بلا تاريخ إصدارات)، تنجز وظيفتها الأساسية (تحميل/نسخ)، لكنها غير جاهزة للنشر العام بسبب الصلاحيات، وتحتمل تحسينًا في استقرار DOM وسلامة روابط الجودة.

## 9) خريطة دخول للتطوير (Onboarding Map)

**ترتيب قراءة مقترح (3 ملفات ≈ 885 سطرًا):**
1. `manifest.json` — يحدد الصلاحيات ونقاط الحقن (يشرح كل ما يلي).
2. `facebook-saver.js` — ابدأ من `initFacebookSaverPro` (السطر ~648) ثم صعودًا: المعالجة → الأزرار → التحميل/النسخ → الكشف.
3. `background-pro.js` — نقطة واحدة فقط: `onMessage` ثم `handleFacebookDownload`.

**أين تعدّل ماذا:**
- لتغيير **نطاق العمل** (فيسبوك فقط): `manifest.json` → `content_scripts.matches` و`host_permissions`.
- لتغيير **معايير كشف الصور**: `findFacebookImages` + `isValidFacebookImage` في `facebook-saver.js`.
- لتغيير **شكل الأزرار والإشعارات**: `injectPowerfulStyles` (بلوك CSS واحد).
- لتغيير **مجلد الحفظ أو أسماء الملفات**: `folderPath` في `background-pro.js` + `generateUniqueFilename` في `facebook-saver.js`.
- لتغيير **إعادة بناء الرابط للجودة العالية**: `getHighestQualityUrl`.

**أولويات تحسين مقترحة:** ① تضييق الصلاحيات والمطابقات ② حذف استراتيجية البروكسي الخارجي ③ جعل حذف معاملات `_nc_` اختياريًا (خيار toggle) ④ إزالة `setInterval` من الـ SW ⑤ تقليل الإشعارات داخل الصفحة ⑥ إضافة أيقونات للإضافة (مفقودة تمامًا).

## 10) فهرس الملفات (File Index)

| الملف | دوره | ملاحظة |
|---|---|---|
| `manifest.json` (49 سطرًا) | تعريف إضافة MV3: الاسم/الإصدار، 5 صلاحيات، host_permissions واسعة جدًا، حقن سكربت المحتوى في `<all_urls>`، service worker | لا أيقونات ولا popup — الإضافة لا تظهر إلا عبر أزرارها داخل الصفحات |
| `facebook-saver.js` (676 سطرًا) | سكربت المحتوى: كشف صور فيسبوك، لفّها وحقن زرّي تحميل/نسخ، إشعارات داخل الصفحة، إرسال طلب التحميل للخلفية | IIFE واحدة بلا مكتبات؛ ≈50% منها CSS مُحقون |
| `background-pro.js` (160 سطرًا) | Service Worker: استقبال `facebook_download`، تنفيذ `chrome.downloads` إلى `FacebookSaverPro/`، إشعارات نظام، مراقبة اكتمال التحميلات | يحوي معطليْن فعليين: `getMemoryInfo` (غير موجودة في MV3) و`createSuccessIcon` (Promise في مكان نصي) |
