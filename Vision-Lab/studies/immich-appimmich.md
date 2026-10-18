# 🏗️ ملخص معماري: immich-appimmich

> دراسة معمارية بعناية «فيجن» — وضع قراءة فقط (لم تُفتح أي صورة أو بيانات مستخدم — كود وإعدادات فقط). اكتملت 2026-10-18.
> ملاحظة بيئة: مجلد `.venv` حُذف بأمر المالك (كان 1.01GB) — **يتجدد تلقائيًا** عند أول تشغيل/تثبيت للتبعيات (`pip install -r elnagar_ai/requirements.txt`)، ولم يُعد بناؤه خلال هذه الدراسة احترامًا لقرار المالك.
> سكربتا `immich_elnagar_sync.py` و`immich_elnagar_watcher.py` نُقلا مؤخرًا من جذر القرص إلى داخل المشروع (تصحيح تنظيمي 2026-10-17) وقُرئدا من موقعهما الحالي.

## 1) الغرض
تشغيل خادم **Immich** كاملًا عبر Docker لمعرض أعمال ورشة «النجار برنت» (37GB، غالبه صور مستخدم حقيقي)، وفوقه طبقة ذكاء اصطناعي محلية **«النجار AI Brain»** (elnagar_ai): تصنيف الصور بـ CLIP/BLIP، تنظيمها في ألبومات Immich، بحث دلالي بـ FAISS، وتعلم من تصحيحات المستخدم — مع جسر ويب Flask وواجهة محقونة داخل متصفح Immich تنقل الأصول المختارة إلى مجلدات العمل المحلية (H:\CNC\Ordring).

## 2) نقاط الدخول والتشغيل
| نقطة الدخول | النوع | ماذا تفعل |
|---|---|---|
| `elnagar_ai/launcher.py` | **المشغّل الرئيسي** | 3 خطوات: يرفع Docker Desktop إن لزم → `docker compose up -d` → ينتظر `/server/ping` → إعداد أول تشغيل (اختيار مجلدات الفحص) → يشغّل `daemon.py` و`api_server.py` بـ pythonw منفصلَين تمامًا → يفتح المتصفح على `localhost:2283` (`--silent-startup` يمنع الفتح — لهذا تستدعيه مهام الإقلاع) |
| `elnagar_ai/daemon.py` | خلفية دائمة (pythonw) | دماغ خفيف: `Brain(stealth_mode=True, skip_models=True)`؛ خيط `move_worker` كل 30 ثانية (أتمتة النقل) + حلقة كل 5 دقائق للتعلّم الخفي فقط عند توفر النماذج. يوجّه stdout إلى `daemon.log` (سبب انتفاخه لـ 44MB) |
| `elnagar_ai/api_server.py` | خادم جسر Flask | **المنفذ 5000**، CORS مفتوح بالكامل — نقطة نهايات النقل/الحذف/البحث/التنزيل للواجهة المحقونة (جدول في §7) |
| `elnagar_ai/run.py` | CLI تفاعلي (rich) | المدخل اليدوي الشامل: خط أنابيب كامل، بحث نصي/تشابه، إدارة ألبومات، تعلّم نشط، إحصاءات، مجلدات، Wipe & Restart |
| `docker-compose.yml` | بنية الخدمات | 5 حاويات (§7) — ويب Immich :2283 وبروكسي nginx :80 |
| `immich_elnagar_sync.py` | سكربت مستقل | مزامنة شاملة لمرة واحدة: جلب كل الأصول → تصنيف بقواعد الأسماء → ألبومات (أُعيد إدخاله للمشروع 2026-10-17) |
| `immich_elnagar_watcher.py` | سكربت مستقل | مراقب دوري كل 5 دقائق للأصول الجديدة فقط (نُقل للمشروع 2026-10-17) |
| سكربتات Windows | إقلاع | `Start_Elnagar_Server.bat` → `Start_Elnagar_Silent.vbs`، `Run_Elnagar.bat`، `Install/Remove_Startup_Task.bat`، `Enable_Autostart.bat` |
| `export_embeddings.py` → `build_faiss.py` | أدوات فهرسة | تصدير متجهات Immich من PostgreSQL → بناء فهرس FAISS (§6) |

