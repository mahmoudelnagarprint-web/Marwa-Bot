# 🏗️ ملخص معماري: 2026 (مساحة عمل المالك)

> دراسة معمارية لمساحة العمل `G:\ai\2026` — وكيل مذاكرة معمارية تحت إدارة «فيجن».
> ✅ حالة الملف: مكتمل — 12/12 ملفًا من الميزانية مقروء، وجرد التوب-ليفل كامل (13 مجلدًا).

## الغرض

`G:\ai\2026` هي **مساحة العمل السنوية العامة للمالك** (2026) — ليست مشروعًا واحدًا بل صندوق عمل سنوي يجمع أربع حزم من العمل: (1) **منتجات تجارية** لورشة «النجار برنت» ومتاجر العائلة (أدوات قص ليزر، إضافة فوتوشوب، ريل ترويجي)، (2) **منصات تواصل اجتماعي** (إضافة كروم لإدارة منشورات فيسبوك، AutoPoster، مجدول بايثون)، (3) **بنية تحتية للذكاء الاصطناعي** (ذاكرة DSH الدائمة، إصلاح tool-calling لـ vLLM، مساعد شخصي بذاكرة معرفية، جسر لوحة مفاتيح PC↔أندرويد)، (4) **تطبيقات أندرويد** من Google AI Studio. الدور العام: **محطة عمل متعددة المشاريع** يتكامل فيها جانب الإنتاج التجاري مع تجارب AI وبنية DSH.

## الهيكل العام (أهم الفروع)

جرد التوب-ليفل (13 مجلدًا، لا ملفات سائبة) مقسمًا بحسب الوظيفة:

| المجلد | الدور | التقنية | الحزمة |
|---|---|---|---|
| `facebook share` | **المشروع المحوري**: إضافة كروم لفيسبوك + qwen-tool-fix + dsh-memory-agent-preset | JS/Python | AI/تواصل |
| `facebook` | مجدول منشورات فيسبوك مستقل ببايثون (main.py 17KB + scheduler.db + إعداد registry) | Python/SQLite | تواصل |
| `el-naggar-brain` | **«النجار برين»**: مساعد AI شخصي ذاتي بذاكرة معرفية + APK + HUD + hotkeys | Python/PySide6/SQLite-vec | AI |
| `Ai ME keybord` | «Smart Workspace & Mobile Bridge Hub»: جسر PC↔أندرويد + لوحة مفاتيح ذكية عربية | Python/FastAPI/PyQt6/Kotlin | AI/أدوات |
| `استوديو-القص-والتصميم-الذكي` | تطبيق ويب AI Studio للاستوديو الذكي للقص والتصميم (server.ts + Vite) | TS/Web/Gemini | تجاري |
| `laser-box-designer` | «مولد صناديق الليزر التفاعلي الذكي»: تصميم ومحاكاة 3D للصناديق — 4 ملفات ثابتة فقط | JS/Three.js | تجاري |
| `drivedeck` | تطبيق أندرويد من AI Studio + مجلد فرعي `layan-erp---staff-edition` | Kotlin/Gradle/Gemini | أندرويد |
| `smart-ai-gallery` | معرض صور ذكي (أندرويد) — APK مبني (146MB) + web-preview | Kotlin/Gradle/Gemini | أندرويد |
| `auto poster` | «AutoPoster Pro»: تسويق اجتماعي وأتمتة AI — بنية client/server | Node/JS | تواصل |
| `Ps grad` | «Smart Gradient & Palette Engine»: إضافة فوتوشوب UXP بمحرك ألوان OKLab/OKLCH | UXP/JS | تجاري |
| `promo` | ريل ترويجي «النجار برنت» 2026 (mp4 11.4MB) + filter_complex لـ ffmpeg | ميديا | تجاري |
| `_backup_v1.0.0` | نسخة الإضافة كروم القديمة v1.0.0 (المصدر محل التحليل الأمني) | JS | احتياط |
| `scrcpy-master` | مصدر scrcpy المفتوح (انعكاس شاشة أندرويد) — مجلد متداخل بنفس الاسم | C (upstream) | أدوات |

