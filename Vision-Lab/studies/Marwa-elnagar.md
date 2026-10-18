# 🏗️ ملخص معماري: Marwa elnagar

> ملف دراسة معمارية — وكيل «فيجن» | الدراسة مكتملة (28 ملفًا مقروءًا)
> 📌 **node_modules محذوفة حاليًا بأمر المالك — تتجدد بأمر `npm install`؛ لا تعتبر غيابها عطلًا.**
> 🔒 خصوصية: يوجد مفتاح (apiKey) داخل `firebase-applet-config.json` — لم تُطبع قيمته عمدًا. ملف `.env` لا يحوي سرًّا حقيقيًا (قيم placeholder فقط).

## 1) الغرض
«CashBox Flow» — تطبيق ويب React لإدارة مالية يومية لمتاجر مروة النجار («ليان ستور» / «مروة فاشون»): تسجيل مبيعات اليوم، حجز حق البضاعة (COGS)، توزيع الصافي آليًا على الديون والأقساط بالأولوية، متابعة «حصالة البضاعة»، وتقارير تصدير. مبني من قالب Google AI Studio ويعمل بالكامل على Firebase (Auth + Firestore) بواجهة عربية RTL ولهجة مصرية.

## 2) نقاط الدخول والتشغيل
- `index.html` → نقطة التحميل (عربي RTL، عنوان CashBox Flow) → `src/main.tsx` → `src/App.tsx`.
- `src/App.tsx` — جذر التوجيه: `AuthProvider` + `BrowserRouter`؛ المسارات: `/login`، `/` (Dashboard)، `/obligations`، `/inventory-vault`، `/daily-entry`، `/history` (الأربعة الأخيرة داخل `<Layout/>`).
- التشغيل: `npm install` (لتجديد node_modules المحذوفة) ← `npm run dev` (Vite منفذ 3000 بعرض 0.0.0.0).
- البناء: `npm run build` → `dist/` (منشور على Firebase Hosting). الفحص/الأنواع: `npm run lint` = `tsc --noEmit`.
- النشر: `firebase deploy --only hosting` (مدوَّن حرفيًا في `New Text Document.txt`).
- أصل المشروع: قالب Google AI Studio (README يشير لـ ai.studio + vite.config يذكر تعطيل HMR في AI Studio).

## 3) الهيكل العام
- SPA متصفح خالص: Vite 6 + React 19 + TypeScript؛ **لا يوجد Back-end مكتوب** — الواجهة تتصل بـ Firebase مباشرة من المتصفح.
- تدفق البنية: `main.tsx` → `App.tsx` (توجيه + AuthProvider) → `Layout.tsx` (قائمة جانبية RTL + وضع ليلي في localStorage) → 5 صفحات في `src/pages/` + سياق مصادقة `src/contexts/AuthContext.tsx` + تهيئة Firebase في `src/firebase.ts`.
- المالك: مشروع Firebase `canvas-abacus-474519-b5`، وقاعدة Firestore مسماة `ai-studio-a03ab129-814a-4534-9bc4-37d6af04ed03` (انظر `firebase.json` و`.firebaserc`).
- يوجد `dist/` مبني مسبقًا + كاش نشر `.firebase/` — تخطّيها من القراءة (خارج نطاق الدراسة عمدًا).

## 4) الوحدات الرئيسية
| الوحدة | الملف | الدور |
|---|---|---|
| التهيئة | `src/main.tsx` | تركيب React على #root بـ StrictMode |
| التوجيه/البنية | `src/App.tsx` | تعريف المسارات + AuthProvider |
| المصادقة | `src/contexts/AuthContext.tsx` | onAuthStateChanged + قراءة ملف `users/{uid}` لحظيًا (onSnapshot)؛ فرض دور Owner لأسماء محددة صلبًا بالكود (المدير/محمود/محمود النجار) |
| التخطيط | `src/components/Layout.tsx` | Sidebar يمين RTL، 5 عناصر تنقل بأسماء مصرية عامية، وضع داكن (localStorage)، زر خروج |
| الدخول | `src/pages/Login.tsx` | دخول/تسجيل باسم + كلمة سر؛ يحوّل الاسم إلى «إيميل وهمي» hex@cashbox.local؛ إنشاء وثيقة `users` عند التسجيل |
| لوحة القيادة | `src/pages/Dashboard.tsx` | 4 مؤشرات KPI + نسب إنجاز ديون قصيرة/طويلة/مجمدة + جداول + تصدير PNG (html2canvas) وCSV؛ يستمع live لـ daily_entries و obligations |
| القيد اليومي | `src/pages/DailyEntry.tsx` | «تقفيلة النهاردة»: صافي = إجمالي − COGS% − 5% أمان؛ توزيع شلالي آلي (priority ثم carry_over) أو يدوي؛ كتابة دفعة واحدة (batch): daily_entries + allocations + تحديث obligations |
| الالتزامات | `src/pages/Obligations.tsx` | إضافة/حذف/تجميد الديون؛ حذف للمدير (Owner) فقط |
| الحصالة | `src/pages/InventoryVault.tsx` | رصيد محسوب جمعًا من كل `vault_transactions` (In/Out) + سحب للمخزن |
| الأرشيف | `src/pages/History.tsx` | سجل القيود اليومية مع بحث بالتاريخ وتوسيع التفاصيل |
| أدوات | `src/lib/utils.ts` | دالة `cn` فقط (clsx + tailwind-merge) |