## 3) الهيكل العام
```
immich-appimmich/
├── docker-compose.yml        ← 5 خدمات (server, ML, redis, postgres, elnagar-proxy)
├── nginx.conf + elnagar_web/ ← بروكسي :80 + واجهة محقونة (inject.js 40KB + style.css)
├── .env                      ← إعدادات Immich (UPLOAD_LOCATION, DB_*, IMMICH_VERSION...)
├── immich_elnagar_sync.py    ← مزامنة شاملة (تصنيف بقاموس NAME_RULES → ألبومات)
├── immich_elnagar_watcher.py ← مراقب كل 5 دقائق (نفس القواعد + تتبع synced_assets.json)
├── immich_elnagar_injector.user.js (38KB, 791 سطرًا) ← سكربت Tampermonkey v1.2
├── build_faiss.py / export_embeddings.py   ← بناء فهرس البحث من متجهات Immich نفسها
├── download_model.py / download_ui.py      ← تنزيل نماذج/واجهة (بالاسم)
├── elnagar_ai/               ← حزمة الدماغ (15 وحدة Python + data/)
│   ├── config.py (مركز التكوين) · run.py (CLI) · launcher.py (مشغّل) · daemon.py (خلفية)
│   ├── api_server.py (Flask :5000) · brain.py (المنسّق، 732 سطرًا)
│   └── محركات: vision_engine · classification_engine · search_engine · album_manager
│              filesystem_engine · naming_engine · upload_engine · active_learning
│   └── data/  ← classification_db.json · learned_rules.json · faiss_index.bin(+.meta.json)
│               immich_embeddings.csv · embeddings_cache/ · models (HF_HOME) · _trash · user_settings.json
├── elnagar_web/              ← inject.js + style.css يُخدمان عبر nginx على /elnagar
├── data/                     ← model_cache (ML) + postgres (DB حية) + uploads (مكتبة الصور)
├── _OLD_SCRIPTS_BACKUP/      ← سكربتات مهجورة (wipe_immich.py, reset.py, اختصارات...)
├── empty_video/              ← مُوصل فارغ يُركّب على /mnt/Downloads/Video داخل الحاوية
└── .env                      ← إعدادات Immich القياسية
```
ملاحظة تنظيمية: `immich_elnagar_sync.py` + `immich_elnagar_watcher.py` كانا في الجذر ونقلا للمشروع (2026-10-17) — طبقة مزامنة منفصلة عن حزمة `elnagar_ai`.