## المشاريع الفرعية

### 1) `facebook share` — الحزمة المحورية (4 كيانات مترابطة)

**أ. إضافة كروم `Facebook Smart Curator & Reposter` v2.0.0** (`manifest.json` — MV3):
- الغرض: سحب وتعديل وإعادة نشر منشورات فيسبوك (صور وفيديو) مع Graph API للصفحات. أذونات: storage/notifications/alarms/scripting/contextMenus/activeTab + هوست لفيسبوك وfbcdn وgraph(-video) — أُضيفت في v2 بعد أن كانت ناقصة في v1.
- بنية: `background.js` (Service Worker: Graph API، توكن، قوائم سياق) + `content.js` (71KB — المحرك الأكبر: كشف المنشورات، حقن الأزرار، نافذة التحرير) + `options.html/js` + اختصار `Alt+Shift+R` لإعادة نشر المنشور الظاهر.
- `configure_free_model.py` + `pull_free_models.py`: سكربتات لضبط/سحب موديلات مجانية للإضافة (غير مقروءة ضمن الميزانية). `test-button-engine.html` صفحة اختبار لمحرك الأزرار.

**ب. `qwen-tool-fix` — إصلاح دورة Tool Calling بين Qwen المحلي (vLLM) وDSH وdsh-memory:**
- **السبب الجذري** (مقاس لا مخمَّن): خادم vLLM 0.30.0 يخدم `Qwen2.5-Coder-14B-Instruct-AWQ` ولا يحوّل tool call إلى حقل `tool_calls` منظَّم — الموديل يكتب النداء نصًا (`<tools>{json}</tools>` أو ```json``` مجوّل) داخل `message.content` مع `finish_reason="stop"`، فلا ينفّذه DSH. ليس عيبًا في DSH ولا الـ preset ولا تسجيل الأدوات ولا حجم السياق (العطل يتكرر عند 173 توكن؛ max_model_len=32768 مطابق لما يعلنه DSH).
- **الإصلاح**: parser plugin لـ vLLM باسم `qwen_coder_json` (`vllm_qwen_coder_tool_parser.py`) يتعرّف على 4 صيغ، يدعم streaming (إلزامي لأن DSH يمرر `stream:true`)، ويطبق قواعد أمان (JSON صحيح + اسم ضمن أدوات الطلب، ورفض القوائم الجزئية كاملة، وعدم ابتلاع النص غير الأداتي). يُشغَّل بـ `--enable-auto-tool-choice --tool-call-parser qwen_coder_json --tool-parser-plugin <path>`.
- **الاختبارات**: 27/27 وحدة (`test_vllm_qwen_coder_tool_parser.py` بلا vLLM — تغطي الصيغ الأربع والدفق بقطع 1–4 أحرف ومنع التسريب)، و`check-qwen-tool-calling.mjs` قبول حيّ (1/6 قبل → 6/6 بعد)، و`capture-corpus.mjs` يلتقط الأدلة الخام في `corpus/`.
- **ما لم يُغيَّر**: dsh-memory، الـ preset، مسار DeepSeek — سليم كله. تفسير فشل البدائل: `hermes` يشترط وسم `<tool_call>` الذي لا يُخرجه موديل Coder (فشل صامت)، و`xlam` يشترط JSON array بينما الموديل يُخرج object.
- **ملاحظة أمنية موثّقة**: خادم Kaggle عبر quick tunnel **مفتوح بلا مصادقة** — يُنصح بـ `--api-key` مع `apiKeyEnv: KAGGLE_SERVER_API_KEY` (لا تُطبع المفاتيح أبدًا).
- الرجوع: حذف الوسائط الثلاث من أمر vLLM يعيد السلوك القديم بالكامل.

