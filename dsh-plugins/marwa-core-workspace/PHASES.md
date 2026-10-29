# Marwa Command Center — سجل المراحل والأدلة

> توجيه هندسي رئيسي (2026-10-28): تحويل واجهة marwa-core-workspace إلى بيئة قيادة مبنية على
> محرك DSH الأصلي — بلا محرك محادثة بديل، بلا بيانات وهمية، وبلا خروج المستخدم من الواجهة.

## الحالة الأساسية الموروثة (v1.5.3)

- إصلاح حقن Cordis في النصفين: `export const inject = ['connection','webServer']` (index.js)
  و `inject: ['slots','layout','workspaces','uiWorkspace','sessions']` (client.js).
- **دليل نجاح التسجيل**: `route.diag.json` → `{ "via": "connection.fetch.register", "ok": true, "injected": true, "registered": true }` (إقلاع 2026-10-28 02:54).
- كود التسجيل داخل `ctx.inject([...], ...)` + fallback خام لـ`webServer.register` (kind:'exact') + watchdog تشخيصي.

## المرحلة A — الاكتشاف والتشخيص (مكتملة)

**المنهج**: قراءة كود الإصدار الحالي من `app.asar` المستخرج + الاستعلام عن العقود الرسمية
من فاحص Cordis الحي (host/client Service + Config). صفر تعديلات وظيفية في هذه المرحلة.

**ما يدعمه DSH أصلاً (بالأدلة)**:
- Slots: `main` / `sidebar.panellist` / `conversation.composer.dock` — مسجّل في client.js:1127-1140.
- Factory slot للمحادثة الأصلية: `conversation.content` (session-maybe) — قابل للتضمين بتمرير sessionId.
- خدمات الواجهة (عقود رسمية): uiWorkspace (openSession/openWorkspace/connectWorkspace/startSession)،
  sessions (retain/create/fork/search + binding.session.prompt)، workspaces (create idempotent)، layout.
- خدمات المضيف: connection.fetch.register (مسار مصادق — عقد ConnectionFetchRoute)،
  agentPresets (دساتير الوكلاء)، workspaceRegistry (resolveByPath)، subagents + agentTeams
  (التكليف الأصلي بين الوكلاء)، commands/approval/jobs.
- WorkspaceView: `{ workspaceId, path, title, sessionIds, createdAt, updatedAt }` — المسار مكشوف للعميل.
- `workspaces.create({path})` — «created or **idempotently resolved**» → منع التكرار مدمج رسمياً.

**ما كانت تعاني منه الواجهة (وانتهى)**:
- 404 صامت: تسجيل المسار كان في فرع ميت (`!connection &&`) + غياب إعلان inject → عولج بالحقن الرسمي.
- خدمات الواجهة undefined بصمت: `ctx.get` على متغير غير معرف في النطاق → عولج بـSVC/getSvc بعد الحقن.

## المرحلة B — نموذج وكيل واحد (قيد التنفيذ — فارس)

**التغييرات**:
1. `bridge/dsh_bridge.py`: endpoints جديد `binding.get` / `binding.ensure` —
   سجل ربط دائم في `orchestrator/marwa_command_center/bindings.json`
   (Agent → workspaceId/title/path + preset + lastSessionId + updatedAt)، كتابة ذرية tmp+replace.
2. `client.js` — `ensureAgentSession`:
   - 3-أ: استشارة سجل الربط أولاً (workspaceId المحفوظ يتفوق على مطابقة الأسماء).
   - الاكتشاف: مطابقة `squad/<agent>` في المسار + العنوان العربي من AGENT_MAP.
   - `workspaces.create({path})` الرسمي (idempotent — لا ازدواج بالنقر المتكرر).
   - حفظ الربط fire-and-forget في مساري الإرجاع (جلسة معاد استخدامها / جلسة منشأة).

**ملاحظة تشغيل**: endpoints الجسر الجديدة تُحمّل مع إعادة تشغيل التطبيق (أو قتل عملية
الجسر — يعاد إطلاقها كسولاً). قبل ذلك تفشل `binding.get` بلطف ويسقط الكود للاكتشاف العادي.

**الاختبارات**:
- [x] `node --check client.js` — OK
- [x] `python -m py_compile bridge/dsh_bridge.py` — OK
- [x] **اختبار وظيفي مباشر للجسر** (تشغيل dsh_bridge.py بمدخل JSON-lines):
      `binding.ensure` بعنوان عربي «غرفة عمليات - فارس» → `{ok:true}` + الملف على القرص
      بترميز UTF-8 سليم + `binding.get` يعيد نفس السجل. (دليل: مخرجات 2026-10-28 04:05)