## 4) الوحدات الرئيسية
### أ) elnagar_ai — الدماغ المركزي
- **`brain.py` (732 سطرًا) — المنسّق المركزي**: `Brain(stealth_mode, skip_models)` يجمّع المحركات؛ الخط الكامل `run_full_pipeline()`: مسح مجلدات الفحص → رفع عبر `UploadEngine` → معالجة دفعات (10) تحليل/تصنيف → إنشاء ألبومات بأسماء عربية → حفظ التقدم بعد كل دفعة → غير المؤكد إلى ألبوم «❓ تصنيف يدوي (للمراجعة)» → بناء فهرس بحث. دوال محورية: `batch_move_by_ids` (نقل فيزيقي مع سقوط مرجعي لتنزيل الأصل من API ثم حذف الأصل من Immich = «نقل خارج النظام»)، `run_move_automation()` (يفحص أي ألبوم اسمه يحوي «نقل»: «📦 نقل إلى: X» → مجلد فرعي)، `run_stealth_learning()` (يتعلم حين ينقل المستخدم صورة من ألبوم المراجعة إلى ألبوم معروف = تسجيل تصحيح)، `_resolve_local_path()` (ترجمة مسارات الحاوية `/mnt/X/`, `/data/` إلى Windows — ببدائل مثبتة مثل `G:\Downloads\3.2025`)، `wipe_and_restart()`.
- **`config.py` (292 سطرًا)**: مركز كل المسارات (§6) + مفتاح API مضمّن (سطر 30) + `CATEGORY_MAP` (~90 تسمية إنجليزية→عربية تولّد `ZERO_SHOT_LABELS`) + عتبات (ثقة عالية 0.70 / منخفضة 0.40 / أدنى عنقود 3) + إعدادات المستخدم JSON + نوافذ اختيار مجلدات (tkinter وحل PowerShell مرئية لعمليات الخلفية).
- **`api_server.py` (583 سطرًا)**: Flask على **:5000** مع CORS `*` — جسر واجهة المتصفح؛ يهيئ `Brain(stealth_mode=True, skip_models=False)` (وضع كامل بالنماذج)؛ 12+ نقطة نهاية (§7).
- **`vision_engine.py` (238 سطرًا)**: CLIP عبر open_clip (ViT-B-32/openai) بتحميل خامل آمن-خيطيًا؛ تضمينات 512-بعد معياريّة بكاش `.npy` (مفتاح md5 من المسار+الحجم+وقت التعديل)؛ تصنيف zero-shot بـ softmax فوق تسميات CATEGORY_MAP؛ BLIP موجود لكن `generate_caption()` معطّل (يعيد نصًا فارغًا — توفير ذاكرة/سرعة)؛ دفعات 8.
- **`daemon.py` (69 سطرًا)**: خلفية بوضع «خفيف» بلا نماذج؛ خيط `move_worker` كل 30 ثانية + حلقة 5 دقائق؛ توجيه السجلات إلى ملفات.
- **`launcher.py` (273 سطرًا)**: منسّق الإقلاع 3 خطوات (§2).
- **`run.py` (204 سطرًا)**: CLI تفاعلي rich بـ 10 خيارات فوق Brain.
- **أنماط**: تحميل كسول آمن-خيطي، حفظ تقدم بعد كل دفعة (10)، سجل نشاط JSON محدود بآخر 1000 إجراء، قاعدة تتبع مراجعة خفية.
- **محركات تُعرف من نداءات Brain/API (غير مقروءة — أدوار مستنتجة)**: `album_manager.py` (كل استدعاءات Immich للألبومات/الأصول) · `filesystem_engine.py` (نقل/حذف نهائي/سلة) · `naming_engine.py` (اسم عربي للفئة) · `classification_engine.py` (قاعدة classified/pending_review + تجميع HDBSCAN) · `search_engine.py` (بناء/استعلام FAISS) · `upload_engine.py` (رفع وفحص امتدادات) · `active_learning.py` (مراجعة وتصحيحات).

### ب) طبقة المزامنة (الجذر)
- `immich_elnagar_sync.py` (207 سطرًا): دورة شاملة — `POST /search/metadata` بترقيم صفحات → قاموس `NAME_RULES` (~60 كلمة عربية/إنجليزية → 20 فئة عمل: تصاميم Gemini، بوكسات، أفراح، دروع وكؤوس، ميداليات، آيات قرآنية، دعاية صلبة…) + امتدادات فيكتور (`.cdr .dxf .ai .eps .pdf .plt .g64 .xml .svg` → «ملفات فكتور») → إنشاء ألبومات → إضافة دفعات 100.
- `immich_elnagar_watcher.py` (268 سطرًا): نفس القواعد (مكررة حرفيًا) + قاعدة تتبع `synced_assets.json` + بذر أول تشغيل + حلقة 5 دقائق متسامحة مع الانقطاع.