**ج. `dsh-memory-agent-preset` — Agent Preset لـ DSH بذاكرة خارجية دائمة:**
- تعريف `@deepseek-ai/dsh-agent-preset` (id: `memory`, name: `dsh-memory`): أبناء الـ preset العشرون **منقولون حرفيًا** من الـ preset الرسمي `cordis`، والتغيير الوحيد `persona.config.prefix` بسياسة ذاكرة من 14 قاعدة (بحث استباقي → حفظ انتقائي → عدم اختراع → خصوصية → تسلسل Search/Analyze/Task/Decide/Write).
- المعمارية المفروضة: `Model → dsh-memory tools → External Persistent Memory` (وليس ذاكرة داخلية للموديل).
- التثبيت الفعلي في `C:\Users\mahmo\.dsh\profiles\desktop\cordis.patch.yml` (سطور 101–292)؛ `preset-memory.patch.yml` نسخة قابلة للنقل لprofiles أخرى؛ `verify.mjs` = **23/23 فحصًا ناجحًا** (مطابقة الأبناء 20=20، عقد الـ preset، عدم اختراع أدوات/parameters، متغيرات prompt مسجّلة فقط `{{model}}`/`{{cwd}}`).
- تفعيله يتطلب إعادة تشغيل DSH (التعريفات تُحمَّل عند البدء). المواصفة صُححت لتطابق schemas الفعلية: `scope` (global/workspace/project) بدل `namespace`، لا scope للجلسة، `memory_add` يرفض الأسرار تلقائيًا (`allowSecret=false`)، والملخص محقون تلقائيًا فلا لزوم لـ `memory_read` كل دور. `scopedMemory` مفعّل منذ 2026-10-03.
- **ممنوع إعادة تركيب bundle dsh-memory داخل الـ preset** — مثبَّت على مستوى الـ profile (تسجيل مزدوج). الـ presets لا تدعم الوراثة (نسخ حرفي من cordis).

**د. وثيقة `تحليل-الإضافة-وخطة-التطوير.md` (245 سطرًا):** تحليل معماري للإضافة v1.0.0 + تنفيذ v2.0.0. أبرز ما وثّق:
- ثغرة **حرجة**: توكن وصول حقيقي مكتوب داخل `background.js` (v1) ينسخ عبر `storage.sync`، ودالة `extractAndSaveImmichToken` (بقايا مشروع Immich) تمسح localStorage/sessionStorage لفيسبوك وتخزن ما تجده — سلوك رفض فوري من Chrome Web Store.
- مشكلة بنيوية: **ثلاثة أنظمة حقن متوازية** في `content.js` (أزرار بجوار Share + عائمة fixed + عائمة بإحداثيات + زر ثابت) — سبب تكدس الأزرار فوق الكومنتات؛ الزر يظهر بجوار أزرار التعليقات لأن `findShareActionBarFromButton` يصعد حتى يجد شريط Like/Comment/Share.
- 28 نقطة ضعف موثّقة (Regex بلا escape، دالة معرفة مرتين، لا مسار رفع فعلي للفيديو — اعتماد على file_url يفشل مع fbcdn الموقعة، blob: URLs، تسريب مستمعين mousemove/mouseup، data URLs تضخم 33%، مسح React بلا حد) + قسم أداء (تعقيد شبه تربيعي في findActionBar).

### 2) `el-naggar-brain` — «النجار برين» (أضخم مشروع)