- [x] **عيب مكتشف ومصلوح بالاختبار**: stdin كان بلا لف UTF-8 → UnicodeEncodeError للنص
      العربي في params. عولج (`sys.stdin = io.TextIOWrapper(..., encoding="utf-8")`) —
      يفيد كل endpoints مستقبلاً بمعاملات عربية.
- [ ] اختبار وظيفي حي للواجهة: فتح فارس → مساحته الصحيحة → المحادثة الأصلية مضمّنة → إرسال/تاريخ
      (يتطلب تفاعل الواجهة — الجولة القادمة).

## قواعد ثابتة أثناء كل المراحل

- قراءة فقط على `pos_data.db` وملفات الحالة المالية — لا كتابة إنتاج إطلاقاً.
- لا تعديل على ملفات DSH الأساسية — slots + خدمات معلنة + حقن رسمي فقط.
- لا أسرار في الواجهة أو السجلات — الجسر يقرأ NODE_ID فقط من .env.
- لا PASS في التوثيق إلا بدليل قابل للتكرار.

### إضافة (2026-10-28 04:45) — قائمة الجلسات داخل اللوحة
- شريط جلسات الوكيل في صفحته: يقرأ مساحة الوكيل من خدمات DSH المحقونة (workspaces.list + sessions.list)
  ويعرض جلساتها بعناوينها الحقيقية — والنقر يبدّل التضمين فوراً داخل واجهة مروة (بلا openSession/خروج).
- زر «➕ جديدة»: connectWorkspace(workspaceId, {agentPreset}) الرسمي + workspaces.ensure + حفظ binding
  + تحديث فوري للقائمة. ملاحظة: create رسمي idempotent — لا ازدواج بالنقر المتكرر.
- node --check: OK (بعد إصلاح قوس زائد كشفه الفحص).

### إضافة (2026-10-28 05:25) — صفحة الوكيل بتبويبات + إحصائيات حقيقية
- endpoint جديد على الجسر: squad.stats — إحصائيات محسوبة من سجلات فعلية فقط
  (نوتبوك notebook.db موسومة agent:<id> + inbox_tasks/<agent> + ملفات المساحة/AGENTS.md).
- اختبار مباشر ناجح بالأدلة: فارس (مهمتان مفتوحتان + 2 inbox + AGENTS.md 5080 حرف) و
  سلمى (0 مهام + 13 inbox + AGENTS.md غير موجود — تقرير صادق بالسالب).
- صفحة الوكيل أصبحت 5 تبويبات داخل واجهة مروة: 💬 المحادثة (التضمين الأصلي) ·
  📋 المهام (نوتبوك + inbox الحقيقيان) · 📊 البيانات (بطاقة السياق) ·
  📈 إحصائيات (squad.stats) · 📜 التعليمات (الدستور + الهوية من الملفات الأصلية).
- node --check: OK. ملاحظة: التبويبات تعمل بعد إعادة تحميل صفحة DSH (Ctrl+R).

### جلسة 2026-10-28 (استئناف بعد انهيار سياق) — تنظيف + اختبار قبول المرحلة B
1. **تنظيف بيئة العمل (Sanitization):**
   - حُذف `bridge/__pycache__/` (مصدر + نسخة البروفايل — **المثبّتة Junction → المصدر**،
     أي موقع مادي واحد، فأي تعديل على المصدر حي فوراً بلا إعادة تثبيت).
   - فحص ملفات السياق المُحقنة (سكورات الوكلاء المصغّرة `orchestrator/squad/*/AGENTS.md`):
     كشفت عيبين حقيقيين في الجسر أفسدا الحقن.
2. **عيبان مُكتشفان ومُصلَحان في `bridge/dsh_bridge.py` (جوهر إصلاح الـContext):**
   - **`_head` يقصّ في منتصف كلمة:** كان `text[:chars]` يقطع «علاقتها بالفر…» و«اقتراح ي…»
     في نص سليم ← عولج: يقطع عند آخر حد فقرة قبل السقف ويختم بـ`…` (لا كلمة مبتورة).
   - **تكرار عنوان/بدن المثبتة:** عنوان النوتة يضمّن بدنها فظهر «عاجل:خد بالك …» مرتين
     في سطر واحد ← عولج `body != title` (لا تكرار).
   - إعادة توليد AGENTS.md للوكيلَين (fares + marwa) عبر الجسر الحي — نظيفان الآن.
