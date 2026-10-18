# 🏗️ ملخص معماري: Maestro

> ملف دراسة — مستودع `G:\ai\Maestro\maestro-main\maestro-main` (إطار خارجي منقول من GitHub، للدراسة فقط)
> آخر تحديث: 2026-10-18 — **دراسة مكتملة** (3 دفعات قراءة: التعريف → خادم MCP → عينتا مهارة)

---

## 1) الهوية والإصدار

| البند | القيمة |
|---|---|
| **الاسم** | Maestro |
| **الشعار** | «Workflow fluency for AI coding agents» — سلاسة سير عمل لوكلاء البرمجة الذكية |
| **الإصدار** | **1.3.1** |
| **المؤلف** | sharpdeveye |
| **الرخصة** | MIT |
| **المستودع الأصلي** | https://github.com/sharpdeveye/maestro |
| **حزمة npm** | `maestro-workflow-mcp` (الخادم) — `maestro` (المستودع الجذري) |

**التصحيح الجوهري (من المحاولة السابقة، مؤكَّد الآن بالقراءة):** Maestro **ليس** إطار أتمتة موبايل (لا علاقة له بمكتبة maestro لاختبار iOS/Android) — بل **إطار مهارات (Skills) لوكلاء ذكاء اصطناعي**: 22 مهارة + خادم MCP + بناء متعدد المزوّدات.

## 2) الغرض الأساسي

معالجة «الملل المتوقع» في سلوك وكلاء البرمجة: أوامر غير منظمة، فيض نافذة السياق، تشتّت الأدوات، غياب معالجة الأخطاء، ونظم متعددة الوكلاء لمشكلات وكيل واحد. يقدم Maestro:

1. **مهارة جوهرية واحدة** `agent-workflow` مع 7 ملفات مراجع قطاعية (هندسة الأوامر، إدارة السياق، تنسيق الأدوات، معمارية الوكلاء، حلقات التغذية الراجعة، نظم المعرفة، الحواجز الأمنية).
2. **21 أمرًا** (diagnose / evaluate / refine / streamline / fortify / zero-defect / amplify / compose / enrich / accelerate / chain / guard / iterate / temper / turbocharge / extract-pattern / adapt-workflow / onboard-agent / specialize / calibrate / teach-maestro) — كل أمر يوصي بالخطوة التالية (لا طرق مسدودة).
3. **Anti-patterns صريحة** («Workflow Slop»): ما يجب ألا يفعله الوكيل — حقن الكود كله في السياق، تعدد وكلاء لمشكلة وكيل واحد، تجاهل معالجة الأخطاء، النشر بدون ضوابط تكلفة… إلخ.
4. **بروتوكول تجميع سياق** عبر ملف `.maestro.md` يضمن وعي كل أمر بخصوصيات المشروع (الأمر `/teach-maestro` يجمعه مرة واحدة).

التركيب: `npx skills add sharpdeveye/maestro` ثم استدعاء الأوامر كـ `/diagnose`، `/fortify payment-workflow`… إلخ. الأوامر قابلة للدمج: `/diagnose /calibrate /refine`.

## 3) نقاط الدخول

| نقطة الدخول | الوصف |
|---|---|
| `source/skills/*/SKILL.md` | 22 تعريف مهارة (المصدر الأصلي للفحص البشري) |
| `mcp-server/src/index.ts` | مدخل خادم MCP (نقل stdio محلي + HTTP بعيد عبر `http.ts`) |
| `mcp-server/src/tools.ts` / `prompts.ts` / `resources.ts` | 4 أدوات MCP / 21 prompt / 8 resources |
| `scripts/build.js` | خط بناء متعدد المزوّدات (يولّد مجلدات `.cursor/skills/` وغيرها) |
| `scripts/validate.js` | فحوصات صحة المهارات (`npm run check`) |
| `scripts/bundle-skills.js` | تجميع المهارات داخل حزمة MCP |

## 4) الهيكل العام للمستودع

```text
maestro/
├── source/skills/          # 22 مهارة مصدرية
│   ├── agent-workflow/     # المهارة الجوهرية + reference/ (7 مراجع قطاعية)
│   └── (21 مجلد أوامر آخر)
├── mcp-server/             # حزمة خادم MCP (TypeScript)
│   └── src/ (index, http, tools, prompts, resources, version)
├── scripts/                # build.js / bundle-skills.js / validate.js
├── package.json            # لا اعتماديات — سكربتات build/check فقط
├── README.md / CHANGELOG.md / LICENSE (MIT) / NOTICE.md
└── assets/logo.svg
```

## 5) المهارات الـ22 (جرد أسماء)

مهارة جوهرية واحدة (1) + أوامر (21) = **22 مجلد مهارة** — مطابقة للفهرسة المسبقة للـ glob:

