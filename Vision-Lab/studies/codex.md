# 🏗️ ملخص معماري: codex (مساحة الأدوات)

> دراسة جرد معمارية (قراءة فقط) لمجلد `G:\ai\codex` — الأدوات المساندة.
> النطاق: كل ما في المجلد **سوى** `LayanStoreERP` → دراسته الكاملة موجودة مسبقًا في `studies/LayanStoreERP-live.md` (سطر الإحالة في القسم 7).
> المنهجية: استنتاج من أسماء الملفات والدلائل + قراءة ملفات سطحية محدودة (10/15 من الميزانية). لا سرد داخل: node_modules / .m2 / .userhome / .userprofile / target / .git / apache-maven-3.9.6 / java-* / tools / layan-erp---staff-edition.
> الحالة: نهائية — 10 ملفات مقروءة.

---

## 1) الغرض
`G:\ai\codex` ليس مشروعًا واحدًا بل **مساحة عمل تجميعية (Tools Sandbox)** لأدوات مساندة حول ورشة «النجار برنت» ومنظومة ليان:
- **LayanStoreERP** = الأصل الحي لنظام ERP ليان (خارج نطاق هذه الدراسة) — وداخله أيضًا تعيش المرآة السحابية وبيئات أدوات AI (انظر القسم 7).
- **أدوات طباعة وإنتاج** للمطبعية: `Epson ligt` (RIP لطابعة Epson L1800) و`printy` (بروفايلات طابعات TPP/Qt).
- **بنية تحتية للأندرويد**: `Docar/docker-android` (محاكي أندرويد داخل Docker).
- **مشروع ذكاء شخصي**: `Elnaggarbrain V2` = «JARVIS» — نواة عقل وكيل AI بلغة Python القياسية فقط.

## 2) نقاط الدخول
| العنصر | نقطة الدخول | الدليل |
|---|---|---|
| Docar/docker-android | `docker-compose.yml` → `docker compose up android-emulator` | README.md (أوامر التشغيل) |
| Elnaggarbrain V2 | `src/jarvis/` (حزمة `el-naggar-brain-v2`) + مستندات `docs/ROADMAP.md` | pyproject.toml، BUILD_STATE.json |
| Epson ligt/l1800-rip-project | `run.bat` (تثبيت+تشغيل) / `run_gui.py` (واجهة PySide6) | README.md |
| printy | `main.py` → `ui.main_window.launch_app` / `start_printy.bat` | main.py |
| paypass | **لا يوجد** — مجلد فارغ تمامًا (0 عنصر) | فحص عدّاد |
| LayanStoreERP | خارج نطاق — دراسته مستقلة | — |

## 3) الهيكل العام
```
G:\ai\codex\
├── Docar\docker-android\        ← مشروع Docker لإمولة أندرويد (مستودع Git منسوخ: .git/.github)
│   ├── Dockerfile / Dockerfile.gpu / docker-compose.yml
│   ├── install_android.sh · scripts\ · keys\ · assets\ · README.md · LICENSE
├── Elnaggarbrain V2\            ← «JARVIS» عقل وكيل AI (Python 3.12، مكتبة قياسية فقط)
│   ├── .jarvis\ · src\jarvis\{agents,tools} · contracts\ · docs\ (22 مستندًا)
│   ├── tests\ · scripts\ · .venv\ · .pytest_cache\
│   ├── BUILD_STATE.json · pyproject.toml · c.db · l.db · session-status.txt
├── Epson ligt\l1800-rip-project\← RIP مخصص لطابعة Epson L1800 (Gutenprint + PySide6)
│   ├── src\ · patches\ (لعُدة Gutenprint) · vendor\ · config\ · profiles\ · docs\
│   ├── run.bat · run_gui.py · rip_config.json · build_exe.bat · VERSION (1.0.0-beta)
├── LayanStoreERP\               ← خارج النطاق (ERP ليان — دراسة مستقلة؛ يداخله cloud-mirror وبيئات الأدوات)
├── paypass\                     ← فارغ (Placeholder)
└── printy\                      ← محلل بروفايلات طابعات + واجهة Qt
    ├── core\ · ui\ · printers\ · plugins\ · ps_plugin\ · presets\ · profiles\
    ├── colors\ · locale\ · translations\ · assets\ · output\ · venv\
    ├── main.py · requirements.txt · start_printy.bat · printers_cache.json (~21MB)
```
ملاحظة مهمة: عناصر السياق المذكورة في التكليف (cloud-mirror، .agents/.qwen/.m2، apache-maven-3.9.6، java-*، tools، layan-erp---staff-edition، node_modules) ليست على مستوى `codex` بل **داخل LayanStoreERP** — لذا تصنّف ضمن سطر الإحالة (القسم 7) وليست وحدات مستقلة هنا.

