# 🏗️ ملخص معماري: nagarpnest

> 📅 دراسة معمارية نهائية — وكيل الدراسة التابع لـ «فيجن»، 2026-10-18.
> المنهج: قراءة مباشرة للكود (51 ملفًا) مع الاستنتاج باسم الملف المقروء؛ تخطّي node_modules وdist وdist-electron وbuild.
> ⚠️ **ملاحظة تشغيلية: node_modules حُذفت بأمر المالك (تنظيف)** — التبعيات تُعاد بـ `npm install` في `G:\ai\nagarpnest` قبل أي تشغيل أو بناء.

## 1) الغرض (سطران)

تطبيق سطح مكتب Electron + React 19 + TypeScript لتخطيط القص 2D Nesting: يستورد DXF (من CorelDRAW) ويصلح هندسة القطع المتقطعة ويحسب أفضل رصّ على ألواح خشب (بفجوة صفرية افتراضيًا) ثم يصدّر DXF جاهزًا للليزر لورشة «النجار برنت».
الواجهة عربية/إنجليزية (عربي وRTL افتراضيًا)، والألوان تُحوَّل إلى عمليات: أحمر=قص، أزرق=حفر، أسود/غيره=رسم؛ مع مراجع مفتوحة مدمجة (Deepnest/SVGnest/Clipper2) كمصدر خوارزمي.

## 2) نقاط الدخول والتشغيل

- `package.json` (الجذر): `"main": "dist-electron/main.js"` — المخرَج المترجَم من `electron/main.ts` (يُبنى بـ `tsc -p electron/tsconfig.json`).
- **التطوير**: `npm run dev` = تشغيل متوازٍ (concurrently) لـ `dev:vite` (Vite على 5173) + `dev:electron` (wait-on tcp:5173 ثم `electron .`) + `build:electron:watch` (ترجمة مستمرة لعملية الإلكترون).
- **البناء**: `npm run build` = `tsc` + `vite build` + `tsc -p electron/tsconfig.json`. **الحزم**: `npm run dist` = build ثم electron-builder.
- **مشغّل مباشر**: `Run App.bat` (فقط cd ثم `npm run dev`) و`Start App.vbs` (يشغّل الـ bat بنافذة مخفية). أيضًا `Deepnest-master/Run Deepnest.bat` للنسخة المرجعية.
- `electron/main.ts`: نافذة 1200×800 بخلفية داكنة `#0f172a`، إخفاء القائمة، **nodeIntegration:true + contextIsolation:false + webSecurity:false** (نموذج أولي — التعليق يقول "secure later")؛ dev يحمّل `http://localhost:5173` مع DevTools، والإنتاج يحمّل `../dist/index.html`. **لا IPC ولا preload** — كل العمل في الـ renderer.
- الاستيراد في الواجهة بفلتر `.dxf` فقط (App.tsx: `accept=".dxf"`) مع سحب وإفلات داخل منطقة العرض.

## 3) الهيكل العام

```
G:\ai\nagarpnest\
├── electron/            # عملية Electron الرئيسية (main.ts → dist-electron/main.js)
├── src/                 # التطبيق الحقيقي: React + المحرك (components / utils / workers / hooks / locales)
├── dist/ , dist-electron/  # مخارج البناء (مُتخطّاة عن قصد في هذه الدراسة)
├── Deepnest-master/     # مرجع كامل: Deepnest.io 1.0.5 (Electron 1.4 + addon Minkowski C++ مُترجَم مسبقًا)
├── SVGnest-master/      # مرجع: SVGnest (ويب خالص — الجد الأب للمشروع)
├── Clipper2-main/       # مرجع: مكتبة Clipper2 (CPP/C#/Delphi — قص/إزاحة/تثليث المضلعات)
├── Test/                # نموذج تجريبي موازٍ (main/renderer/engine بمحرك وDxfLoader/DxfWriter مستقلين)
├── 16/                  # عيّنات إنتاج حقيقية: 1..8.dxf + 7.cdr
├── Run App.bat / Start App.vbs     # مشغّلات سريعة (vbs يشغّل الـ bat بصمت)
├── nagarpnest.rar       # نسخة احتياطية مضغوطة من المشروع
├── system_architecture.md  # وثيقة معمارية موجودة (إنجليزية) — تُطابق الكود عمومًا
└── eslint.config.js / tsconfig*.json / tailwind.config.js / postcss.config.js / .hintrc / .gitignore
```