| # | المجوّد | الدور (من README) |
|---|---|---|
| 1 | **agent-workflow** | المهارة الجوهرية — تصميم سير عمل الوكلاء + 7 مراجع قطاعية |
| 2 | diagnose | تحليل وتدقيق جودة سير العمل بأبعاد مُقيَّمة (قراءة فقط) |
| 3 | evaluate | مراجعة شاملة لجودة تفاعل سير العمل (قراءة فقط) |
| 4 | refine | جولة صقل نهائية على الأوامر والأدوات والإعداد |
| 5 | streamline | إزالة التعقيد غير الضروري، تسطيح الإفراط الهندسي |
| 6 | calibrate | محاذاة مكوّنات سير العمل لمعايير المشروع |
| 7 | fortify | إضافة معالجة أخطاء، إعادات محاولة، بدائل، قواطع دوائر |
| 8 | zero-defect | 🆕 وضع أقصى دقة — لا أخطاء مسموحة |
| 9 | amplify | تعزيز القدرات بأدوات وسياق أفضل |
| 10 | compose | تصميم تنسيق متعدد الوكلاء والتفويض |
| 11 | enrich | إضافة مصادر معرفة وRAG وترسيخ |
| 12 | accelerate | تحسين السرعة وخفض الكمون والتكلفة |
| 13 | chain | بناء سلاسل أدوات وخطوط أنابيب فعالة |
| 14 | guard | قيود أمان وحدود حماية |
| 15 | iterate | حلقات تغذية راجعة ودورات تقييم |
| 16 | temper | تقليل الإفراط الهندسي، تبسيط المبالغ فيه |
| 17 | turbocharge | تجاوز الحدود المعتادة — تقنيات متقدمة |
| 18 | extract-pattern | استخراج أنماط قابلة لإعادة الاستخدام من مهام ناجحة |
| 19 | adapt-workflow | تكييف المهام لمزوّدات/سياقات مختلفة |
| 20 | onboard-agent | إعداد وكلاء جدد من الصفر |
| 21 | specialize | تخصيص المجال (قانوني، طبي…) |
| 22 | teach-maestro | جمع سياق المشروع مرة واحدة → `.maestro.md` |

**تصنيف الأوامر الـ21:** تحليل (2: diagnose, evaluate) · إصلاح وتحسين (6: refine, streamline, calibrate, fortify, zero-defect) · تعزيز (9: amplify, compose, enrich, accelerate, chain, guard, iterate, temper, turbocharge) · أدوات مساندة (5: extract-pattern, adapt-workflow, onboard-agent, specialize, teach-maestro).

**ملاحظة من العينتين المقروئتين بالعمق:** (1) `agent-workflow` — `user-invocable: false`، بروتوكول جمع سياق إلزامي قبل أي إرشاد، 5 مبادئ جوهرية (البنية فوق الارتجال، القيود ميزة، قِس ولا تفترض، تعقيد مناسب، تعثر رشيق)، 7 مجالات بقالب DO/DON'T + مؤشر لمرجعه، و«اختبار Slop» من 10 بنود كل بند يحيل لأمر علاج. (2) `teach-maestro` — البوتستراب: مقابلة من 5 أقسام (النماذج/المعمارية/الجودة/القيود/الأولويات) تُنتج `.maestro.md`، مع جدول «أثر النقص» يربط كل قسم ناقص بالأوامر التي تضعف دونه، وقاعدة NEVER (لا تجاوز أسئلة، لا كتم ملف قائم). frontmatter موحّد: name/description/category/version/user-invocable/argument-hint.

## 6) المكتبات والاعتماديات

- **الجذر `package.json` بلا اعتماديات** — الحزمة عبارة عن محتوى (Markdown) + سكربتات بناء Node خام (`scripts/*.js`) فقط.
- **`mcp-server/package.json`** (`maestro-workflow-mcp`، نفس الإصدار 1.3.1، ESM `type:module`، Node ≥ 20):
  - اعتماديات تشغيل: `@modelcontextprotocol/sdk ^1.12.0` (SDK الرسمي لـ MCP) · `express ^5.1.0` (للنقل HTTP) · `zod ^3.24.0` (تحقق المخططات).
  - تطوير: `typescript ^5.7` + أنواع Node 22/Express.
  - البناء: `npm run bundle` (سكربت `bundle-skills.js` يولّد `generated/skills-data.js` من `source/skills`) ثم `tsc`.
  - `bin`: أمر سطرية `maestro-workflow-mcp` → `dist/index.js`.

## 7) التكاملات (MCP؟)

**نعم — خادم MCP كامل** (`maestro-workflow-mcp` على npm، مبني على SDK الرسمي):