3. **اختبار قبول موثق (متطلب خارطة الطريق «اختبارات قبول بالدليل»):**
   - أُضيف `scripts/acceptance_phase_b.py` — ذاتي، بلا بيانات وهمية، يفحص:
     workspaces.ensure / سلامة الحقن (لا قصّ ولا تكرار) / squad.stats (أرقام فعلية) /
     binding.get / binding.ensure round-trip (سجل وهمي يُحذف ذاتياً — لا يمسّ الربط الحقيقي).
   - التشغيل: **15/15 PASS** (دليل مخرجات 2026-10-28 20:57) — خروج 0.
   - `dsh_bridge.py` py_compile: OK.

### إصلاح انهيار الواجهة (2026-10-29 ~04:30) — Duplicate Prop + التضمين الأصلي
**الخطأ المرصود**: `factory 'conversation.content' occurrence received duplicate prop 'sessionId'`
— محرك DSH يحقن `sessionId` تلقائياً في مصانع المحادثة، وتمريرنا اليدوي
`renderFactorySlot('conversation.content', { sessionId: room.sessionId })` سبّب تعارضاً.

**الإصلاح في `client.js` (5 بنود حسب توجيه المالك)**:
1. **حذف التمرير اليدوي**: الاستدعاء أصبح `renderFactorySlot('conversation.content')` نظيفاً —
   المحرك يأخذ الجلسة من حالته الخاصة (دليل: `grep` الصف اليدوي = False).
2. **تعيين الجلسة النشطة**: مكوّن `NativeMount` الجديد داخل `RoomView` يضبط الجلسة النشطة
   برمجياً قبل الرسم عبر خدمة `sessions` المحقونة (`setActive` إن وُجدت وإلا `ss.active = sid`)
   — بأمان كامل try/catch لا يكسر الرسم.
3. **حماية التضمين الأصلي**: فحص كامل — لا `router.push` ولا `openSession` تلقائي في مسار
   الرسم؛ الاستدعاءان الموجودان (سطرا openDSH وnav) كلاهما خلف أزرار المستخدم فقط
   («ملء الشاشة») — الشات الأصلي يُرسم حصرياً داخل `mcw-native` في المنتصف.
4. **تنظيف الحالة**: `key={active.id}` على `RoomView` (كان موجوداً) + `key: room.sessionId`
   على حاوية الشات الأصلي — إعادة تركيب نظيفة عند تبديل الوكيل أو الجلسة (لا نصوص متداخلة).
5. **المراقبة**: `console.log('[Phase B Test] Workspace: X | Session: Y')` عند تحميل كل
   غرفة وكل جلسة — لتأكيد دقة الربط في الـConsole.

**الفحوصات**: `node --check client.js` OK · لا نص مبتور · الجسر لم يُمس.
**ملاحظة تشغيل**: الإصلاح حي فوراً (النسخة المثبتة Junction → المصدر) — يتطلب
إعادة تحميل صفحة DSH (Ctrl+R) فقط.

## المرحلة C — تعميم النموذج على السرب (قيد التنفيذ — خطوة أولى منجزة)

**البدء العملي (2026-10-29 ~05:40)** — كانت المساحات ناقصة:
- قبل: من وكلاء السرب الثمانية، 4 فقط يملكون `AGENTS.md` (marwa/fares/rased/hakim)
  و4 بلا (salma/koko/bibo/sasa)، وسجل الربط يضم marwa فقط.
- الآن: **توليد كامل** عبر الجسر الحي (`workspaces.ensure` لكل وكيل):
  - أُنشئت AGENTS.md لـ salma, koko, bibo, sasa (بداية المرحلة ج).
  - أُعيد توليد rased و hakim (كانا يحملان نمط التكرار القديم) — **8/8 نظيفون**.
- **فحص السلامة الشامل**: كل ملف AGENTS.md الثمانية بعلامة المولد، بلا قصّ وسط كلمة
  (الـ_fix في _head)، وبلا تكرار عنوان/بدن المثبتة (الـ_fix في workspaces.ensure) —
  دليل scan شامل بتاريخ 2026-10-29 05:43.
- **اختبار القبول موسّع**: أُضيف بند «تغطية السرب» إلى `scripts/acceptance_phase_b.py`
  (يُعيد توليد + يفحص الثمانية كلهم) — **23/23 PASS** (دليل مخرجات 2026-10-29 ~06:00).