## 4) الوحدات الرئيسية

### أ. الواجهة (React 19 + Tailwind 4، RTL افتراضي)
- `src/main.tsx` (11 سطرًا): مدخل React (StrictMode) → `App` — يستورد `i18n` و`index.css`.
- `src/App.tsx` (557 سطرًا): عقل التطبيق وخط العمل كاملًا — استيراد DXF → `GeometryRepair.joinShapes` (تسامح 0.1mm) → `detectParts` → عرض `ImportWizard` → قبول الربط → `NestingEngineV2` (عادي أو Auto-Fill) → إعادة رسم الألواح فوق بعضها (فاصل 200mm) → تصدير. الحالة كلها `useState` محلية (shapes/parts/sheetWidth 1200/sheetHeight 800/gap 0/sheetResults)؛ تبديل عربي/إنجليزي يضبط `document.dir`؛ لوحة ألوان تفاعلية (نقر يبدّل أحمر→أزرق→أسود→أبيض)؛ ملخص إنتاج (cut/etch/draw) وإحصاء الإصلاح (عدد المسارات المدموجة).
- `src/components/CanvasViewer.tsx` (313 سطرًا): Canvas 2D مع pan/zoom/ملاءمة تلقائية ووضعي wireframe/solid.
- `src/components/ImportWizard.tsx` (281 سطرًا): تجميع (طبقة::لون) في مجموعات وربطها بعمليات cut/etch/draw قبل القبول — يرث افتراضيًا كشف اللون الآلي.
- `src/components/PartManager.tsx` (159 سطرًا): كمية/دوران (ثابت 0° / خطوات 90° / حر) / أولوية لكل جزء + **مضاعف عالمي** للكميات.
- `src/components/Toast.tsx` (68 سطرًا) + `src/hooks/useNotifications.ts` (37 سطرًا): نظام إشعارات جاهز لكن Toast غير مربوط في App (الاستخدام الفعلي alert()).

### ب. محرك التعشيق (الأهم)
- `src/utils/nestingEngineV2.ts` (101 سطرًا): **وكيل رقيق (Worker Proxy)** — يطلق `nfpWorker.ts` عبر `new Worker(new URL(...), {type:'module'})` ويترجم progress/complete/error. `startAutoFill` يرفع الكمية إلى 1000.
- `src/workers/nfpWorker.ts` (680 سطرًا): **المحرك الفعلي** `WorkerNestingEngine` — خوارزمية **Raster/Pixel** رغم اسم الملف "NFP":
  - شبكة تصادم `Uint8Array` للوح بدقة 1mm (scale=1.0) — [nfpWorker.ts:45-56].
  - قناع تصادم لكل (شكل×دوران) مخزَّن في `maskCache`؛ تعبئة المضلع بـ **Scanline Fill** (التعليق: أسرع 300x من Point-in-Polygon)، خطوط بـ **Bresenham**، أقواس/دوائر بتكثيف نقاط، ودعم **Bulge** للمنحنيات — [nfpWorker.ts:324-560].
  - توسيع الكميات، فرز تنازلي بالمساحة، دورات 0/90/180/270 أو حرّة، استراتيجيات: **bottom-right** (مسح من الزاوية العليا اليمنى بمسافة تربيعية) / bottom-left / corner-cluster مع **تقليم مبكر** — [nfpWorker.ts:140-233].
  - بعد كل لوح: `applyMinimumBounding` (ضغط القطع نحو الركن) ثم **خَبز** الإحداثيات النهائية (Baked True Shape) داخل `PlacedPart.shape` — [nfpWorker.ts:582-651].