### ج) طبقة الواجهة
- `immich_elnagar_injector.user.js` (v1.2، 791 سطرًا — قُرئ العنوان والآلية): يرصد صفحات `/search?q=` لبحث سياقي، **يعترض `window.fetch`** لالتقاط معرّفات الصور المحددة من أجسام POST (assetIds/ids)، ويحقن أزرارًا في شريط تحديد Immich الأصيل (مطابقة aria-label عربية/إنجليزية). `API_BASE` ديناميكي: منفذ 2283 مباشرة → `http://localhost:5000`؛ عبر البروكسي → `/elnagar-api` (يؤكد دور nginx.conf).
- `elnagar_web/inject.js` + `style.css`: نسخة يخدمها nginx على `/elnagar` — **بصمة SHA256 مختلفة عن سكربت المستخدم** ⇒ نسختان منفصلتان تتعاظمان.

## 5) المكتبات (من requirements فعلًا)
`elnagar_ai/requirements.txt` (14 سطرًا، بلا تثبيت إصدارات — مخاطرة تثبيت مستقبلي):
- **تعلّم عميق**: torch, torchvision, transformers, open-clip-torch (CLIP ViT-B-32/openai؛ BLIP عبر transformers)
- **بحث/تجميع**: faiss-cpu, hdbscan, scikit-learn, numpy
- **صور**: Pillow
- **ويب**: flask, flask-cors
- **أدوات**: requests, rich, python-dotenv
- ⚠️ **نقص مكتشف**: `api_server.py:242` يستورد `deep_translator` وهي **ليست في requirements.txt** — ستفشل `/translate-search` على بيئة جديدة (يسقط على قاموس بديل يدوي عربي→إنجليزي مدمج).
- مكتبة قياسية إضافية: tkinter (اختيار مجلدات) وsubprocess (استدعاء docker/powershell).

## 6) مخازن البيانات
| المخزن | الموقع | الدليل |
|---|---|---|
| PostgreSQL 14 (VectorChord+pgvectors) | حاوية `immich_postgres` — بياناتها `data/postgres` | compose سطر 62-76 |
| جدول `smart_search` | متجهات CLIP الخاصة بـ Immich نفسها — تُصدَّر CSV عبر `docker exec … psql … COPY` | export_embeddings.py:5-7 |
| Redis/Valkey | حاوية `immich_redis` | compose سطر 55 |
| أصول الصور | `${UPLOAD_LOCATION}` = `data/uploads` → `/data` | compose سطر 21 + config.py:40 |
| كاش ML لـ Immich | `data/model_cache` → `/cache` | compose سطر 48 |
| نماذج HuggingFace للدماغ | `elnagar_ai/data/models` (ضبط `HF_HOME` برمجيًا — نماذج محمولة) | config.py:22-24 |
| فهرس FAISS | `elnagar_ai/data/faiss_index.bin` + `.meta.json` (قائمة asset_id) | config.py:287 + build_faiss.py:42-45 |
| CSV متجهات | `elnagar_ai/data/immich_embeddings.csv` (وسيط التصدير→البناء) | build_faiss.py:13 |
| كاش متجهات CLIP | `elnagar_ai/data/embeddings_cache/<md5>.npy` (مفتاح: مسار+حجم+mtime) | vision_engine.py:62-84 |
| قواعد JSON للدماغ | `classification_db.json` (classified/pending_review)، `learned_rules.json`، `brain_log.json` (آخر 1000 حدث)، `user_settings.json`، `stealth_review_tracking.json` | config.py + brain.py |
| تتبع المزامن | `synced_assets.json` بجانب الـ watcher | watcher:10 |
| سلة AI | `elnagar_ai/data/_trash` | config.py:15 |