مساعد AI شخصي **ذاتي** بمعمارية ذاكرة معرفية فوق مزودي LLM مجانيين (SambaNova/Groq/Gemini/Mistral) — فلسفته: «موديلات الـ LLM سلعة زائلة؛ الذاكرة أصل دائم».
- **التقنية**: Python 3.10+، واجهة PySide6 سطح مكتب، SQLite + إضافة sqlite-vec (وضع WAL) + تضمينات محلية BAAI bge-m3 متعددة اللغات.
- **المعمارية**: 11 مرحلة تنفيذ كلها ✅ مكتملة (خدمة تطبيق بـ feature-flag، أوامر ذاكرة صريحة بلا LLM، Context Budget Builder بتقليم تكيفي، Provider Router بـ circuit breaker لـ 429 وفشل التبديل، عامل تضمين خلفي، التقاط حقائق مؤجل وتجميع، لوحة ذاكرة تفاعلية، كشف المشاريع والتبديل السياقي، harness تحقق حي).
- **الجودة**: 160 اختبارًا آليًا في 13 حزمة (دقة anti-overfitting 100% — 15/15)، 5 قرارات معمارية ADR موثقة (`docs/adr/`: bge-m3، feature-flag/adapter، sqlite-vec/WAL، حصانة الذاكرة من محرك الانحلال البيولوجي، circuit breaker ×3)، دليل معماري شامل `ARCHITECTURE.md` + `MASTER_SPEC.md`.
- **مكونات إضافية على الجذر**: brain_gateway، bot، hotkeys، APK جاهز، HUD (launch_silent)، package.json + server.ts + vite (واجهة ويب)، `.env` حقيقي (مُخفي — لا يُطبع).
- اختصارات التشغيل: `python main.py` للواجهة، `scripts/live_llm_validation.py --mode interactive|smoke|stress` للتحقق الحي.

### 3) `Ai ME keybord` — Smart Workspace & Mobile Bridge Hub

منظومة موحدة تربط Windows PC بأندرويد عبر Wi-Fi/LAN (WebSocket):
- **نواة الـ PC**: FastAPI + جسر WebSocket، طبقة SQLite، محرك حافظة Win32، متتبع caret ورفيق حي، مبدّل تخطيط لوحة المفاتيح، بوابة AI متوافقة OpenAI، واجهة PyQt6 glassmorphic، محرك قاموس متعلَّم (عربي/إنجليزي).
- **تطبيق أندرويد**: Kotlin + Coroutines، OCR عربي/لاتيني بـ ML Kit، كتابة حية بلوحة الجوال، مُرسل ميديا مجزأ، مستمع إشعارات النظام، ماسح QR/كاميرا، Find My Phone + flashlight.
- **التوثيق**: ARCHITECTURE.md + PROTOCOL.md + PERMISSIONS.md + DEVELOPMENT.md + MASTER_SPECIFICATION.md + FULL_IMPLEMENTATION_AUDIT.md.
- **ملاحظات الصحة**: مجلدات استرجاع `.backup_pre_recovery_20261014` و`.backup_phase20` + عشرات سكربتات `_tmp_*.py` للإصلاحات المتكررة على المعجم (اقتراحات الكلمات/التطبيع) تدل على دورات إصلاح كثيرة؛ `validate_lexicon.py` + `validation_results.txt` للتحقق من المعجم؛ `tools/health_check.py` لفحص البيئة. `.env` حقيقي (مُخفي).

### 4) `استوديو-القص-والتصميم-الذكي`

تطبيق ويب مولَّد من **Google AI Studio** (README قالب AI Studio — app id `72395d5a…`): Vite + TypeScript + `server.ts` (12.6KB)، يعمل بـ `npm run dev` مع `GEMINI_API_KEY` في `.env.local` (لديه `.env.example` آمن). ملفا قفل: bun.lock وpackage-lock معًا (بيئتا تثبيت). مجلدات: assets/dist/node_modules/src. التفاصيل الوظيفية الداخلية خارج الميزانية.

### 5) `drivedeck` (ومع `layan-erp---staff-edition`)

تطبيق أندرويد من **AI Studio** (نفس قالب README — app id `9b8c2fdf…`): مشروع Gradle/Kotlin يُفتح من Android Studio، `GEMINI_API_KEY` في `.env`. يحوي مجلدًا فرعيًا مستقلًا `layan-erp---staff-edition` (نسخة موظفين من ERP «ليان» — يخص متجر ليان ستور) + مجلد assets وbuild جاهز.

### 6) `smart-ai-gallery`

معرض صور ذكي (أندرويد) من **AI Studio** (نفس القالب — app id `d122181e…`) — يطابق مشروع «تطبيق أندرويد لمعرض صور بتصنيف محلي» في سجل مشاريع المالك. APK مبني موجود (`smart-ai-gallery-fixed.apk` — 146MB!) + مجلد `web-preview` + `.env` حقيقي صغير (مُخفي).