## 5) المكتبات (من package.json)
- الاسم `react-example` (اسم قالب AI Studio) — خاص، 0.0.0، type:module.
- سكربتات: `dev` (vite --port=3000 --host=0.0.0.0)، `build`، `preview`، `clean`، `lint` (tsc --noEmit).
- أساس الواجهة: react 19 + react-dom 19 + react-router-dom 7.
- الخدمة: `firebase` 12 (auth + firestore).
- جمالية/UX: tailwindcss 4 (عبر @tailwindcss/vite) + lucide-react + motion + clsx + tailwind-merge.
- نماذج/بيانات: react-hook-form + @hookform/resolvers + zod (مثبّتة لكن غير مستخدمة في الصفحات الحالية)، recharts (مثبتة، لا يوجد رسم فعلي في الكود المقروء)، date-fns، html2canvas.
- بقايا قالب: @google/genai (Gemini SDK — لا import له في src)، express + @types/express + dotenv (لا خادم في المشروع)، tsx (لتشغيل سكربتات Node مثل check_data.js).
- ملاحظة: vite مكرر في dependencies و devDependencies (يعمل لكنه خارج العُرف).

## 6) مخازن البيانات
- **Firestore** (قاعدة مسماة، لا SQLite ولا ملفات محلية):
  - `users/{uid}`: uid, name, role (Owner/Partner), createdAt.
  - `obligations/{id}`: name, total_amount, paid_amount, daily_target, priority, category (Short/Long-term), status (Active/Frozen/Paused/Completed), term_months, startDate, carry_over, createdBy…
  - `daily_entries/{id}`: date, store_name, gross_revenue, cogs_percentage, cogs_amount, safe_buffer_amount (5%), net_revenue, sweep_amount (الفايض), createdBy, createdAt.
  - `allocations/{id}`: date, daily_entry_id, obligation_id, amount_allocated, type (Auto/Manual).
  - `vault_transactions/{id}`: type (In/Out), amount, description, createdAt — الرصيد يُحسب جمعًا من كل الحركات في العميل (بدون وثيقة رصيد مركزية).
- **localStorage**: مفتاح `theme` (وضع داكن/فاتح).
- **استضافة**: Firebase Hosting من مجلد `dist` مع إعادة كتابة SPA (firebase.json) وكاش `.firebase/`.
- تكوين الاتصال: `firebase-applet-config.json` (projectId/appId/apiKey… — يوجد مفتاح apiKey في هذا الملف، لم تُطبع قيمته) + `firebase-blueprint.json` (مخطط الكيانات الأصلي من AI Studio — يسبق بعض الحقول الحالية).

## 7) التكاملات
1. **Firebase Auth** — دخول Email/Password بأسلوب مبتكر: اسم المستخدم يُشفَّر hex ويصبح `…@cashbox.local` (Login.tsx:22-29)؛ تذكّر الجلسة browserLocal/Session.
2. **Firestore** — الاستماع اللحظي onSnapshot في Dashboard/Obligations/InventoryVault/History، وقراءة أحادية في DailyEntry.
3. **Firebase Hosting** — نشر dist (أمر في New Text Document.txt)؛ .firebaserc = مشروع `canvas-abacus-474519-b5`.
4. **Google AI Studio** — أصل المشروع (README + vite.config + metadata.json + .env.example لمفتاح Gemini).
5. **Gemini (`@google/genai` + GEMINI_API_KEY عبر vite define)** — البنية جاهزة لكن لا استخدام فعلي في كود الواجهة.
6. **html2canvas** — تصدير «تقرير المركز المالي» كصورة PNG، وتصدير CSV (بـ BOM للعربية).
7. لا تكاملات دفع ولا REST خارجي؛ Express/dotenv بقايا قالب غير مستخدمة.

## 8) تقييم الصحة (بدليل)
**الصحة العامة: 🟡 يعمل وظيفيًا لكن به أعطال موثقة وقواعد أمان غير متطابقة.**