## 4) الوحدات الرئيسية
- **Docar/docker-android** (v1.1.0، HQarroum): صورة Docker ميني (Alpine+KVM) تشغّل محاكي أندرويد كخدمة — ADB على منفذ 5555، متوافق مع scrcpy، متغيرات API_LEVEL/IMG_TYPE/ARCHITECTURE، دعم GPU/CUDA وPlay Store، ومفاتيح ADB في `keys\`. دورها المحتمل: بيئة اختبار أندرويد معزولة/CI بدل تشغيل محاكي مباشرة.
- **Elnaggarbrain V2 (JARVIS)**: «Brain Kernel» بمعمارية V3 — كيرنل ذاكرة (Memory Engine)، بوابة مزودات + Token Economy، دماغ LLM، واجهة عقل عامة، تنفيذ أدوات/قدرات، نواة تنفيذ وكيل، تخطيط LLM بناءً، وتكامل Google (OAuth 2.0 + Drive/Sheets/Calendar للقراءة فقط) — كل ذلك بلا أي اعتماد خارجي (stdlib فقط). الحالة: Phase 5D-4 COMPLETED (المرحلة التالية 5D-5). توقف الجلسة موثق في `session-status.txt` («We are paused... resume at 2026-10-03T12:24:57Z»).
- **Epson ligt/l1800-rip-project (v1.0.0-beta)**: نظام RIP احترافي مبني على Gutenprint مع Patch مخصص للتحكم بقنوات الحبر الفاتح (LC/LM) عبر `patches/gutenprint-l1800-channel-control.patch` + `rip_config.json` (كثافات CMYK + حد حبر إجمالي + منحنيات LC/LM لنقاط Light/Mid/Dark — نموذج حالي لمجموعة `glossy_photo`، بدون إعادة ترجمة)، وواجهة PySide6 داكنة (سطوع/تباين/Gاما، 5 بروفايلات جودة، Presets JSON، سجل طباعة في `config/print-history.json`).
- **printy**: محرك بروفايلات طابعات بصيغة TPP — `core.parser.TppParser` يمسح مجلد `printers\` ويطابق الطابعات المثبتة (فلتر Epson أولًا) ثم يفتح واجهة Qt (PySide6 ≥6.7 عبر `qt_compat`)؛ فيه `ps_plugin` (إضافة PhotoShop محتملة) ونظام Plugins/Presets/Translations و`printers_cache.json` (~21MB كاش بروفايلات). البادئ `start_printy.bat` يبني venv محليًا ويثبّت الاعتماديات (PySide6/Pillow/numpy/pywin32) ثم يشغّل `main.py`.
- **paypass**: فارغ — مجرد اسم محجوز.
- **cloud-mirror**: ليس على مستوى `codex` بل **داخل LayanStoreERP** — دوره (موثق في دراسة الـ ERP): مرآة سحابية Next.js 16 + React 19 تقرأ Firestore مباشرة (`src/lib/firebase.ts`، projectId `layan-erp`) بـ15 صفحة admin، وتُصدَّر ثابتًا إلى `out/` لـFirebase Hosting، ويعمل مقابل 3 خدمات Java للـ Sync/Listener/Migration — أي أنه **واجهة الويب الإدارية لمرآة بيانات ERP السحابية** (تفصيله الكامل في `studies/LayanStoreERP-live.md`).

## 5) المكتبات
| العنصر | التقنية | مكتبات ملموسة (بدليل) |
|---|---|---|
| docker-android | Docker/Alpine + Java 11 + QEMU/KVM + Android SDK/Emulator | Dockerfile، docker-compose.yml |
| Elnaggarbrain V2 | Python ≥3.12 — **مكتبة قياسية فقط، صفر اعتماديات** (`dependencies = []`) | pyproject.toml |
| l1800-rip-project | Python 3.11 + PySide6 + Pillow + PyInstaller (واجهة)، Gutenprint/C (النواة) | README + requirements.txt + VERSION |
| printy | Python + PySide6≥6.7 + Pillow≥10 + numpy≥1.26 + pywin32 (ويندوز فقط) | requirements.txt |
| cloud-mirror (داخل LayanStoreERP) | Next.js 16.2.3 + React 19 + firebase-js + Tailwind 4 + TypeScript | دراسة LayanStoreERP-live.md |

## 6) مخازن البيانات
- `Elnaggarbrain V2\c.db` و `l.db`: قاعدتا SQLite صغيرتان (~12KB) — مخازن حالة/ذاكرة محلية (استنتاج من الامتداد وقيد «لا وصول مباشر لـ SQLite من طبقة العميل» في BUILD_STATE).
- `Elnaggarbrain V2\BUILD_STATE.json` + `session-status.txt`: حالة بناء/جلسة نصية؛ مخزن الوكالة الدائم متعطَّل عمدًا حسب القيود.
- `l1800-rip-project\config\` (ومنه `print-history.json`) + `rip_config.json` + مجلدات `profiles/` و`presets/` — تخزين إعدادات/منحنيات/سجل كملفات JSON.
- `printy\printers_cache.json` (~21MB) — كاش بروفايلات الطابعات (أكبر ملف بيانات في المساحة)، بالإضافة إلى `presets/` و`profiles/` و`output/`.
- `Docar\docker-android`: `/data` داخل الحاوية للاستمرارية الاختيارية للـ AVD (وإلا يُمسح عند كل إعادة تشغيل).
- لا مخازن سحابية مفعّلة هنا (JARVIS: مزامنة سحابية مُنفَّذة لكن بلا بيانات اعتماد Supabase).

## 7) التكاملات (مع LayanStoreERP وDSH)
- **الإحالة (سطر واحد)**: `LayanStoreERP` = الأصل الحي الوحيد لـ ERP ليان — دراسته الكاملة في `studies/LayanStoreERP-live.md`، وهو أيضًا المضيف الداخلي لعناصر السياق: `cloud-mirror` (مرآة سحابية Next.js/Firestore لمزامنة ERP) وبيئات أدوات AI (`.agents/.qwen/.m2/apache-maven-3.9.6/java-*`) و`tools` و`layan-erp---staff-edition` — كلها محظورة السرد هنا وكلها مشروحة تفصيلًا في دراسة الـ ERP.
- **مع DSH/الوكيل**: `Elnaggarbrain V2 (JARVIS)` هو المرشّح الطبيعي لعقل وكيل محلي مساند/بديل لـ DSH (خطة مزودات + صلاحيات + تنفيذ قدرات)، فيما يخدم docker-android احتياجات الاختبار عبر `adb connect` (نفس مسار أدوات android_* في DSH).
- **مع المطبعية**: l1800-rip وprinty يلتفّان مباشرة حول عمل «النجار برنت» (تحكم ألوان أحبار Epson L1800، بروفايلات طابعات TPP).
- تكامل مباشر مكتوب بين هذه العناصر الخمسة وبين LayanStoreERP لم يُلاحَظ على مستوى `codex` الجذري (لا مراجع متبادلة في الملفات المقروءة).

## 8) تقييم الصحة (بدليل)
- **Elnaggarbrain V2**: ✅ سليم ومُختبر ذاتيًا — `BUILD_STATE.json`: verification PASSED (113 unit + 43 integration + 34 e2e، فحص أسرار وحدود طبقات)، Phase 5D-4 COMPLETED، لا أخطاء حرجة. نقاط انتباه: مخزن Agent الدائم غير محدد، InMemoryCredentialStore للتطوير فقط، لا بيانات اعتماد حقيقية، والجلسة موقوفة منذ 2026-10-03 (session-status.txt).
- **Epson ligt/l1800-rip-project (v1.0.0-beta)**: ✅ ناضج التشغيل — README بأوامر تثبيت/تشغيل/بناء EXE + `PAPER_EJECT_FIX.md` (إصلاح موثق) + logs/backups/out + `rip_config.json` بتوليف فعلي (glossy_photo) — دليل استخدام فعلي في الورشة.
- **printy**: ✅ يعمل بشكل رئيسي — نقطة دخول واضحة + بادئ تشغيل يبني venv تلقائيًا + كاش بروفايلات ضخم؛ لكن التبعية على Qt مشروطة بفشل صامت مع طباعة تتبع (سلوك مقصود في main.py)، والاعتماديات ضئيلة (4 أسطر) أي مشروع خفيف قابل للكسر فقط عند غياب Qt.
- **Docar/docker-android**: ✅ مستودع مفرد مكتمل (README+CI+LICENSE+Dockerfile.gpu) لكنه مستودع خارجي مُستنسخ — لا دليل على تخصيص محلي غير `keys\`.
- **paypass**: ⚠️ فارغ تمامًا (0 عنصر) — إما أطلال/محجوز؛ لا يمكن تقييم أي شيء.
- **LayanStoreERP**: خارج نطاق التقييم هنا (انظر دراسته).

## 9) خريطة دخول للتطوير
1. **لعقل وكيل AI محلي**: ابدأ من `Elnaggarbrain V2\docs\ROADMAP.md` ثم `docs/ARCHITECTURE.md` و`NEXT_TASK.md` (المرحلة التالية 5D-5) — الكود في `src/jarvis/`.
2. **لمعالجة الطباعة L1800**: `patches/gutenprint-l1800-channel-control.patch` = مصدر الحقيقة + `rip_config.json` للتوليف الحي + `run_gui.py` للتجربة + `build_exe.bat` للتوزيع.
3. **لبروفايلات الطابعات**: `printy\main.py` → `core/parser.py` و`printers\`، وواجهة `ui/main_window.py`؛ التشغيل عبر `start_printy.bat`.
4. **لمحاكي أندرويد في Docker**: `Docar\docker-android\docker-compose.yml` (أو build-args حسب API) ثم `adb connect 127.0.0.1:5555`.
5. **القرارات المعلّقة في JARVIS** (من BUILD_STATE): تخزين مفاتيح إنتاجي (CredentialStore)، متجر مهام وكيل دائم، توثيق اختبار Google الحي — نقاط دخول مباشرة للمساهمة.
6. **تحذير**: لا تعدّل `vendor/` في l1800 (قابل لإعادة الجلب عبر scripts)، ولا تدخل في `.venv` أو `__pycache__`.

## 10) فهرس الملفات المهمة (جدول)
| الملف | العنصر | الأهمية |
|---|---|---|
| `Docar\docker-android\docker-compose.yml` | Docar | تشغيل المحاكي كخدمة |
| `Docar\docker-android\README.md` | Docar | مرجع الاستخدام والبناء |
| `Elnaggarbrain V2\BUILD_STATE.json` | JARVIS | حالة البناء/الاختبارات/القيود الحية |
| `Elnaggarbrain V2\pyproject.toml` | JARVIS | هوية المشروع وقاعدة «صفر اعتماديات» |
| `Elnaggarbrain V2\session-status.txt` | JARVIS | حالة إيقاف/استئناف الجلسة |
| `Elnaggarbrain V2\docs\*` (22 مستندًا) | JARVIS | معمارية/قرارات/أمان/خريطة المراحل |
| `Elnaggarbrain V2\c.db` / `l.db` | JARVIS | مخازن حالة SQLite محلية |
| `Epson ligt\l1800-rip-project\patches\*.patch` | L1800 | مصدر الحقيقة لمنطق الأحبار |
| `Epson ligt\l1800-rip-project\rip_config.json` | L1800 | توليف المنحنيات وقت التشغيل |
| `Epson ligt\l1800-rip-project\README.md` | L1800 | دليل التشغيل/البناء/QA |
| `Epson ligt\l1800-rip-project\VERSION` | L1800 | 1.0.0-beta |
| `printy\main.py` | printy | نقطة الدخول ومنطق المطابقة |
| `printy\requirements.txt` | printy | الاعتماديات (PySide6/Pillow/numpy/pywin32) |
| `printy\start_printy.bat` | printy | بادئ التشغيل مع بناء venv |
| `printy\printers_cache.json` | printy | كاش البروفايلات (~21MB) |
| `G:\ai\Naggar Print POS Agent\Vision-Lab\studies\LayanStoreERP-live.md` | (مرجع) | دراسة ERP ليان الكاملة |