### 7) `auto poster` — AutoPoster Pro

«Next-Gen Social Marketing & AI Automation»: monorepo بجذر خفيف — `npm --prefix server` و`npm --prefix client` (server + client + scripts)، تشغيل عبر `تشغيل_البرنامج.bat`/`start.bat`. مستودع git. تفاصيل العميل/الخادم الداخلية خارج الميزانية.

### 8) `Ps grad` — Smart Gradient & Palette Engine (فوتوشوب UXP)

إضافة Adobe Photoshop (2023 → 2026+) بمعايير UXP v5 وتصميم مسطح (متسق مع قاعدة عمل المالك «التصاميم مسطحة»):
- **المحرك**: رياضيات ألوان `OKLab/OKLCH/HSL/RGB` (تدرجات بلا مناطق رمادية موحلة)، مورفينج تطبيقي واعٍ بالسياق (نص → Gradient Overlay قابل للتعديل؛ شكل متجه → تعديل الملء؛ مقفل/ذكي/بكسل → طبقة Gradient Fill بـ Clipping Mask)، ماسح «DNA» لألوان الكانفس (Color Quantization)، مزامنة حية مع قطارة الفوتوشوب.
- **التخزين**: مفضلة محلية + طبقة مزامنة سحابية اختيارية (Supabase/Firebase/REST).
- **التوزيع**: حزمة `.CCX` جاهزة (تثبيت بنقرة) + `package-ccx.js` لإعادة التجميع + `npm test` للفحص السريع. بنية js/ موثقة (color-engine، ps-engine، storage، ui).

### 9) `laser-box-designer` — مولد صناديق الليزر التفاعلي الذكي

أداة ويب عربية (RTL) بملفات ثابتة 4 فقط — بلا بناء ولا node_modules:
- Three.js 0.128 + OrbitControls (من CDN unpkg) لمحاكاة ثلاثية الأبعاد، و`box-generator.js` (29.9KB) + `app.js` (30.6KB) للمنطق.
- الميزات (من الواجهة): صناديق مغلق/مفتوح/مفصلي، غطاء سحاب، تقسيمات شبكية داخلية، طبقات متعددة، زخارف تفريغية، وحدات mm/inch، حساب أبعاد خارجي/داخلي، واستيراد بالذكاء الاصطناعي. أداة إنتاج مباشرة لورشة القص بالليزر.

### 10) `facebook` (المجدول المستقل)

أداة بايثون منفصلة عن الحزمة الكبرى: `main.py` (17KB) + `database_manager.py` + `scheduler.db` (SQLite 12KB) + `setup_registry.py` + `fix_facebook_menu.reg` — مجدول/مدير منشورات يعمل من سطح المكتب مع تسجيل Windows.

### 11) مشاريع مساندة

- **`promo`**: ريل ترويجي نهائي `promo_reel_najjarprint_2026.mp4` (11.4MB) + `filter_complex.txt` — أثر إنتاج بالـ ffmpeg (تركيب مقاطع).
- **`scrcpy-master`**: نسخة vendored من مصدر scrcpy المفتوح (انعكاس شاشة أندرويد على PC) — مسند عملي لجسر «Ai ME keybord» وأعمال الأندرويد؛ upstream لا يُعدَّل.
- **`_backup_v1.0.0`**: النسخة القديمة الكاملة للإضافة كروم (background 19.5KB + content 50.4KB مقابل 71.6KB الحالي) — أساس المقارنة مع v2.0.0.

## التكاملات