- 🔴 **خلل تجميع/تشغيل: `logout` غير موجود في سياق المصادقة** — `Layout.tsx:19` يستخرج `logout` من `useAuth()` بينما عقد السياق `AuthContext.tsx:14-18` يعرّف فقط currentUser/userProfile/loading → خطأ TypeScript (يفشل `npm run lint`) وزر «اخرج بره» سيرمي استثناء وقت التشغيل. (Login يتسرب للصفحات دون حماية مسارات أيضًا: لا يوجد Route guard للمسارات المحمية غير الـ Layout.)
- 🔴 **انهيار محتمل عند فتح سجل في الأرشيف** — `History.tsx:166,172` يقرأ `entry.allocations.map/length` لكن الاستعلام (History.tsx:63-75) لا يجلبها أبدًا؛ المكوّن المكتوب لجلبها عند الطلب `AllocationRows` (History.tsx:26-55) **غير مستخدم** (كود ميت) → TypeError عند أول توسيع.
- 🔴 **قواعد Firestore لا تطابق ما تكتبه الواجهة** (لو نُشرت القواعد الحالية ستُرفض عمليات):
  - إنشاء دين: الواجهة تكتب category/term_months/startDate/createdBy (Obligations.tsx:62-74) بينما `isValidObligation` يشترط `monthly_installments` ويمنع أي حقل آخر عبر hasOnly (firestore.rules:34-46) → رفض.
  - التجميد: الواجهة تحفظ status='Frozen' (Obligations.tsx:83) غير مدرج في قائمة القواعد (firestore.rules:41) → رفض.
  - الحصالة: الواجهة تكتب type/description (InventoryVault.tsx:57-62) بينما القاعدة تشترط reason/entityName/createdBy (firestore.rules:71-78) → رفض كل سحب.
  - تسجيل «محمود النجار» كـ Owner: القاعدة تسمح Owner فقط لاسم 'المدير' أو 'محمود' (firestore.rules:86-87) بينما Login يعطيه Owner (Login.tsx:54) → رفض إنشاء الوثيقة.
- 🟡 **هشاشة تصميم**: الأدوار تُفرض بالاسم في كود العميل (AuthContext.tsx:44-47) — تجاوز أمني بالاسم النصي؛ الرصيد يُحسب من كل حركات الحصالة بلا limit (ينمو مع البيانات)؛ رسم الجداول في Firestore بلا فهارس مذكورة؛ لا اختبارات ولا CI.
- 🟡 **قيمه زائدة**: express/dotenv/@google/genai/zod/recharts/react-hook-form مثبتة بلا استخدام فعلي في الكود — حمولة تثبيت زائدة؛ package name عام (`react-example`).
- 🟢 **نقاط قوة**: فصل واضح pages/contexts/components؛ عمليات مالية ذرية عبر writeBatch (DailyEntry.tsx:98-144)؛ صيغة توزيع مركزية (COGS% + 5% أمان + شلال أولوية مع carry_over)؛ قواعد Firestore فيها تحقق صارم من البنية والدور؛ RTL + وضع داكن + تجاوب كامل.
- 🔒 **الخصوصية**: يوجد مفتاح Firebase apiKey داخل `firebase-applet-config.json` (مفتاح ويب Firebase علني بطبيعته، وذكرناه دون قيمته). ملف `.env` يحوي placeholder فقط (لا سر حقيقي). `.gitignore` يستبعد .env* — سليم.

## 9) خريطة دخول للتطوير
1. **أول إصلاح ممكن**: أضف `logout` إلى AuthContextType وقيمته (`signOut(auth)`) في AuthContext.tsx:14-18/82 — يصلح lint وزر الخروج معًا.
2. **ثانيًا**: إما تفعيل `AllocationRows` داخل توسيع History أو إزالة `entry.allocations` من JSX (History.tsx:160-176).
3. **مزامنة الأمان**: حدّث `firestore.rules` لقبول الحقول الفعلية (category/term_months/startDate/createdBy في obligations؛ type/description في vault_transactions؛ status 'Frozen'؛ Owner لاسم 'محمود النجار') ثم `firebase deploy --only firestore` — أو أعد صياغة الكتابات لتفق المخطط في firebase-blueprint.json.
4. **إضافة صفحة جديدة**: أنشئ ملفًا في `src/pages/` + Route في `App.tsx` + عنصر في مصفوفة `navigation` بـ `Layout.tsx:45-51` (الأسماء والاتجاه RTL).
5. **منطق المال** (أهم نقطة امتداد): كل الحساب في `DailyEntry.tsx:52-86` — صافي = إجمالي − COGS% − 5% أمان؛ التوزيع الشلالي يتبع priority ثم يحمل العجز في carry_over؛ الفايض sweep_amount.
6. **النشر**: `npm run build` ثم `firebase deploy --only hosting` (الاستضافة من dist، لا كاش) — بيئة التطوير: `npm install` ثم `npm run dev` على منفذ 3000.
7. **فحص الأنواع قبل أي تعديل**: `npm run lint` (tsc --noEmit) — سيكشف خلل logout فورًا.