- **قيود الاختبار الحي**: المحاولة عبر Playwright/Chromium (ملف `scripts/live_phase_b.cjs`)
  اصطدمت ببوابة الواجهة «dsh web authentication required» — الواجهة محمية بتوكين
  يُسلّم للجلسة الأصلية فقط؛ خدمة الجسر + اختبار القبول يعملان، والاختبار الحي
  داخل الواجهة يُكمل يدوياً (فتح فارس → سطر `[Phase B Test]` في Console).

**الفارق للجلسة القادمة**: المرحلة B شبه مغلقة (بقي الاختبار الحي اليدوي الأخير)،
والمرحلة C بدأت بتعميم المساحات — الخطوة التالية: ربط بقية الوكلاء في سجل الربط
عند أول فتح لواجهة (ensureAgentSession يكتبه تلقائياً) + اختبار فارس الحي في الواجهة.

## إصلاح شريط الكتابة المفقود (2026-10-29 ~08:00) — جذر هندسي + تصحيح اسم السلوت

**الشكوى** (اختبار حي): واجهة الرسائل تعمل عبر `conversation.content` لكن شريط الكتابة
غائب تماماً.

**التشخيص من بنية المحرك الفعلية** (بحث في `app.asar` — لا تخمين):
- **لا يوجد سلوت مستقل «conversation.input» ولا «session.view»** في هذه النسخة:
  - `conversation.input` كاسم سلوت = **0 مرات** (يظهر فقط كبادئة لمجموعة `conversation.input.*`).
  - `session.view` و`chat.input` و`chat.panel` = غير موجودة.
- مربع الكتابة الحقيقي اسمه **`conversation.composer`** — Child **داخل** مصنع
  `conversation.content` (scope: `session`)، و`renderSlotChain` يسلّح المحرر الكامل فقط
  عندما **`sessionId !== void 0`** (`fallbackOnly: sessionId === void 0`)؛ وإلا يرسم شريطاً
  بديلاً (composerBar) بلا محرر. هذه هي الآلية التي تجعل المحرر مختفياً في حالة
  الجلسة غير «المقيمة/الحالية».

**الإصلاح المطبّق في `client.js`** (الحل الجذري):
1. **حذف composer المحجوب بالكامل**: `InputMount` (استدعاء `renderFactorySlot('conversation.composer')`) —
   محذوف. لا نستخدم سلوت `conversation.composer` البتة.
2. **حذف فرض الجلسة via setCurrent/select**: محاولات `ss.setCurrent`/`ss.select`/`ss.current.sessionId` —
   محذوفة. نترك فقط `ss.setActive`/`ss.active` (المصرّح به Phase B الأصلية).
3. **جذر انهيار التبويبات — "Rendered fewer hooks than expected"**:
   كان `NativeMount()` يُستدعى كدالة عادية داخل RoomView، وكان يحتوي `useEffect`. عند تبديل
   `vt` من `'chat'` إلى `'tasks'` كان ترتيب hooks في RoomView يتغيّر → React يدمّر.
   **الإصلاح**: نقل `NativeMount` إلى مستوى الوحدة كمكوّن حقيقي
   (`h(NativeMount, {...})`) — hooks في نطاقها المستقل، وتُفكّك نظيفة عند التبديل.
4. **شريط كتابة مخصص `CustomChatInput`**:
   - textarea ذهبي/أسود RTL + زر إرسال; Enter=إرسال، Shift+Enter=سطر جديد
   - الإرسال عبر مسارات محمية: ① `binding(sid).session.prompt(text)` (الموثّق)
     ② `ctx.chat.send(sid, text)` ③ `ss.prompt(sid, text)`
   - عرض الأخطاء、「✓ أُرسلت」ديناميكياً في الشريط.
5. **حرس آمن لتبويب البيانات**: `agentCtx` null → يعرض `div.mcw-safe-tab` «قيد التطوير».
6. **CSS**: `.mcw-inputwrap` + `.mcw-inputbar` + `.mcw-input` + `.mcw-send`
   + `.mcw-inputerr` + `.mcw-inputok` + `.mcw-safe-tab`.

**الفحص**: `node --check client.js` OK.
**ملاحظة أمان**: لم نلمس طرداً/تنقلاً؛ المحاولات كلها داخل مساحتنا المركزية.
**اختبار يدوي بعد إعادة تحميل DSH**: افتح فارس → الرسائل + (إن سلّحت الجلسة) شريط كتابة
أسفل؛ شاهد سطر `[Phase B Test]` في Console.