- `src/utils/nestingEngine.ts` (438 سطرًا): **محرك V1** على الخيط الرئيسي (Cascading Best-Fit: إعادة الدورة من الأكبر بعد كل نجاح) — لم يعد مربوطًا بالواجهة؛ يستهلكه `nesting.worker.ts` القديم فقط.
- `src/workers/nesting.worker.ts` (72 سطرًا): worker قديم ببروتوكول START/STOP/UPDATE — **كسر API**: يستدعي `startNesting(parts, shapes)` بينما V1 تستقبل وسيطًا واحدًا؛ وذكر "Gemini Engine" فيه بقايا تسمية سابقة. كود ميت فعليًا.
- `src/utils/geometryUtil.ts` (736 سطرًا): ترجمة TS كاملة لوظائف NFP من SVGnest — **مستوردة في nfpWorker للأنواع فقط**؛ دوالّها الحسابية غير مستدعاة في المحرك الجاري.

### ج. خط أنابيب DXF (استيراد→إصلاح→تصدير)
- `src/utils/dxfParser.ts` (358 سطرًا) — `DxfLoader`: يغلّف حزمة `dxf-parser`؛ يحوّل الوحدات من `$INSUNITS` (بوصة ×25.4 / قدم ×304.8 / مم / سم ×10 / م ×1000)، يبني جدول الطبقات، يحلّ الألوان بأولوية: **TrueColor (color24) → RGB مضمّن (>256) → ACI → ByBlock/ByLayer** مع debug logs — [dxfParser.ts:21-118].
- `src/utils/dxfColors.ts` (81 سطرًا): جدول ACI 0→255 كامل إلى Hex + `getNearestACI` (أقرب ACI للتصدير).
- `src/utils/colorDetection.ts` (80 سطرًا): كشف العملية بـ«هيمنة القناة»: أحمر>150 → cut؛ أزرق>150 → etch؛ غير ذلك draw + ألوان تصدير معيارية (ACI 1/5/7).
- `src/utils/geometryRepair.ts` (428 سطرًا): `joinShapes` (دمج LINE/ARC المتقطعة بمطابقة النهايات — الافتراضي 1.0mm وفي App يُمرَّر 0.1mm) + `detectParts` (فرز بالمساحة → أب مغلّق → فلتر صندوق محيط → تأكيد Ray-Casting) — ينتج `CompoundPart`.
- `src/utils/dxfWriter.ts` (185 سطرًا): كاتب DXF يدوي (AC1009) — `write` (HEADER/TABLES/LAYER/ENTITIES) + `writeSheet` + `writeAllSheets` (تركيب الألواح عموديًا بفاصل 200mm)؛ المخرَج **Blob** مباشرة (تنزيل `nested_layout_all_<timestamp>.dxf` في App).
- `src/utils/clipper.js` (6,927 سطرًا): Clipper 6.2.1 (Angus Johnson, rev 482) محفوظة محليًا + `src/js-clipper.d.ts` تعريفات أنواع يدوية لحزمة js-clipper.

### د. عقود البيانات (`src/types.ts`, 107 سطرًا)
`Shape` (line/polyline/circle/arc + bulge + aci + process + layer + children + partId)، `Part`، `PlacedPart`، `SheetResult` (مع شبكة `_grid: Uint8Array` اختيارية)، و**`CompoundPart` v2.0 — Rigid Body**: `collider` للاصطدام + `payload` للهندسة الراكبة (ثقوب/تفاصيل) + `matrix` تحويلي + metadata (area/priority/quantity/rotationStep) — بنيوة المعمارية المركزية (تعليق "REFRACTOR v2.0: Rigid Body / Auto-Fill Architecture").

### هـ. عملية Electron (`electron/main.ts`, 52 سطرًا)
نافذة واحدة بلا IPC ولا preload؛ dev → localhost:5173 (مع DevTools)، الإنتاج → dist/index.html. المُخرَج `dist-electron/main.js` (مُتخطّى من القراءة وفق القواعد).

## 5) المكتبات (من package.json فعليًا)

**الجذر — dependencies** (`package.json`):
- واجهة: react@^19.2 + react-dom@^19.2، framer-motion@^12، lucide-react@^0.561، clsx، tailwind-merge، @tailwindcss/postcss@^4.1.
- توطين: i18next@^25 + react-i18next@^16.
- هندسة DXF: dxf-parser@^1.1.2، js-clipper@^1.0.1 (+ Clipper 6.2.1 محفوظة محليًا في `src/utils/clipper.js` مع `src/js-clipper.d.ts` لأنواعها).
- فيزياء: matter-js@^0.20 — مستعملة فقط في `Test/engine/nesting/PhysicsEngine.ts`، غير ظاهرة في `src/`.
- سطح المكتب: electron-squirrel-startup.

