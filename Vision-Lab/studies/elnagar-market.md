# 🏗️ ملخص معماري: elnagar market

## 1. الغرض
متجر إلكتروني (Storefront + لوحة تحكم أدمن) لعلامة «النجار برينت» لمنتجات الطباعة المخصصة وحفر الليزر (مجات، تابلوهات، بوكسات هدايا، أقلام، دروع). واجهة عميل عربية RTL بثيم أسود/ذهبي، دورة طلب كاملة: تصفح ← تخصيص ← سلة ← دفع فودافون كاش برفع إيصال ← تتبع الطلب، مع بوابة عملاء جملة بأسعار مخفضة. مُولَّد من Google AI Studio Applet ويعمل بالكامل على Firebase (بدون باكند مخصص).

## 2. نقاط الدخول والتشغيل
- **`index.html`**: صفحة الدخول — `lang="ar" dir="rtl"`، خطوط Google (Amiri + Tajawal)، تحمّل `/src/main.tsx`. العنوان: «النجار برينت | فخامة الطباعة المخصصة».
- **`src/main.tsx`**: ركوب React — `<App/>` داخل `StrictMode` على `#root` + استيراد `index.css`.
- **`src/App.tsx`**: العقل الموجّه — يبني شجرة الـ Providers: `Settings → Category → Product → Wholesale → Cart`، ثم يبدّل بين `Storefront` (واجهة العميل) و`AdminDashboard` حسب حالة `isAdminMode` (يُقلب بزر عائم بالأسفل يمين — دخول أدمن بلا كلمة مرور!). `ThemeStyles` يحقن ألوان الثيم من `settings` كمتغيرات CSS.
- **أوامر التشغيل** (`package.json`، الاسم الداخلي `react-example`):
  - `npm run dev` → `vite --port=3000 --host=0.0.0.0`
  - `npm run build` → `vite build` | `npm run preview` → `vite preview`
  - `npm run lint` → `tsc --noEmit` (فحص أنواع فقط — لا ESLint)
  - `npm run clean` → `rm -rf dist`
  - النشر: `firebase deploy --only hosting` (مكتوبة بخط اليد في `New Text Document.txt`)
- **README.md**: قالب قياسي من AI Studio (`npm install` + `GEMINI_API_KEY` في `.env.local` + `npm run dev`) — لم يُحدَّث ليعكس طبيعة المتجر.
- لا يوجد routing حقيقي (لا react-router) — التطبيق SPA بعرض واحد يتناوب بين الواجهتين.

## 3. الهيكل العام
```
elnagar market/
├── index.html                  # صفحة RTL تحمّل main.tsx
├── package.json / tsconfig.json / vite.config.ts
├── firebase.json               # نشر: hosting=dist + rewrites SPA، firestore، storage
├── .firebaserc                 # المشروع: canvas-abacus-474519-b5
├── firestore.rules / storage.rules  # قواعد = سماح كامل read/write (⚠️)
├── firebase-applet-config.json # تهيئة Firebase + معرّف قاعدة Firestore المسماة
├── firebase-blueprint.json     # مخطط Schemas لمجموعتي orders و wholesale_users
├── metadata.json               # اسم الوصف التسويقي «النجار برينت» (AI Studio)
├── .env / .env.example         # GEMINI_API_KEY + APP_URL (قالب AI Studio)
├── .maestro.md                 # سياق مشروع Maestro — يؤكد أن Gemini غير مدموج بعد
├── maestro-main/maestro-main/  # مستودع منفصل متداخل (مجموعة مهارات Maestro + خادم MCP) — لا علاقة له بمنطق المتجر
└── src/
    ├── main.tsx → App.tsx      # سلسلة الدخول
    ├── firebase.ts             # تهيئة Firestore (قاعدة مسماة) + Auth + Storage
    ├── index.css               # ثيم Tailwind v4: ذهبي/أسود + ثيمات رمضان ورأس السنة
    ├── context/                # 5 مزوّدي حالة: Cart, Settings, Product, Category, Wholesale
    ├── data/                   # store.ts (بذور منتجات/أقسام) + admin.ts (طلبات Mock)
    └── components/             # واجهة العميل (13) + components/admin/ (8)
```
ملاحظة: `maestro-main` متداخل مرتين (`maestro-main/maestro-main/`) ويحوي حزمة مهارات وكيل + `mcp-server` — مرجع مستقل لا يشارك في بناء المتجر.