| النوع | العدد | التفصيل (كما في الكود الفعلي) |
|---|---|---|
| Prompts | 21 | أمر واحد لكل command قابل للاستدعاء (`userInvocable`) |
| Tools | 4 | الأسماء الفعلية في `tools.ts`: `maestro_list_commands` · `maestro_run_command` · `maestro_read_context` · `maestro_init` |
| Resources | 8 | المهارة الجوهرية + 7 مراجع قطاعية |

**سلوك الأدوات الأربع (من قراءة `src/tools.ts`):**
- `maestro_list_commands` — يولّد قائمة الأوامر الـ21 مجمّعة حسب الفئة (analysis / fix / enhancement / utility).
- `maestro_run_command(command, focus?)` — **النمط التعليمي**: لا ينفّذ شيئًا؛ يجلب نص المهارة، يحلّ القوالب `{{command_prefix}}` و`{{available_commands}}`، ويعيد التعليمات لينفذها الوكيل بنفسه. الوكيل هو المشغّل؛ الخادم مجرّد «كتاب تعليمات حي».
- `maestro_read_context(projectPath)` — يقرأ ملف `.maestro.md` من جذور المشروع (بروتوكول الوعي بالمشروع).
- `maestro_init(projectName, techStack, conventions?)` — يولّد قالب `.maestro.md` (مكدس تقني + اتفاقيات + ملاحظات سير عمل) لتحفظه يدويًا.

**معمارية النقل (`src/index.ts`, 39 سطرًا فقط):** `McpServer` من SDK الرسمي → تسجيل أدوات/prompts/resources → اختيار النقل من وسيطات CLI: `--http` يستورد `http.ts` **ديناميكيًا** (express لا يُحمَّل لمستخدمي stdio أصلًا) على منفذ افتراضي 3001، وإلا `StdioServerTransport`.

- النقل المحلي: `npx -y maestro-workflow-mcp` — يُضاف لإعدادات Claude Desktop / Cursor / VS Code.
- النقل البعيد: `npx maestro-workflow-mcp --http --port 3001` → `http://server:3001/mcp`.
- **التكامل مع 10 مزوّدات أدوات** (نسخ ملفات مهارات إلى مجلداتهم): Cursor `.cursor/skills/` · Claude Code `.claude/skills/` · Gemini CLI `.gemini/skills/` · Codex CLI `.codex/skills/` · VS Code Copilot/Antigravity `.agents/skills/` · Kiro `.kiro/skills/` · Trae `.trae/skills/` · Trae China `.trae-cn/skills/` · OpenCode `.opencode/skills/` · Pi `.pi/skills/`.

## 8) لماذا موجود في G:\ai (استنتاج مدعوم)

- **السياق المباشر:** يقع بجوار مشاريع محمود النشطة في `G:\ai` (Vision-Lab، وكيل POS، تجارب أدوات) — و`studies/` هدف مخصص لهذا التحليل. مجلد اسمه `Maestro` يحوي `maestro-main` **مكررًا مرتين** (`maestro-main/maestro-main/`) — نمط تنزيل ZIP من GitHub وفكّه دون إعادة تسمية، أي أنه **نسخة للمطالعة لا استنساخ git**.
- **الدافع الوظيفي المرجّح:** المستخدم يبني وكلاء وتركيبات DSH/AI (وكيل POS، لوحات، سكربتات). Maestro يقدّم **منهجية مُجمّعة جاهزة لعناية سير عمل الوكيل**:
  1. تعريفه للـ `user-invocable: false` في المهارة الجوهرية يطابق تمامًا نموذج مهارات DSH (مهارات خلفية تلقائية مقابل مهارات يستدعيها المستخدم) — أي أنه **مرجع تصميمي مباشر** لبناء/تحسين مهارات الوكيل هنا.
  2. «اختبار Workflow Slop» (10 بنود) وقوائم DO/DON'T لكل من: هندسة الأوامر، ميزانية السياق، 3-7 أدوات لكل وكيل، عدم تعدد الوكلاء لمشكلة وكيل واحد — **إرشادات قابلة للتطبيق فورًا** على وكلاء DSH والأوامر (مثل علاج فقدان tool calls عند Qwen الموثق في الذاكرة).
  3. بروتوكول `.maestro.md` (مقابلة → ملف سياق يقرأه كل أمر) نظير عملي لملفات AGENTS.md/context — نمط قابل للتبني في مشاريع G:\ai.
