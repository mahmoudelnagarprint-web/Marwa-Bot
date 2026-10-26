# غرفة عمليات مروة — Marwa Core Workspace (Native DSH UI Plugin)

إضافة واجهة أصلية (Native DSH UI Plugin) تُزرع مباشرة داخل شجرة مشروع مروة الأساسي
`G:\Marwa-Bot` وتعمل داخل بيئة DeepSeek Harness (DSH) نفسها — بلا تطبيق خارجي منفصل،
وبأقل استهلاك للرام (بلا خادم Next.js ولا متصفح ثقيل؛ جسر بايثون واحد يُطفأ عند الخمول).

## القرار المعماري
- **المسار:** `G:\Marwa-Bot\dsh-plugins\marwa-core-workspace\` — بجانب `mcp/` (خوادم MCP) و`Vision-Lab\plugins\` (إضافات فيجن) و`notebook/` (نوتبوك v1) و`exports/` (الكتالوج).
- **الحِمل:** 3 فتحات DSH أصلية: `main` (اللوحة المركزية بمفتاح `marwa-core`) + `sidebar.panellist` (أيقونة الشريط الجانبي) + `conversation.composer.dock` (شريحة سريعة في الشات الأصلي).
- **الجسر:** POST `/marwa-core/api` (يوفره نصف المضيف داخل Harness نفسه، مُصادق تلقائياً) ← جسر بايثون JSON-lines `bridge/dsh_bridge.py` (يُشغَّل كسولاً من `.venv` ويُطفأ بعد 5 دقائق خمول).

## الاكتشاف الذاتي (2026-10-26) — مصدر الحقيقة
| الكيان | المسار المكتشف | الربط |
|---|---|---|
| مروة | `orchestrator/core.py` + `AGENT.md` | غرفة القيادة |
| الفريق (8 وكلاء) | `orchestrator/squad/<agent>/AGENT_PROFILE.md` + `CHAT_BOOTSTRAP_PROMPT.md` + `orchestrator/router.py` (`_PERSONAS`) | الرصيف المصنف |
| أفكاري (Notebook v2) | `Vision-Lab/projects/notebook-v2/` (web 8110 + بوت @Afkary22Bot) | تبويب 📓 + مؤشر تزامن |
| فيجن (Vision) | `Vision-Lab/` (المعمل الوحيد) + `SQUAD_PROFILE.md` | تبويب 👁️ مرسم فيجين |
| الكتالوج الماستر | `exports/products_catalog_master.xlsx` | جدول السياق الحي |
| قاعدة POS (قراءة فقط) | `pos_data.db` (مرآة اللابتوب المحلية) | كروت السياق الحي |
| النوتبوك v1 الموحد | `notebook/data/notebook.db` عبر `notebook/store.py` (القناة الرسمية) | إضافة/تثبيت/نسخ النوتات |

## الهوية
- أسود مطفي `#09090b` + ذهبي ملكي `#d4af37` + خط Cairo + توقيع لوني لكل وكيل (مروة=ذهبي، فارس=سماوي، سلمى=وردي، بيبو=كهرماني، صاصا=تركواز، حكيم=برتقالي، فيجن=نيلي، كوكو=زمردي، أفكاري=فوشيا، راصد=بنفسجي).

## التشغيل
- تثبيت: `plugin_manager` → `install_bundle` ← هذا المجلد (لا تُعدّل ملفات الـ profile يدوياً أبداً).
- الفتح: أيقونة «م» الذهبية في الشريط الجانبي → لوحة «غرفة عمليات مروة»، أو `Ctrl+K` داخل اللوحة.

## الصدق التشغيلي
- كل بيانات POS/الكتالوج/النوتبوك قراءة فقط (ميثاق MARWA_CORE)؛ الكتابة الوحيدة في النوتبوك عبر `store.add_note` الرسمي.
- المؤشرات (NB2 8110، الرام، العقدة) تُقرأ حياً من المضيف؛ عند تعطل الجسر تظهر الواجهة «غير متاح» بصدق.
- الردود الحقيقية للوكلاء تتم في جلسات DSH الأصلية («فتح في DSH» / «ربط جلسة DSH» بيتا) — الغرف المحلية لا تخترع ردوداً.

## المرحلة 2 — ربط الجلسات التلقائي (Native Agent Presets & Zero-Click Routing)
- **10 Agent Presets حية** تُبنى عند الإقلاع من الدساتير الفعلية (`orchestrator/squad/*` + `AGENT.md` + مسارات Notebook v2 وVision-Lab)
  عبر `agentPresets.register` في المضيف: marwa، notebook، rased، hakim، fares، salma، koko، bibo، sasa، vision.
  كل Preset يحمل persona بدستور الوكيل + مراجع رسمية (كوكو ← الكتالوج، صاصا ← أدوات الفحص + bash/pwsh/fs، فيجن ← Vision-Lab + أدوات كود).
- **المولد:** `scripts/build_presets.py` — يقرأ الدساتير وينتج `presets.summary.json`؛ نمط ثابت عبر `--static-presets` إن أُريد (أي تحديث للدساتير = إعادة توليد + إعادة تثبيت).
- **Zero-Click:** فتح غرفة ← `ensureAgentSession`: 1) جلسة مسجلة محلياً ما زالت حية؟ 2) جلسة نشطة مطابقة للـPreset عبر
  `sessions.findForPreset` (يقرأ `Session.header.agentPreset`)؟ 3) إنشاء فوري `uiWorkspace.connectWorkspace(wsId, {agentPreset})` بالخلفية.
- **حقن الذاكرة:** عند تهيئة أي جلسة جديدة يُحقن بلوك «📌 قرارات/ملاحظات المالك المثبتة» من `notebook.pinned` (أولوية عالية/عاجلة).
- **بوابة الاعتماد:** `[✅ اعتماد وتنفيذ]` يرسل أمر التنفيذ لجلسة DSH الحقيقية للغرفة؛ `[🦉 طلب تدقيق]` يستدعي Preset حكيم برمجياً ويرسل الطلب.
- **الحالة:** `presets.status` (لوحة الـ🧬 في الشريط العلوي) + `presets.rebuild` (تحديث حي) + `boot.log`/`presets.last.log` كسجلات إقلاع.
- ملاحظة: تغييرات نصف المضيف تُفعَّل بإعادة تفعيل/تركيب الحزمة؛ لوحة الواجهة تتحدث بعد تحديث صفحة المتصفح.