## 4. الوحدات الرئيسية
- **واجهة العميل** (`src/components/`): `Hero` (بانر من `settings.bannerUrl`)، `CategoryTabs` (أقسام نشطة فقط، sticky)، `OffersSection` (عروض `isOffer=true` بعدّاد تنازلي زائف ثابت)، `ProductGrid` (شبكة مع تسعير ذكي: خصم القسم بالجنيه + سعر جملة)، `ProductModal` (معرض صور + معاينة حية لنص الحفر/الطباعة + يوجّه للمخصّصات)، `MugCustomizer` (مجات متعددة، 3 خانات صور DataURL، نص، ملاحظات)، `TableauCustomizer` (3 مقاسات بأسعار وحد أدنى/أقصى صور، صورة مرجعية)، `CheckoutPage` (نموذج الطلب الكامل)، `OrderTrackingModal` (تتبع برقم الطلب)، `WholesaleLoginModal` (دخول/تسجيل جملة)، `Footer` (تواصل + سوشيال + أيقونة واتساب SVG يدوية).
- **لوحة التحكم** (`src/components/admin/`): `AdminDashboard` (وجّه التبويبات + تبويب إعدادات مدمج: بيانات تواصل، رفع بانر إلى Storage، ألوان ثيم، استعادة بيانات افتراضية) — `Sidebar` (8 تبويبات)، `OrdersTable` (بث Firestore حي + بحث)، `OrderModal` (تفاصيل + تغيير الحالة)، `InventoryManager` (CRUD منتجات + رفع صور)، `CategoryManager` (أقسام + خصم بالجنيه لكل قسم)، `OffersManager` (إنشاء/إزالة عروض بخصم من السعر)، `WholesaleManager` (عرض/حذف عملاء جملة)، `AnalyticsDashboard` (إحصائيات ثابتة Mock بلا بيانات حقيقية).
- **مزوّدو الحالة** (`src/context/`): `ProductContext` (بث Firestore `products` + هجرة تلقائية إذا فُضيت + `forceSync` من بذور store.ts)، `CategoryContext` (نفس النمط لمجموعة `categories`)، `WholesaleContext` (دخول بالهاتف عبر `wholesale_users` + حفظ الجلسة في `localStorage.wholesale_user`)، `CartContext` (سلة في الذاكرة فقط — لا تُحفظ)، `SettingsContext` (إعدادات المتجر — قيم افتراضية ثابتة تُعدَّل بالأدمن **دون حفظ في Firestore**).
- **بيانات** (`src/data/`): `store.ts` — 6 أقسام افتراضية + 5 منتجات بذور (درع كريستال/تابلوه/مج/قلم نوت/بوكس)؛ `admin.ts` — `MOCK_ORDERS` قديمة غير مستخدمة فعليًا (جدول الطلبات يقرأ Firestore مباشرة).
- **خدمة Firebase** (`src/firebase.ts`): تصدير `db` / `auth` / `storage` + فحص اتصال صامت.
- **منطق الأعمال**: `CheckoutPage` يكتب مستندًا في `orders` برقم `ORD-<6 خانات عشوائية>`؛ `OrderModal` يحدّث الحالة؛ تدفقات الصور للإيصال والتصاميم تعمل **Base64 DataURL** (حد 800KB للإيصال) لا عبر Storage.

## 5. المكتبات (من package.json)
- **React 19 + react-dom 19**: الواجهة (بدون راوتر).
- **firebase 12**: Firestore + Auth + Storage (الأداة الوحيدة للبيانات).
- **motion 12**: حركات (`motion/react`) في كل النوافذ المنبثقة والقوائم.
- **lucide-react**: الأيقونات.
- **@google/genai 1.29**: SDK Gemini — **مثبَّت وغير مستخدم إطلاقًا في src** (تحقق grep + نص `.maestro.md`).
- **express + dotenv**: في dependencies — **بقايا قالب AI Studio، لا يستعملهما أي ملف**.
- **Tailwind CSS 4** (`@tailwindcss/vite`): ثيم مخصص بـ `@theme` (ذهبي `#F59E0B`، `matte-black #0a0a0a`).
- **Vite 6 + @vitejs/plugin-react**: البناء (vite مكرر بين deps وdevDeps).
- **TypeScript 5.8 + tsx + autoprefixer**: تطوير. لا ESLint ولا ملف اختبارات.