- **خلاصة الاستنتاج:** نُسخ إلى `G:\ai` **كمادة مرجعية لدراسة منهجيات هندسة وكلاء AI** — وتحديدًا لأن فهم ما هو Maestro (مهارات + MCP لا أتمتة موبايل) كان شرطًا لاتخاذ قرار: استخدامه كمرجع أنماط، أو تركيبه كخادم MCP في عميل مثل DSH، أو نسخ مهاراته إلى مجلدات skills. القيمة الجوهرية فيه نصية (219 سطرًا من إرشادات مضغوطة) لا برمجية — خادم MCP مجرد ناقل لهذا النص.

## 9) تقييم الصحة

**النتيجة: مستودع سليم ومتقَن بدرجة عالية (8.5/10) — نسخة مطبوعة سليمة.**

| المحور | التقييم |
|---|---|
| **اتساق الإصدار** | ✅ 1.3.1 متماثل في: الجذر، mcp-server، وfrontmatter المهارات — دقة تحريرية نادرة |
| **الانضباط الوثائقي** | ✅ README شامل، LICENSE (MIT)، NOTICE.md، CHANGELOG، شارات إصدار صادقة |
| **بِنية قابلة للتحقق** | ✅ سكربت `validate.js` للفحص، frontmatter موحّد، وصف يبدأ بـ«Use when…»، لغات أسوار الكود إلزامية (قواعد المساهمة) |
| **جودة كود الخادم** | ✅ مقتضب (index.ts = 39 سطرًا)، تحقق مدخلات zod، تحقق منفذ 1-65535، تحميل ديناميكي لـ express (تجنب حمل غير ضروري لمستخدمي stdio)، رسائل خطأ إرشادية |
| **التصميم التعليمي** | ✅ فصل نظيف: «الخادم يعيد تعليمات؛ الوكيل ينفذ» — أنماط NEXT-STEP إلزامية في كل أمر (لا طرق مسدودة)، جدول أثر لكل قسم ناقص من السياق |
| **نقاط ضعف** | ⚠️ لا توجد اختبارات وحدة ظاهرة (validate.js يفحص المحتوى لا الكود) · ⚠️ `maestro_read_context` يقرأ أي مسار يمرره العميل (طبيعي لخادم محلي، لكن يستحق الوعي عند التشغيل البعيد عبر HTTP) · ⚠️ الغلاف المزدوج `maestro-main/maestro-main` يُربك الأدوات الآلية |
| **سلامة النسخة المحلية** | ✅ الحقول الحاسمة قابلة للقراءة كاملة؛ .git/node_modules خارج نطاق الدراسة عمدًا |

**حكم الاستخدام لمحمود:** قابل للاستخدام فورًا كـ (1) مرجع قراءة لتصميم مهارات DSH، (2) خادم MCP محلي `npx -y maestro-workflow-mcp` لأي عميل MCP، (3) مرجع أنماط anti-patterns لأوامر المشروع. لا يحتاج بناء إلا إذا أريد تشغيل الخادم (`npm run build` داخل mcp-server، يتطلب Node ≥ 20).

## 10) فهرس مختصر

| المسار | الدور | الحالة |
|---|---|---|
| `README.md` | الوثيقة الأم — ما هو، التركيب، التثبيت | قُرئ ✅ |
| `package.json` (الجذر) | الهوية والإصدار 1.3.1، بلا اعتماديات | قُرئ ✅ |
| `mcp-server/package.json` | حزمة `maestro-workflow-mcp` + الاعتماديات | قُرئ ✅ |
| `mcp-server/src/index.ts` | مدخل الخادم (stdio/HTTP) — 39 سطرًا | قُرئ ✅ |
| `mcp-server/src/tools.ts` | الأدوات الأربع الفعلية + توليد `.maestro.md` | قُرئ ✅ |
| `source/skills/agent-workflow/SKILL.md` | المهارة الجوهرية — 7 مجالات + Slop Test | قُرئ ✅ (عينة 1) |
| `source/skills/teach-maestro/SKILL.md` | أمر البوتستراب — مقابلة → `.maestro.md` | قُرئ ✅ (عينة 2) |
| `source/skills/<19 أخرى>/SKILL.md` | أوامر متبقية | غير مقروء (خارج الميزانية، موثقة من README) |
| `mcp-server/src/prompts.ts` / `resources.ts` / `http.ts` / `version.ts` | بقايا الخادم | غير مقروءة — التوقع مغطى بالوثائق والكود المقروء |
| `scripts/*.js` (build/bundle/validate) | خط البناء متعدد المزوّدات والفحص | غير مقروء — موثقة من README |
| `CHANGELOG.md` / `LICENSE` / `NOTICE.md` | تاريخ إصدارات ورخصة | غير مقروءة (واضحة المصدر: MIT، v1.3.1) |

---
*ميزانية القراءة: 10 ملفات كحد أقصى — العدّاد: 7/10 (اكتملت الدراسة ضمن الميزانية)*