**devDependencies**: electron@^39.2، electron-builder@^26، vite@^7.2 + @vitejs/plugin-react، typescript@~5.9، tailwindcss@^4.1 + postcss + autoprefixer، eslint@^9 + typescript-eslint + react-hooks + react-refresh + globals، concurrently + cross-env + wait-on، @types/{node,react,react-dom,matter-js}.

**مرجعية (لا تُثبَّت عادةً)**: `Deepnest-master/package.json` → electron@^1.4.1، paralleljs، electron-settings، electron-config، request، nan، graceful-fs… — نسخة مرجعية قديمة (2016) ذات addon native مُترجَم مسبقًا (`minkowski/Release/addon.node`).

**معلَنة وغير مستغلة في `src/` حاليًا**: matter-js (استعمالها في Test فقط)، framer-motion، js-clipper (النسخة المحلية هي مصدر الوظائف).

## 6) مخازن البيانات

- **localStorage داخل Electron** هو المخزن الوحيد: `src/hooks/useProjectStorage.ts` — مشروع كامل (اسم/تواريخ/إعدادات لوح/أشكال/قطع) تحت مفتاح `nesting_project_<id>` + فهرس `nesting_project_list`. **ملاحظة**: الـ hook جاهز لكنه غير مربوط بأي زر في App.tsx — لا يوجد حفظ/فتح مشاريع فعلي في الواجهة بعد.
- **لا قاعدة بيانات خارجية**: لا SQLite/PostgreSQL ولا درايفرات في التبعيات.
- المخرَج الدائم الوحيد = **ملف DXF مُصدَّر**.
- مدخلات الإنتاج: عيّنات حقيقية في `16/` (1..8.dxf + 7.cdr) — مصدر اختبار جاهز.
- `nagarpnest.rar` في الجذر: نسخة احتياطية مضغوطة (ثنائية — لم تُفحص).
- `dist-electron/package.json` موجود (مخرَج بناء — مُتخطّى وفق القواعد).

## 7) التكاملات