## 6. مخازن البيانات
- **Firestore** (قاعدة مسماة `ai-studio-bae38f8d-...` على مشروع `canvas-abacus-474519-b5`):
  - `products` — وثيقة لكل منتج (id رقمي، سعر/سعر جملة، صور، `isOffer`، `customizationType`، `visibleFields`).
  - `categories` — أقسام مع `isActive` + `discountEGP`/`isDiscountActive`.
  - `orders` — مفتاح الوثيقة = رقم الطلب `ORD-xxxxxx`؛ items محفوظة **JSON stringified**؛ `receiptImage` Base64؛ `createdAt` serverTimestamp؛ حالة من pending→processing→shipped→delivered/cancelled.
  - `wholesale_users` — مفتاح الوثيقة = رقم الهاتف (دخول جملة بلا كلمة سر: مجرد وجود الرقم = دخول).
- **Storage**: `banners/` (بانر الهيرو) و`products/` و`categories/` (صور).
- **حالة محلية**: `localStorage['wholesale_user']` (جلسة جملة). السلة والإعدادات في الذاكرة فقط — **الإعدادات لا تُحفظ في أي مخزن** (تضيع عند التحديث).
- **بذور ساكنة**: `src/data/store.ts` تُزرع تلقائيًا في Firestore إذا كانت المجموعة فارغة (`forceSync`).
- **Auth/Firebase Auth مُهيَّأ لكن غير مستخدم**: الجملة تنشئ وثيقة Firestore بالهاتف، لا حساب مصادقة.

## 7. التكاملات
- **Firebase** (Firestore + Storage + Auth معطّل عمليًا) — مشروع `canvas-abacus-474519-b5`، كونفيغ جاهز في `firebase-applet-config.json` و`.firebaserc` و`firebase.json` (نشر: `firebase deploy --only hosting`).
- **فودافون كاش** — الدفع اليدوي الوحيد: عرض الرقم + رابط USSD `tel:*9*7*<رقم>*<مبلغ>#` + رفع إيصال Base64 (كامل أو عربون 25%).
- **WhatsApp** (`wa.me/<settings.whatsappNumber>`) — زر عائم + الفوتر + قناة تأكيد الطلبات المعلنة للعميل.
- **Firebase Storage** — رفع البانر وصور المنتجات/الأقسام (من الأدمن فقط في الكود الحالي).
- **Gemini (`@google/genai`)** — مثبّت ومُمرَّر عبر `define` في vite لكن **صفر استخدام** (قائمة تحسينات مستقبلية في `.maestro.md`).
- **Google Fonts** (Amiri + Tajawal) و Unsplash و transparenttextures (نقوش CSS).