- **سلسلة الأدوات الموثّقة** (qwen-tool-fix): `User → Qwen → (vLLM + qwen_coder_json) → OpenAI tool_calls → pi-ai adapter → DSH tool execution → dsh-memory → tool result → Qwen → إجابة طبيعية → User`. المنفذ الوحيد القابل للتطبيع في DSH: حدث `llm/stream` (waterfall) في `dsh-llm/lib/index.js:2371` (موضَّح لكنه **لم يُنفَّذ** — قرار مقصود).
- **الـ preset ↔ profile DSH**: يعتمد على bundle `@dsh-external/dsh-memory` المثبَّت على مستوى الـ profile `desktop` (لا يعيد تثبيته)؛ التثبيت عبر `cordis.patch.yml`؛ نقل لprofiles أخرى بـ `preset-memory.patch.yml`.
- **ثلاثي AI Studio** (استوديو-القص / drivedeck / smart-ai-gallery): جميعها بنمط AI Studio القياسي مع `GEMINI_API_KEY` (.env/.env.local) — منصة واحدة، أنماط تشغيل متطابقة.
- **النجار برين ↔ مزودو LLM مجانيون**: SambaNova/Groq/Gemini/Mistral عبر Provider Router + circuit breaker، والذاكرة على sqlite-vec محليًا.
- **Ai ME keybord ↔ أندرويد**: WebSocket عبر LAN (بروتوكول موثق في PROTOCOL.md) — حافظة، إشعارات، ميديا، كتابة حية.
- **إضافة كروم ↔ Graph API فيسبوك** (صفحات + graph-video)؛ وAutoPoster + مجدول `facebook` كطبقة نشر موازية.
- **Ps grad ↔ Photoshop UXP** (batchPlay/executeAsModal) + مزامنة سحابية اختيارية (Supabase/Firebase).
- **promo ↔ ffmpeg**: filter_complex لتجميع الريل.
- **عكس تكاملٍ أُزيل**: `extractAndSaveImmichToken` في الإضافة v1 كان يسرق توكنات جلسة فيسبوك باسم «Immich» — حذف في v2.

## تقييم الصحة

| المشروع | الصحة | الدليل |
|---|---|---|
| qwen-tool-fix | 🟢 ممتاز | 27/27 وحدة + قبول حي 6/6 بعد الإصلاح + أدلة corpus + خطة رجوع واضحة |
| dsh-memory-agent-preset | 🟢 ممتاز | verify.mjs 23/23؛ التفعيل يتطلب إعادة تشغيل DSH (قيد منصة، ليس عيب تعريف) |
| إضافة كروم v2.0.0 | 🟡 جيد مع ملاحظة | أعيدت معماريتها بعد 28 نقطة ضعف موثقة؛ لا اختبارات آلية بعد (نقطة 28 من التحليل) |
| el-naggar-brain | 🟢 ممتاز | 160 اختبارًا/13 حزمة، 11 مرحلة مكتملة، 5 ADRs، harness تحقق حي |
| Ai ME keybord | 🟡 متوسط | توثيق ممتاز لكن عشرات `_tmp_*.py` ومجلد استرجاع 2026-10-14 يدلان على دورات إصلاح متكررة لم تستقر |
| استوديو-القص / drivedeck / smart-ai-gallery | 🟡 جيدة/مسودة | مولَّدة من AI Studio بقوالبها؛ دريفديك يحتضن مشروع ERP فرعيًا؛ معرض الصور له APK نهائي مبني |
| auto poster | 🟠 ضحل التوثيق | جذر خفيف بلا README؛ البنية في client/server (لم تُفحص ضمن الميزانية) |
| laser-box-designer / Ps grad / promo | 🟢 سليم | أدوات ثابتة صغيرة مكتملة الوظيفة؛ Ps grad موثق ومبني CCX |
| أمني عام | 🔴 ينتبه له | (1) endpoint الـ vLLM بلا مصادقة؛ (2) توكن حقيقي كان مصدرًا في v1 (أُصلح في v2)؛ (3) ملفات `.env` حقيقية في el-naggar-brain وAi ME keybord وsmart-ai-gallery — **لم تُطبع محتوياتها** |

## خريطة دخول

