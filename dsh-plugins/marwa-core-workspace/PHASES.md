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