## 8. تقييم الصحة (بدليل)
- ✅ **قابل للتشغيل بعد `npm install`** — بنية متسقة: كل الاستيرادات تُشير لملفات موجودة (`../firebase`, `context/*`, `components/*`)؛ لا استيراد لأي وحدة خارج src غير معروفة. `node_modules` محذوف (تتجدد بالتثبيت) و`dist/index.html` موجود (بناء سابق ناجح).
- ✅ **تدفق الطلب مكتمل فعلًا**: CheckoutPage → Firestore `orders` → OrdersTable (بث حي) → OrderModal تحديث الحالة → OrderTrackingModal للعميل. نفس خريطة الحالات (`pending→shipped→delivered`) متطابقة في الملفات الثلاثة.
- ⚠️ **أمن حرج**: `firestore.rules` و`storage.rules` = `allow read, write: if true` على كل شيء — أي زائر يقرأ/يعدّل/يحذف الطلبات وبيانات الجملة (دليل: ملفا القواعد، 9/8 سطور).
- ⚠️ **لا حماية للأدمن**: `App.tsx` يفتح لوحة التحكم بزر عائم بلا مصادقة (`AdminToggle (For Demo Purposes)` في التعليق)، و`auth` غير مستخدم إطلاقًا رغم التصدير.
- ⚠️ **`SettingsContext` ذاكرة فقط**: تعديلات الأدمن (الألوان/البانر/رقم فودافون كاش) تضيع عند إعادة التحميل (`handleSaveSettings` يستدعي `updateSettings` المحلي فقط — لا Firestore).
- ⚠️ **صور كبيرة Base64 في Firestore**: إيصالات ومجات وتابلوهات ≤800KB لكل صورة داخل وثيقة `orders` (اقترب من حد 1MB/وثيقة، وتضخيم قراءة الطلبات).
- ⚠️ **عدم اتساق طفيف**: `CategoryTabs` لا يفلتر «offers»/«all» إلا من بذور store؛ عدّاد العروض في OffersSection يحسب خصمًا من `oldPrice` وقد ينهار (NaN%) لو منتج بلا `oldPrice`؛ العدّاد التنازلي ثابت زائف.
- ✅ خفض مخاطرة: `forceSync` يستعيد البذور تلقائيًا عند فراغ المجموعة (أزرار استعادة في تبويب الإعدادات).
- **الحكم**: نموذج أولي/جاهز للعرض التجريبي بميزات تجارية حقيقية (جملة، عربون 25%، هدايا Upsell) لكن **غير جاهز للإنتاج** حتى: شدّ قواعد Firestore/Storage، حماية الأدمن بحساب، حفظ الإعدادات في Firestore، ونقل صور الطلبات إلى Storage.

## 9. خريطة دخول للتطوير
1. **تشغيل**: `npm install` ثم `npm run dev` → `http://localhost:3000` (زر الترس أسفل يمين = لوحة التحكم).
2. **إضافة ميزة في المتجر**: ابدأ من `src/App.tsx` (شجرة الـ Providers وترتيب الشاشات) ← `ProductContext/CategoryContext` هي مصدر البيانات الوحيد ← المكونات تستهلك عبر `useProducts/useCategories/useSettings/useCart/useWholesale`.
3. **إضافة نوع تخصيص جديد**: انسخ نمط `MugCustomizer/TableauCustomizer` — يبني `CartItem` بـ `type` و`customData` (كل شيء Base64)، و`ProductModal` يوجّه حسب `product.categoryId` ('mugs'/'tableaus').
4. **تعديل الطلب/الحالات**: `CheckoutPage.tsx` (إنشاء + حساب الشحن/الهدايا/العربون) و`admin/OrderModal.tsx` (STATUS_OPTIONS + updateDoc).
5. **تسعير الجملة**: مخفوض في `ProductGrid` + `ProductModal` + المخصّصات عبر `isWholesale` + `wholesalePrice` — أي تغيير تسعير يجب أن يمر بالثلاثة.
6. **ثيم جديد**: أضف متغيرات الألوان في `src/index.css` (نمط `.theme-ramadan`) + خيار في `StoreSettings.currentTheme` + `App.tsx` (`themeClass`) + قائمة الأدمن.
7. **تفعيل Gemini**: `process.env.GEMINI_API_KEY` جاهز عبر `vite.config.ts` + `.env` — مكانه الطبيعي وصف منتجات آلي (ملحوظ في `.maestro.md`).
8. **قبل أي نشر حقيقي**: إصلاح قواعد Firestore/Storage (القسم 8) أولًا — النشر يتم بـ `firebase deploy --only hosting`.