## 7) التكاملات — نعم: خادم Immich هو قلب النظام
1. **Immich REST API** (`http://localhost:2283/api` + `x-api-key`): `/server/ping` (جاهزية)، `GET /albums`، `POST /search/metadata` (ترقيم صفحات وفق v1.115+)، `POST /albums`، `PUT /albums/{id}/assets` (دفعات 100 ضد OOM)، `GET /assets/{id}/original` (تنزيل بدل الملف المحلي)، وحذف الأصول.
2. **5 خدمات Docker**: immich-server:2283 · immich-machine-learning (كاش `data/model_cache`) · valkey · postgres 14 (vectorchord 0.4.3 + pgvectors) · **elnagar-proxy** (nginx:80 يخدم `elnagar_web` على `/elnagar`، ويُفترض تمريض `/elnagar-api` إلى Flask:5000 — محسوم من منطق `API_BASE` في المحقون).
3. **أقراص كاملة للقراءة فقط** داخل حاوية الخادم: `D:/ G:/ H:/ I:` + `empty_video` على `/mnt/Downloads/Video` — أساس دالة `_resolve_local_path` (تحويل `/mnt/g/... → G:\...` و`/data/... → data\uploads` مع بدائل مثبتة).
4. **جسر الواجهة (Flask :5000)** — أبرز النهايات: `/ping`، `/get-destination`، `/pick-folder` (حوار ويندوز)، `POST /move-assets` (نقل فعلي + حذف من Immich)، `POST /delete-assets` (حذف نهائي من Immich **ومن القرص**)، `POST /delete-immich-only`، `/asset-info/<id>`، `/categories`، `/category-assets/<id>`، `/translate-search` (عربي→إنجليزي)، `/context-search-stream` (SSE بحث FAISS بدفعات 24)، `POST /prepare-download` + `/download-status` + `/download-archive` (ZIP غير متزامن برموز مؤقتة وتنظيف تلقائي بعد 10 دقائق)، `/download-single`. الوجهة الافتراضية للنقل: مجلد طلبات CNC على القرص H.
5. **استغلال ذكي لمتجهات Immich**: `export_embeddings.py` يصدر متجهات CLIP الجاهزة من جدول `smart_search` (psql داخل الحاوية) → `build_faiss.py` يطبّعها ويبني `IndexFlatIP` → بحث دلالي فوري بلا إعادة حساب.
6. **تعلّم خفي**: ألبوم «❓ تصنيف يدوي (للمراجعة)» قناة تعليم — نقل المستخدم صورة منه إلى ألبوم عربي معروف = تصحيح مسجّل يحدّث قواعد التصنيف تلقائيًا.
7. **أتمتة النقل**: أي ألبوم اسمه يحوي «نقل» («📦 نقل إلى: طلبيات») يُفرَّغ دوريًا إلى مجلد الوجهة (بمجلد فرعي بعد النقطتين) ثم تُحذف الأصول من Immich — «نقل خارج النظام» كامل.