## 10) فهرس الملفات المهمة
| الملف | دوره | ما يلزم معرفته |
|---|---|---|
| `package.json` | بيانات المشروع والسكربتات والمكتبات | `dev` منفذ 3000؛ `lint` = tsc --noEmit؛ مكتبات كثيرة غير مستخدمة؛ vite مكرر |
| `README.md` | تعليمات تشغيل قالب AI Studio | `npm install` ثم `npm run dev`؛ يذكر GEMINI_API_KEY في .env.local |
| `index.html` | نقطة تحميل الواجهة | عربي RTL، عنوان CashBox Flow، root div |
| `src/main.tsx` | تهيئة React | StrictMode + ملف CSS |
| `src/App.tsx` | جذر التوجيه | 6 مسارات؛ AuthProvider يغلف الكل؛ لا حماية مسارات إضافية |
| `src/firebase.ts` | تهيئة Firebase | Auth + Firestore (قاعدة مسماة) من firebase-applet-config.json |
| `src/contexts/AuthContext.tsx` | المصادقة وملف المستخدم | أدوار Owner/Partner؛ فرض دور بالأسماء؛ **ينقصه logout** |
| `src/components/Layout.tsx` | الهيكل والتنقل | navigation يجب أن يطابق مسارات App؛ وضع داكن؛ **يستخدم logout غير المعرّف** |
| `src/pages/Login.tsx` | الدخول/التسجيل | إيميل وهمي hex@cashbox.local؛ إنشاء users doc؛ تذكّر الجلسة |
| `src/pages/Dashboard.tsx` | KPIs وتقارير | onSnapshot على daily_entries(limit 100) و obligations؛ تصدير PNG/CSV |
| `src/pages/DailyEntry.tsx` | قفل اليوم وتوزيع الفلوس | قلب المنطق المالي؛ batch ذرية؛ auto/manual |
| `src/pages/Obligations.tsx` | إدارة الديون | حذف للـ Owner فقط؛ تجميد/تنشيط؛ الحقول هنا لا تطابق قواعد Firestore |
| `src/pages/InventoryVault.tsx` | حصالة البضاعة | رصيد محسوب من كل vault_transactions؛ **كتابته يرفضها firestore.rules** |
| `src/pages/History.tsx` | أرشيف اليوميات | **entry.allocations غير موجودة → انهيار عند التوسيع**؛ AllocationRows كود ميت |
| `src/lib/utils.ts` | أداة تنسيق CSS | cn() فقط |
| `src/index.css` | أساس Tailwind | لم يُقرأ بالتفصيل (تنسيق فقط) |
| `firebase-applet-config.json` | تكوين تطبيق Firebase | projectId canvas-abacus-474519-b5؛ **يوجد apiKey (قيمته لم تُطبع)** |
| `firebase.json` | إعداد Firebase CLI | استضافة dist + SPA rewrites + قاعدة Firestore المسماة |
| `.firebaserc` | المشروع الافتراضي | canvas-abacus-474519-b5 |
| `firestore.rules` | أمان القاعدة | **غير متطابقة مع كتابات الواجهة (4 فروقات موثقة)** |
| `firebase-blueprint.json` | مخطط كيانات Firestore | إصدار أبكر: يذكر monthly_installments ولا يذكر category/الحصالة |
| `.firebaserc` / `metadata.json` | تعريفات | المشروع / metadata فارغ (قالب) |
| `vite.config.ts` | إعداد البناء | Tailwind 4 + define لـ GEMINI_API_KEY + alias @ |
| `tsconfig.json` | إعداد TS | ES2022، bundler، noEmit، paths @/* |
| `.env` / `.env.example` | متغيرات البيئة | قيم placeholder فقط (لا سر فعلي)؛ .gitignore يمنع رفع .env* |
| `check_data.js` | سكربت فحص (UTF-16) | يقرأ obligations ويطبعها؛ يشير لمتغيرات VITE_FIREBASE_* غير معرّفة |
| `New Text Document.txt` | مذكرة أوامر | يحوي أمر النشر: firebase deploy --only hosting |
| `firebase-blueprint.json` | مخطط البيانات | مرجع التحقق عند مزامنة القواعد |
| `.gitignore` | استثناءات Git | يتجاهل node_modules/dist/.env* |
| `dist/`, `.firebase/`, `package-lock.json` | مخرجات بناء/قفل | تخُطّيتها عمدًا حسب قواعد الدراسة |

---
*منهجية: قراءة فقط — تخطّي node_modules/.git/dist/build (استُبعدت من التحليل). node_modules محذوفة وتتجدد بـ `npm install`. أُنجزت الدراسة على 3 دفعات مع تحديث هذا الملف بعد كل دفعة.*