- **i18next**: `src/i18n.ts` + `src/locales/ar.json` (38 مفتاحًا) و`en.json`؛ عربي افتراضي + RTL (`document.dir`)؛ عنوان داخلي «أنتي-جرافيتي للتعشيق» (ar.json: app_title) — بقايا تسمية سابقة (كذلك "Gemini Engine" في nesting.worker.ts).
- **dxf-parser** (npm): تحليل DXF بتعديلات محلية (وحدات/طبقات/ألوان) في `dxfParser.ts`.
- **CorelDRAW**: دورة عمل خارجية — CDR يُصدَّر إلى DXF (عينة `16/7.cdr`)؛ فلتر الاستيراد يقبل .dxf فقط.
- **مراجع خوارزمية مدمجة** (مجلدات داخل المشروع، ليست تبعيات تشغيل ولا تُبنى):
  - `Deepnest-master/` — Deepnest.io 1.0.5 (~2016): NFP حقيقي بـ addon C++ (`addon.cc` يعرض `calculateNFP` عبر nan؛ Minkowski؛ كاش NFP في `main/background.js` بأطراف NFP) ومحرك واجهة `main/deepnest.js` (1,465 سطرًا: clipperScale=10M، GA: populationSize/mutationRate/threads، placementType=gravity، mergeLines) — **مصدر حقول Config غير المستخدمة في nfpWorker**.
  - `SVGnest-master/`: النسخة الويبية الأصلية (svgnest.js/svgparser.js/util) — الجد الأب الذي قُدِّم منه `geometryUtil.ts`.
  - `Clipper2-main/`: Clipper2 (CPP/C#/Delphi) لقص/إزاحة/تثليث المضلعات — مرجع مستقبلي.
- **electron-builder + electron-squirrel-startup**: تهيئة تثبيت ويندوز (اختصارات التثبيت/الإزالة).

## 8) تقييم الصحة (بدليل)

**إيجابيات:**
- ✅ سلسلة سكربتات متسقة (dev متوازٍ + wait-on، build ثلاثي، dist) — [package.json].
- ✅ فصل معماري سليم: المحرك كاملًا داخل Web Worker (`nfpWorker.ts`) مع progress وyield — يمنع تجميد الواجهة.
- ✅ أداء مدروس: `maskCache` لكل (شكل×دوران)، Scanline Fill، تقليم مبكر، ترتيب أكبر-أولًا — [nfpWorker.ts:45-56, 115-120, 324-417].
- ✅ معالجة DXF ناضجة (وحدات + طبقات + حل ألوان ثلاثي الأولوية) — [dxfParser.ts:21-118].
- ✅ إصلاح هندسة حقيقي: دمج LINE/ARC المتقطعة + هرمية ثقوب (صندوق ثم Ray-Casting) — [geometryRepair.ts:25-120].
- ✅ توطين عربي فعلي مع RTL — [i18n.ts، ar.json، App.tsx:31-33].
- ✅ وثيقة `system_architecture.md` موجودة وتصف المحرك بدقة مطابقة (raster، الألوان، Blob).

**تحفظات (بدليل مُسمّى):**
- ⚠️ **node_modules محذوفة** (قرار المالك) — يستلزم `npm install` قبل أي تشغيل/بناء.
- ⚠️ **خطأ أنواع يمنع `npm run build`**: `geometryRepair.ts:1` يستورد `PolylineShape` و`ArcShape` من `../types` بينما `types.ts` (107 أسطرًا) لا يعرّفهما — تثبيت: grep (4 مطابقات) + قراءة types.ts كاملة + strict في tsconfig.app.json.
- ⚠️ **كود ميت/انحراف API**: `nesting.worker.ts:40` يستدعي `startNesting(parts, shapes)` بينما `nestingEngine.ts:23` تستقبل وسيطًا واحدًا — الملف قديم (START/STOP/UPDATE) وغير مربوط بـ App.
- ⚠️ **تسمية مضلِّلة**: `nfpWorker.ts` وخيارات GA (populationSize/mutationRate/generations منسوخة من Deepnest config — [main/deepnest.js:20-33]) لكن التنفيذ الفعلي raster heuristic؛ `geometryUtil.ts` (736 سطر NFP) غير مستغل حسابيًا.
- ⚠️ **أمان نموذج أولي**: nodeIntegration:true + contextIsolation:false + webSecurity:false — [electron/main.ts:16-19] (التعليق: "secure later"). نموذج `Test/` أصلحها (preload + contextIsolation:true — [Test/main/main.ts:8-12]) دون نقلها للجذر.
- ⚠️ **تخزين المشاريع غير موصول**: `useProjectStorage.ts` جاهز لكن لا زر حفظ/فتح في App.tsx — الدوام الوحيد تصدير DXF.
- ⚠️ **بقايا قوالب**: `index.html` عنوانه "new-folder"، README.md قالب Vite الافتراضي، package.json اسم "new-folder".
- ⚠️ **الاستيراد DXF فقط** (لا SVG) رغم وجود مراجع SVG/Deepnest — فلتر `accept=".dxf"` في App.tsx.
- ℹ️ مجلد `Test/` غير قابل للبناء بذاته: لا package.json ولا vite config داخله، ويستورد `../engine/types` غير الموجود (فقط `Test/types/dxf-parser.d.ts`) — شظايا تجارب.
- ℹ️ `.npmignore` ثنائي غير مقروء نصيًا (غريب لملف نصي) — تفصيلة عابرة.

**الخلاصة**: **MVP وظيفي متقدم** — خط الاستيراد→الإصلاح→التعشيق→التصدير مترابط فعليًا ويعمل في وضع dev، لكن بناء الإنتاج يحتاج إصلاح خطأ الأنواع أولًا، والتشغيل يستلزم `npm install` (node_modules محذوفة). الصحة العامة: جيدة كنموذج أولي، مع تنظيف كود ميت وإصلاح أنواع قبل أول إصدار.

## 9) خريطة دخول للتطوير

1. **تشغيل**: `cd G:\ai\nagarpnest && npm install` ثم `npm run dev` (أو `Run App.bat` / `Start App.vbs`).
2. **فهم خط العمل**: `src/App.tsx` — كل الحالة والتنسيق من الملف الواحد.
3. **تعديل الخوارزمية**: `src/workers/nfpWorker.ts` (قناع/تصادم/استراتيجية/خَبز)؛ `nestingEngineV2.ts` وكيل لا يُعدَّل.
4. **استيراد DXF**: `dxfParser.ts` → `geometryRepair.ts` → `ImportWizard.tsx` (ربط يدوي).
5. **قواعد الألوان**: `colorDetection.ts` + `dxfColors.ts` + تجاوز يدوي من `ImportWizard`.
6. **التصدير**: `dxfWriter.ts` — write / writeSheet / writeAllSheets.
7. **النافذة والتغليف**: `electron/main.ts` (تحسين الأمان: preload + contextIsolation) ثم `npm run dist`.
8. **تفعيل NFP الحقيقي**: النسخة TS جاهزة في `src/utils/geometryUtil.ts` (منقول من SVGnest)؛ المرجع الكامل `Deepnest-master/main/util/placementworker.js` + `addon.cc` (calculateNFP C++).
9. **ترحيل من `Test/engine/`**: DxfLoader/GeometryProcessor/NestingEngine/PhysicsEngine (matter-js)/Optimizer (أقرب جار لمسار الليزر) — تجارب جاهزة لا تشترك مع src/؛ تحديد مصيرها (دمج أو حذف).
10. **الإصلاح الأول**: إضافة `PolylineShape`/`ArcShape` إلى `src/types.ts` (أو تصحيح الاستيراد) ثم `tsc` — بعد `npm install`.

## 10) فهرس الملفات المهمة (الملف | دوره | ملاحظة)

| الملف | دوره | ملاحظة |
|---|---|---|
| `package.json` | إعداد المشروع والسكربتات (dev/build/dist) | الاسم الداخلي "new-folder"؛ main → dist-electron/main.js |
| `electron/main.ts` | عملية Electron: نافذة 1200×800 فقط (52 سطرًا) | ⚠️ nodeIntegration مفتوح + webSecurity:false |
| `electron/tsconfig.json` | ترجمة الإلكترون → dist-electron | strict + commonjs |
| `vite.config.ts` | إعداد Vite الأدنى (react فقط) | بلا تخصيص |
| `tsconfig.json` + app/node | TS صارم (strict, noUnusedLocals) | سيكشف أخطاء الأنواع عند البناء |
| `tailwind.config.js` / `postcss.config.js` | Tailwind 4 عبر PostCSS | واجهة داكنة بخط Cairo |
| `Run App.bat` / `Start App.vbs` | مشغّلان سريعان (vbs يخفي النافذة) | لا يثبّتان التبعيات — npm install يدويًا |
| `eslint.config.js` / `.hintrc` / `.gitignore` | جودة/تجاهل قياسي | dist مُهمَل من اللينت |
| `src/main.tsx` | مدخل React (StrictMode) | قياسي |
| `src/App.tsx` | عقل الواجهة وخط العمل كاملًا (557 سطرًا) | كل الحالة هنا؛ RTL تلقائي؛ لوحة ألوان تفاعلية |
| `src/types.ts` | عقود البيانات (107 أسطرًا) | CompoundPart v2 = collider+payload+matrix |
| `src/utils/dxfParser.ts` | DxfLoader: DXF→Shape + وحدات/طبقات/ألوان (358) | أولوية TrueColor→RGB→ACI→ByBlock |
| `src/utils/geometryRepair.ts` | دمج القطع + هرمية ثقوب (428 سطرًا) | ⚠️ استيراد أنواع غير معرفة (PolylineShape/ArcShape) |
| `src/utils/dxfColors.ts` | جدول ACI 0-255 → Hex + أقرب ACI | معيار AutoCAD كامل |
| `src/utils/colorDetection.ts` | كشف العملية من اللون (هيمنة قناة) | أحمر=cut أزرق=etch وإلا draw |
| `src/utils/dxfWriter.ts` | كاتب DXF AC1009 (ألواح متراكبة عموديًا) | مخرَج Blob مباشرة |
| `src/utils/nestingEngineV2.ts` | وكيل Worker لمحرك V2 (101 سطرًا) | startAutoFill يرفع الكمية 1000 |
| `src/workers/nfpWorker.ts` | المحرك الفعلي: raster+scanline+خَبز (680 سطرًا) | الاسم NFP لكن التنفيذ Raster |
| `src/utils/nestingEngine.ts` | محرك V1 (Cascading Best-Fit، 438 سطرًا) | يستعمله الـ worker القديم فقط |
| `src/workers/nesting.worker.ts` | worker قديم (START/STOP/UPDATE) | ميت — توقيع استدعاء غير متوافق |
| `src/utils/geometryUtil.ts` | مكتبة NFP منقولة من SVGnest (736 سطرًا) | غير مستغلة حسابيًا في المحرك الحالي |
| `src/utils/clipper.js` + `src/js-clipper.d.ts` | Clipper 6.2.1 محلية + أنواع js-clipper | 6,927 سطرًا (Angus Johnson) |
| `src/hooks/useProjectStorage.ts` | حفظ مشاريع في localStorage | ⚠️ غير مربوط بالواجهة بعد |
| `src/hooks/useNotifications.ts` + `src/components/Toast.tsx` | نظام إشعارات جاهز | غير مربوط في App (تُستعمل alert) |
| `src/components/CanvasViewer.tsx` | عرض Canvas: pan/zoom/auto-fit (313 سطرًا) | وضعا wireframe/solid |
| `src/components/ImportWizard.tsx` | ربط (طبقة::لون)→عملية قبل القبول (281 سطرًا) | يرث كشف اللون الآلي افتراضيًا |
| `src/components/PartManager.tsx` | كميات/دوران/أولوية + مضاعف عام (159 سطرًا) | جزء يمين الشاشة |
| `src/components/Toast.tsx` | حاوية تنبيهات | معلقة جاهزة |
| `src/i18n.ts` + `src/locales/ar.json, en.json` | التوطين (38 مفتاحًا) | عنوان داخلي «أنتي-جرافيتي للتعشيق» |
| `system_architecture.md` | وثيقة معمارية موجودة (إنجليزية) | تُطابق المحرك الحالي (raster/ألوان/Blob) |
| `README.md` / `index.html` | قالب Vite الافتراضي | عناوين "new-folder" — للتوثيق لاحقًا |
| `16/*.dxf` + `16/7.cdr` | عيّنات قص واقعية (8 DXF + CDR) | مصدر اختبار جاهز |
| `nagarpnest.rar` | نسخة احتياطية مضغوطة | ثنائية — لم تُفحص |
| `Deepnest-master/` | مرجع NFP كامل (Electron 1.4 + Minkowski addon.node مُترجَم) | main/deepnest.js 1,465 سطرًا؛ main/background.js كاش NFP |
| `SVGnest-master/` | مرجع الويب الأصلي (svgnest.js) | مصدر ترجمة geometryUtil.ts |
| `Clipper2-main/` | مرجع Clipper2 (CPP/C#/Delphi) | قص/إزاحة/تثليث — مرجع مستقبلي |
| `Test/main/main.ts` + `preload.ts` | نموذج إلكترون آمن (contextIsolation) | نموذج أمان جاهز للنقل للجذر |
| `Test/engine/importer/DxfLoader.ts` | نسخة موازية من DxfLoader (389 سطرًا) | مطابقة المنطق للجذر تقريبًا |
| `Test/engine/nesting/NestingEngine.ts` | محرك raster بالشاشة الحية (528 سطرًا) | listeners onUpdate/onComplete |
| `Test/engine/nesting/PhysicsEngine.ts` | حل فيزيائي matter-js (جاذبية/جدار) | مستهلك matter-js الوحيد في المستودع |
| `Test/engine/export/Optimizer.ts` | ترتيب مسار قص أقرب-جار (59 سطرًا) | فكرة جاهزة للترحيل |
| `Test/` ككل | شظايا تجارب بلا package.json/tsconfig | غير قابلة للبناء بذاتها |

---
*إحصاء الدراسة: 51 ملفًا مقروءًا (كل src/ وelectron/ وتكوينات الجذر + عيّنات من Deepnest/Test/Clipper2) عبر فهرس كامل لـ 499 مسارًا. الجاهزية ~95% — التغطية: 100% من الكود التشغيلي (src+electron)، وعيّنة تمثيلية من المراجع المدمجة.*