- **فهم عطل tool-calling وتشغيل الإصلاح**: `facebook share\qwen-tool-fix\README.md` (تشخيص كامل + أوامر vLLM + الاختبارات).
- **تفعيل الذاكرة الدائمة في DSH**: `facebook share\dsh-memory-agent-preset\README.md` ثم `node verify.mjs` — يلزم إعادة تشغيل DSH.
- **تطوير إضافة فيسبوك**: `facebook share\تحليل-الإضافة-وخطة-التطوير.md` (نقاط الضعف 1–28 + خطة v2.0.0) — القديمة للمقارنة في `_backup_v1.0.0`.
- **المساعد الشخصي**: `el-naggar-brain\README.md` → `ARCHITECTURE.md` → `docs/adr/` → `python main.py`.
- **الجسر PC↔أندرويد**: `Ai ME keybord\README.md` → `ARCHITECTURE.md`/`PROTOCOL.md` + `python tools/health_check.py`.
- **أدوات الورشة**: `laser-box-designer\index.html` (فتح مباشر بالمتصفح) و`Ps grad\README.md` (تثبيت CCX/UDT).
- **تطبيقات AI Studio**: افتح كل مجلد في Android Studio / `npm run dev` (استوديو-القص) مع `GEMINI_API_KEY`.

## فهرس مختصر

| المسار | ما هو |
|---|---|
| `facebook share\` | الحزمة المحورية: إضافة كروم v2 + qwen-tool-fix + dsh-memory-agent-preset + وثيقة التحليل |
| `facebook share\qwen-tool-fix\vllm_qwen_coder_tool_parser.py` | الإصلاح: parser plugin لـ vLLM باسم `qwen_coder_json` |
| `facebook share\qwen-tool-fix\test_vllm_qwen_coder_tool_parser.py` | 27 اختبار وحدة (تعمل بلا vLLM) |
| `facebook share\qwen-tool-fix\check-qwen-tool-calling.mjs` | اختبار قبول حي (1/6 → 6/6) |
| `facebook share\qwen-tool-fix\capture-corpus.mjs` + `corpus\` | التقاط الأدلة الخام من الخادم |
| `facebook share\dsh-memory-agent-preset\preset-memory.patch.yml` | كتلة الـ preset القابلة للنقل بين profiles |
| `facebook share\dsh-memory-agent-preset\verify.mjs` | 23/23 فحص تحقق آلي |
| `facebook share\manifest.json` | MV3 — Facebook Smart Curator & Reposter v2.0.0 |
| `facebook share\تحليل-الإضافة-وخطة-التطوير.md` | تحليل 28 نقطة ضعف + خطة v2.0.0 (245 سطرًا) |
| `_backup_v1.0.0\` | نسخة الإضافة القديمة (مصدر التحليل الأمني) |
| `el-naggar-brain\` | «النجار برين»: مساعد AI بذاكرة معرفية + APK (README + ARCHITECTURE + docs\adr\) |
| `Ai ME keybord\` | جسر PC↔أندرويد + لوحة مفاتيح ذكية (FastAPI/PyQt6/Kotlin + PROTOCOL.md) |
| `استوديو-القص-والتصميم-الذكي\` | تطبيق ويب AI Studio (Vite/TS + server.ts، GEMINI_API_KEY) |
| `drivedeck\` | تطبيق أندرويد AI Studio + `layan-erp---staff-edition` داخله |
| `smart-ai-gallery\` | معرض صور ذكي (أندرويد، APK جاهز 146MB) |
| `auto poster\` | AutoPoster Pro (client/server Node) |
| `Ps grad\` | إضافة فوتوشوب UXP: Smart Gradient & Palette Engine (OKLab/OKLCH + CCX) |
| `laser-box-designer\` | مولد صناديق ليزر ويب (4 ملفات، Three.js) |
| `facebook\` | مجدول فيسبوك بايثون (scheduler.db) |
| `promo\` | ريل «النجار برنت» 2026 + أوامر ffmpeg |
| `scrcpy-master\` | مصدر scrcpy المفتوح (vendored) |

---
_دراسة مكتملة — ميزانية القراءة 12/12 ملفًا. جرد التوب-ليفل: 13/13 مجلدًا. الملفات المقروءة: 2×README داخل facebook share، manifest.json، وثيقة التحليل، و8 README/بنية للمشاريع الأخرى._