## 8) تقييم الصحة (بدليل)
- 🚨 **مفتايا API مضمّنان نصيًا في الكود — ومختلفان**: `immich_elnagar_sync.py:8` = `immich_elnagar_watcher.py:9` (نفس القيمة)، بينما `elnagar_ai/config.py:30` مفتاح آخر. مفتاحان حيّان لخادم Immich مكشوفان في 3 ملفات — التوصية: نقل إلى `.env` + تدوير فوري. (القيم غير مطبوعة هنا عمدًا.)
- 🐛 **خطأ برمجي مؤكد بالقراءة**: `brain.py:237` يستدعي `asset_id_map` غير المعرّف (الصحيح `batch_asset_map`) — NameError حتمي في وضع stealth عند وجود صور للمراجعة؛ مرشح قوي لتكرارات `daemon_error.log` (6.4MB).
- 🐛 تبعية غائبة: `deep_translator` مستورد في `api_server.py:242` وغير مذكور في `requirements.txt` — انكسار `/translate-search` على بيئة نظيفة (يسقط لقاموس بديل).
- 📅 **جدول زمني من التواريخ** (اليوم 2026-10-18): آخر كتابة `daemon.log` = **2026-04-12** و`daemon_error.log` = 2026-05-01 → الخلفية الصامتة بلا نشاط مسجل منذ ~6 أشهر؛ آخر حركة نقل فعلية عبر جسر Flask = `elnagar_move.log` بتاريخ **2026-09-18** (الجسر/الواجهة مستخدمان حديثًا بينما الدمغة الصامتة متوقفة أو بلا مخرجات).
- ⚠️ `swagger.json` = **0 بايت** (فارغ منذ 2026-03-20) — تنزيل فاشل.
- ⚠️ تكرار الخطِر: قاموس `NAME_RULES` مكرر حرفيًا في سكربتين؛ نسختا الواجهة (userscript 791 سطرًا vs `elnagar_web/inject.js`) **مختلفتان تمامًا** (بصمات SHA256 مختلفة) — انحراف مؤكد.
- ⚠️ `CORS(origins="*")` على جسر :5000 + نقطة `delete-assets` تحذف من القرص نهائيًا = سطح خطر محلي (أي صفحة مفتوحة بالمتصفح تستطيع النداء عليها).
- ⚠️ مسارات مثبتة جهازًا-محددًا داخل `_resolve_local_path`: مجلد طلبات CNC على H:، و`G:\Downloads\3.2025`، ومرجع مشروع قديم `G:\immich-app\library\library`.
- ✅ مرونة جيدة: `restart: always` + healthchecks؛ الـ watcher يبتلع ConnectionError؛ الدمغة تحفظ التقدم كل دفعة؛ `brain_log.json` محدود بـ 1000 إدخال.
- ✅ أثر تشغيل حقيقي: `__pycache__`، سجل نقل حتى 2026-09-18، وسجلات نشاط ممتدة.
- ✅ تصميم ذكي موثق: إعادة استخدام متجهات Immich (export → build FAISS) وكاش متجهات على القرص.
- ℹ️ `.venv` حُذفت بأمر المالك (كانت 1.01GB) وتتجدد تلقائيًا عند التثبيت؛ لم تُفتح أي صورة أو بيانات مستخدم خلال الدراسة.

## 9) خريطة دخول للتطوير
1. **أول خطوة تنظيف موصى بها**: توحيد `NAME_RULES` في وحدة مشتركة + نقل المفتاحين إلى `.env` وتدويرهما + إضافة `deep-translator` إلى requirements + إصلاح `asset_id_map` في `brain.py:237`.
2. **مجلدات الفحص/الوجهة**: `elnagar_ai/data/user_settings.json` (target_folders / move_destination) أو CLI خيار 9 — دون تعديل كود.
3. **قواعد التصنيف بالأسماء**: `NAME_RULES` (في السكربتين) — يُستخرج لوحدة مشتركة.
4. **الفئات الذكية zero-shot**: `CATEGORY_MAP` في config.py (تولّد ZERO_SHOT_LABELS تلقائيًا).
5. **خط أنابيب التصنيف الكامل**: `brain.run_full_pipeline()` — رفع → تحليل CLIP → تصنيف (classification_engine) → تسمية (naming_engine) → ألبومات (album_manager).
6. **إعادة بناء فهرس البحث**: `export_embeddings.py` (تصدير من postgres داخل الحاوية) ثم `build_faiss.py` — يُنتج `faiss_index.bin` + `.meta.json`.
7. **نقاط نهاية الواجهة**: `api_server.py` (Flask :5000) — كل ما تستدعيه الواجهة المحقونة.
8. **الواجهة**: `elnagar_web/inject.js` (تُخدَم فورًا عبر nginx) — وانتبه أنها نسخة مختلفة عن `immich_elnagar_injector.user.js`؛ أي تعديل يلزم في الاثنتين أو توحيدهما.
9. **التشغيل من الصفر**: `launcher.py` (أو `Start_Elnagar_Server.bat`) — ويتجدد `.venv` عند أول `pip install -r elnagar_ai/requirements.txt`.
10. **لفهم أي محرك غير مقروء**: نداءاته موثقة داخل `brain.py` و`api_server.py` (قائمة الدوال أعلاه) — ملفاته صغيرة (3-13KB) ويمكن قراءتها لاحقًا ضمن ميزانية جديدة.