## 10. فهرس الملفات المهمة
| الملف | دوره | ما يلزم معرفته |
|---|---|---|
| `index.html` | صفحة الدخول RTL | خطوط Amiri/Tajawal، تحمّل main.tsx |
| `src/main.tsx` | ركوب React | StrictMode على `#root` |
| `src/App.tsx` | التبديل Storefront⇄Admin + شجرة Providers | `isAdminMode` بلا حماية؛ الثيم يُحقن CSS |
| `src/firebase.ts` | تصدير db/auth/storage | يقرأ `firebase-applet-config.json`؛ auth غير مستخدم |
| `src/firebase.ts` + `firebase-applet-config.json` | تهيئة Firebase | قاعدة مسماة AI Studio؛ مفتاح API مكشوف (طبيعي للوب) |
| `firebase-blueprint.json` | مخطط مجموعتي `orders` و`wholesale_users` | مرجع الـ Schemas المتفق عليها |
| `firestore.rules` / `storage.rules` | قواعد الوصول | **سماح كامل — أول ما يُصلح قبل الإنتاج** |
| `firebase.json` + `.firebaserc` + `New Text Document.txt` | النشر | `public: dist`، مشروع `canvas-abacus-474519-b5`، أمر `firebase deploy --only hosting` |
| `src/context/ProductContext.tsx` | CRUD المنتجات + بث حي | زرع بذور تلقائي + `forceSync`؛ `id: parseInt(doc.id)` |
| `src/context/CategoryContext.tsx` | CRUD الأقسام + خصم بالجنيه | نفس نمط المنتجات |
| `src/context/WholesaleContext.tsx` | جلسة الجملة (بدون كلمة سر) | تخزين في localStorage + Firestore `wholesale_users/{phone}` |
| `src/context/CartContext.tsx` | السلة | ذاكرة فقط؛ `customData` يحمل كل بيانات التخصيص |
| `src/context/SettingsContext.tsx` | إعدادات المتجر/الثيم | **لا تُحفظ في Firestore** — تضيع بالتحديث |
| `src/data/store.ts` | بذور الأقسام والمنتجات | مصدر `forceSync`؛ أسعار الجملة هنا |
| `src/data/admin.ts` | `MOCK_ORDERS` | بيانات ديمو قديمة — الجدول الفعلي يقرأ Firestore |
| `src/components/CheckoutPage.tsx` | إنشاء الطلب في Firestore | Vodafone Cash + USSD + إيصال Base64 + عربون 25% |
| `src/components/MugCustomizer.tsx` | تخصيص المجات | 3 خانات صور DataURL داخل `customData` |
| `src/components/TableauCustomizer.tsx` | تخصيص التابلوهات | مقاسات ثابتة في `TABLEAU_SIZES` + حد أدنى/أقصى صور |
| `src/components/ProductModal.tsx` | تفاصيل + تسعير + معاينة حية | يوجّه للمخصّصات حسب `categoryId` |
| `src/components/admin/AdminDashboard.tsx` | مركز اللوحة + تبويب الإعدادات | رفع البانر إلى Storage؛ حفظ الإعدادات ذاكرة فقط |
| `src/components/admin/OrdersTable.tsx` | جدول الطلبات | بث `onSnapshot` مرتّب بـ createdAt |
| `src/components/admin/OrderModal.tsx` | تحديث حالة الطلب | `items` JSON stringified يُفكّ بـ JSON.parse |
| `src/components/admin/InventoryManager.tsx` | CRUD منتجات + رفع صور | يرفع إلى Storage ثم `addDoc/updateDoc` |
| `src/components/admin/CategoryManager.tsx` | أقسام + خصم/تفعيل | خصم بالجنيه لكل قسم |
| `src/components/admin/OffersManager.tsx` | إنشاء/إزالة عروض | يبدّل price⇄oldPrice على وثيقة المنتج |
| `src/components/admin/AnalyticsDashboard.tsx` | إحصائيات | أرقام ثابتة زائفة (Mock) — لا قراءة من Firestore |
| `src/components/admin/WholesaleManager.tsx` | إدارة عملاء الجملة | عرض/حذف من `wholesale_users` |
| `src/index.css` | الثيم (Tailwind 4 `@theme`) | ذهبي/أسود + ثيمتا رمضان ورأس السنة |
| `.maestro.md` | سياق المشروع لوكيل Maestro | يقرّ: Gemini غير مدموج؛ تتطلب معالجة أخطاء Firebase |
| `metadata.json` / `.env.example` | هوية/قالب AI Studio | `GEMINI_API_KEY` يُحقن وقت التشغيل |
| `vite.config.ts` / `tsconfig.json` | بناء + أنواع | alias `@`=الجذر؛ `noEmit` + `lint=tsc --noEmit` |