## 10) فهرس الملفات المهمة
| الملف | دوره | ملاحظة |
|---|---|---|
| immich_elnagar_sync.py | مزامنة شاملة لمرة واحدة (تصنيف بالأسماء → ألبومات) | ✅ مقروء. مفتاح API مضمّن سطر 8 — يُنقل للـ .env ويدور |
| immich_elnagar_watcher.py | مراقب دوري كل 5 دقائق للأصول الجديدة | ✅ مقروء. تتبع synced_assets.json؛ تكرار قواعد sync حرفيًا |
| docker-compose.yml | 5 خدمات: server/ML/valkey/postgres + elnagar-proxy (nginx:80) | ✅ مقروء. يركّب D:/G:/H:/I للقراءة فقط |
| elnagar_ai/requirements.txt | 14 مكتبة: torch/open-clip/faiss-cpu/hdbscan/flask | ✅ مقروء. بلا تثبيت إصدارات؛ ينقصه deep-translator |
| elnagar_ai/config.py | مركز التكوين: مسارات + CATEGORY_MAP + عتبات + مفتاح API | ✅ مقروء. مفتاح ثانٍ مختلف سطر 30 |
| elnagar_ai/brain.py | المنسّق المركزي (732 سطرًا): pipeline + نقل + تعلم خفي | ✅ مقروء. خطأ asset_id_map سطر 237 |
| elnagar_ai/api_server.py | جسر Flask :5000 للواجهة — 12+ نقطة نهاية | ✅ مقروء. CORS مفتوح؛ يستورد deep_translator غير المصرّح بها |
| elnagar_ai/vision_engine.py | CLIP تضمينات + zero-shot + كاش npy؛ BLIP معطل | ✅ مقروء |
| elnagar_ai/launcher.py | مشغّل تلقائي 3 خطوات (Docker → compose → daemon+api_server) | ✅ مقروء. يدعم --silent-startup |
| elnagar_ai/daemon.py | خلفية دائمة: move_worker/30ث + حلقة 5 دقائق (وضع خفيف) | ✅ مقروء. مصدر daemon.log الضخم |
| elnagar_ai/run.py | CLI تفاعلي rich — 10 خيارات فوق Brain | ✅ مقروء |
| build_faiss.py | بناء faiss_index.bin من immich_embeddings.csv | ✅ مقروء. IndexFlatIP بعد تطبيع |
| export_embeddings.py | تصدير جدول smart_search من postgres بالحاوية إلى CSV | ✅ مقروء. 17 سطرًا — استغلال ذكي لمتجهات Immich |
| immich_elnagar_injector.user.js | سكربت Tampermonkey v1.2: التقاط تحديد + بحث سياقي + أزرار نقل | ✅ مقروء جزئيًا (110/791 سطرًا — العنوان والآلية) |
| .env (أسماء المفاتيح فقط) | UPLOAD_LOCATION, DB_DATA_LOCATION, TZ, IMMICH_VERSION, DB_PASSWORD, DB_USERNAME, DB_DATABASE_NAME, IMMICH_HOST | ✅ قُرئت الأسماء فقط؛ القيم سرية |
| elnagar_web/inject.js + style.css | نسخة الواجهة المخدومة عبر nginx | بالاسم + بصمة SHA256 (مختلفة عن userscript) |
| nginx.conf | بروكسي elnagar-proxy (يُفترض: /elnagar ثابت + /elnagar-api → :5000) | بالاسم (2.3KB) |
| elnagar_ai/{classification_engine,search_engine,album_manager,filesystem_engine,naming_engine,upload_engine,active_learning}.py | المحركات السبعة | بالاسم + أدوارها موثقة من نداءات brain/api_server |
| download_model.py / download_ui.py | تنزيل نماذج/واجهة | بالاسم |
| Run_Elnagar.bat / Start_Elnagar_Server.bat / *.vbs | مشغّلات Windows ومهام إقلاع | بالاسم |
| data/postgres, data/model_cache, data/uploads | مخازن حية | لا تُقرأ (بيانات مستخدم حقيقية) |
