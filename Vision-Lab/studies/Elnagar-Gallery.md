# 🏗️ ملخص معماري: Elnagar Gallery

> دراسة قراءة فقط أُنجزت بتاريخ 2026-10-18 — كل استنتاج أدناه يستند إلى ملف قرئ فعليًا (اسمه مذكور). لم يُنفَّذ أو يُعدَّل أي ملف داخل المشروع.

---

## 1) الغرض الوظيفي

معرض صور ذكي محلي (Local-First) متخصص في منتجات ورشة القص بالليزر: يفهرس تلقائيًا صور التصاميم وملفات الفكتور من مجلدات مراقَبة، ويصنّفها إلى 19 فئة عبر CLIP + قواعد أسماء، مع بحث دلالي عربي/إنجليزي، ومراجعة يدوية للتصنيفات الضعيفة، وتصدير الألبومات كمجلدات فعلية على القرص.

## 2) نقاط الدخول + طريقة التشغيل

| المدخل | الدليل | التشغيل |
|---|---|---|
| **main.py** — تطبيق Streamlit (المدخل الرئيسي) | `main.py:17-22` (page_config)، `main.py:12-13` (استيراد Brain وWatcher) | `streamlit run main.py` — عبر `run_app.bat` الذي يفعّل `venv` ثم يشغّله |
| **Docker** | `Dockerfile:62` (`CMD ["streamlit", "run", "main.py"]`)، منفذ 8501 | `docker-compose up -d` (يبنى من python:3.11-slim مع healthcheck) |
| **تشغيل الحارس منفردًا** | `logic/watcher.py:174-181` (`if __name__ == "__main__"`) | `python -m logic.watcher` أو `python logic/watcher.py` |
| **سكربتات تشخيص/اختبار** (لا تلزم لتشغيل المنتج) | `diagnose_ai.py`، `final_check.py`، `test_*.py` | تشغيل فردي بـ python |

ملاحظة تشغيل: `run_app.bat` يفترض مجلد `venv` بجذر المشروع — وهو موجود فعلًا (Python 3.14.0 حسب `venv/pyvenv.cfg`) وتثبيتاته كاملة.

## 3) الهيكل العام

```
G:\ai\Elnagar Gallery\            ← جذر مستودع Git (ملف التزام واحد: "Initial commit" 9b98d51، شجرة نظيفة)
├── main.py                       ← واجهة Streamlit كاملة (797 سطر، CSS مدمج، 4 شاشات)
├── logic/                        ← طبقة المحركات (6 ملفات .py، بلا __init__.py — namespace packages)
│   ├── brain.py                  ← المنسق الرئيسي ElnagarBrain
│   ├── ai_engine.py              ← محرك CLIP للتصنيف
│   ├── database_engine.py        ← غلاف ChromaDB + feedback
│   ├── album_engine.py           ← منطق الألبومات وعمليات القرص
│   ├── watcher.py                ← مراقبة المجلدات (watchdog)
│   └── processor.py              ← نسخة قديمة مونوليثية (غير مستخدمة من main.py)
├── db/                           ← مخزن ChromaDB الفعلي (ملتزم في Git!)
├── photos/                       ← مجلد المراقبة الافتراضي (6 صور jpg)
├── test/                         ← 3 نماذج ذكاء اصطناعي ~127MB (ONNX YuNet/SFace + InceptionV3 .pb) — لا يستوردها أي كود
├── venv/                         ← بيئة Python 3.14.0 مثبتة كاملة
├── settings.json، requirements.txt، Dockerfile، docker-compose.yml، run_app.bat، .gitignore، .dockerignore
└── (feedback.json)               ← غير موجود حاليًا؛ يُنشأ عند أول تدخل مستخدم (save_feedback)
```

استيراد `logic` يعتمد على `sys.path.insert` في `main.py:11` و`diagnose_ai.py:6` (لا توجد حزمة `__init__.py`).

## 4) الوحدات الرئيسية

تدفق البيانات: **Watcher → Brain → (AIEngine + DatabaseEngine + AlbumEngine) → UI**

| الوحدة | الملف | المسؤولية (بدليل) |
|---|---|---|
| `ElnagarBrain` | `logic/brain.py` | المُنسق الرئيسي: خط معالجة الملف (`process_image` س30)، دفعات (`process_batch` س142)، مسح مجلدات (`process_directory` س226)، إعادة تصنيف كامل (`reclassify_all` س282)، بحث نصي دلالي (`search` س409)، بحث بالتشابه البصري (`search_similar` س417)، تجاوزات المستخدم (`override_category` س359)، واجهة الحذف من القرص (`delete_from_disk` س453) |
| `AIEngine` | `logic/ai_engine.py` | التصنيف: CLIP نصي متعدد اللغات (ViT-B-32-multilingual) + CLIP صوري (ViT-L-14 مع fallback إلى B-32، س301-306)، 19 فئة × 8 قوالب وصف عربي/إنجليزي (`CATEGORY_TEMPLATES` س17-218)، قواعد أسماء (`NAME_RULES` س223-288)، كشف مستندات heuristic بنسبة البياض والحواف (`detect_document` س381)، تصيير SVG عبر cairosvg (`_render_svg` س361)، softmax بدرجة حرارة 0.08 وعتبة «متفرقات» 0.04 (`predict_category` س457-480) |
| `DatabaseEngine` | `logic/database_engine.py` | غلاف ChromaDB: `PersistentClient` مع fallback إلى API قديم `chroma_db_impl="duckdb+parquet"` (س44-60)، collection باسم `elnagar_gallery` (س62)، CRUD سجلات (المعرّف = المسار المطلق للملف)، استعلام تشابه، وتعطيل telemetry عبر monkey-patch لـ Posthog (س8-13) |
| `AlbumEngine` | `logic/album_engine.py` | تجميع الألبومات من قاعدة البيانات مع تطبيق overrides/rejected/aliases (`get_albums_summary` س21)، إحصاءات وحساب أحجام (`get_albums_stats` س87)، تنظيف المسارات المفقودة (س124)، **عمليات قرص فعلية**: تصدير copy/move مع منع الكتابة فوق موجود (س134-217)، حذف من القرص وقاعدة البيانات معًا (س219-240)، معلومات ملف (س268) |
| `ElnagarWatcher` | `logic/watcher.py` | مراقبة حية بـ watchdog للمسارات في `settings.json` (`load_settings` س88)، أحداث إنشاء/تعديل/حذف (س27-52)، إعادة محاولة 5 مرات كل 2 ثانية للملفات المقفولة (`process_with_retry` س54)، مسح شامل في thread خلفية (`scan_all_paths` س149)، monkey-patch لـ `print` ضد UnicodeEncodeError (س7-14) |
| `ElnagarProcessor` | `logic/processor.py` | **كود ميت**: نسخة مونوليثية قديمة (581 سطر) تدمج كل ما سبق. مستوردة فقط من ملفات `test_ai.py`، `test_engine.py`، `test_processor_init.py` — لا يستوردها `main.py` ولا `brain.py` (تحققت بـ grep على كل ملفات .py) |

واجهة المستخدم (`main.py`) أربع شاشات: 📂 الألبومات (تصفح/عرض fullscreen/تحديد متعدد/ترقيم صفحات 30)، 🔍 البحث الذكي، 🧐 المراجعة (تصنيفات بثقة منخفضة)، ⚙️ الإدارة (مسارات/مسح شامل/مسح كامل للقاعدة).

## 5) المكتبات (من requirements.txt فعلًا — 7 أسطر، بدون تثبيت إصدارات)

```
sentence-transformers   ← CLIP (نماذج النص والصورة)
chromadb               ← قاعدة المتجهات (المثبت فعليًا في venv: 0.3.23)
Pillow                 ← فتح/تصغير الصور والمصغرات
watchdog               ← مراقبة نظام الملفات
streamlit              ← إطار الواجهة (المثبت: 1.53.0)
streamlit-autorefresh  ← تحديث شريط التقدم الحي (st_autorefresh في main.py:255,272)
cairosvg                ← تصيير SVG قبل تحليل CLIP
numpy                  ← المتجهات وsoftmax
```

حقيقة venv (من عرض site-packages): مثبتات إضافية تُسحب تلقائيًا — torch 2.9.1+cpu، transformers 4.57.6، torchvision، streamlit-autorefresh 1.0.1، fastapi 0.125.0، duckdb، pydantic **مزدوج** (pydantic 1.10.26 + pydantic_core 2.41.5 معًا)، hnswlib 0.8.0. البيئة venv على Python 3.14.0 بينما Dockerfile يستخدم python:3.11-slim — تفاوت بيئتين يجب التنبه له.

## 6) مخازن البيانات

| المخزن | الموقع | المحتوى (بدليل) |
|---|---|---|
| **ChromaDB** | `db/` (chroma.sqlite3 ≈4.3MB + chroma-embeddings.parquet + chroma-collections.parquet + مجلد UUID لمؤشر HNSW + index/) | collection `elnagar_gallery`؛ معرّف السجل = المسار المطلق؛ metadata: `path, mtime, category, confidence, top_score, user_confirmed` (`logic/brain.py:123-130`)؛ embedding = بصمة CLIP. **ملاحظة**: كل ملفات الحالة هذه ملتزمة داخل Git (تحققت بـ git ls-files) |
| **feedback.json** | جذر المشروع (غير موجود حاليًا) | overrides (تصحيحات المستخدم الدائمة)، rejected، aliases لتسميات الألبومات (`logic/database_engine.py:18-31`) — يُنشأ عند أول override/alias |
| **settings.json** | جذر المشروع | `watch_paths` — حاليًا `["C:\\Users\\MASSAYA\\Downloads"]` أي جهاز مختلف عن جهاز التشغيل الحالي |
| **.thumbs/** | جذر المشروع (فارغ حاليًا) | كاش مصغرات باسم MD5 للمسار+الأبعاد (`main.py:182-198`) |
| **photos/** | جذر المشروع | 6 صور jpg باسم md5-like + `test_red.jpg` (مولدة من `create_dummy_image.py:8`) |
| **كاش موديلات CLIP** | خارج المشروع `~/.cache` (في Docker: volume باسم `elnagar-model-cache` — `docker-compose.yml:22-23,38-40`) | نماذج ViT-L-14/B-32 (~2GB حسب تعليق docker-compose) |
| **test/** | `test/` | نماذج ONNX/pb (~127MB) غير مستخدمة في أي كود — بقايا تجارب (لا يوجد أي import لها — تحققت بـ grep) |

## 7) نقاط التكامل

1. **نظام الملفات (الأعمق)**: watchdog recursive على كل watch_paths، os.walk للمسح الشامل، وعمليات قرص حقيقية: `shutil.move/copy2` و`os.remove` في `logic/album_engine.py` — الألبومات ليست مجرد تجميع منطقي بل تُصدَّر/تُحذف فيزيائيًا.
2. **Explorer في Windows**: `open_folder()` يستدعي `explorer.exe` عبر subprocess (`main.py:201-202`) — ربط بنظام التشغيل.
3. **HuggingFace Hub**: تنزيل نماذج CLIP تلقائيًا عند أول تشغيل (`SentenceTransformer(...)` في `ai_engine.py:298-302`) — الشبكة الوحيدة المطلوبة؛ بعد الكاش يعمل المشروع محليًا بالكامل.
4. **ChromaDB**: تعطيل telemetry صريح (env `ANONYMIZED_TELEMETRY=False` + monkey-patch لـ Posthog في `database_engine.py:5-13` و`processor.py:5-13` و`Dockerfile:10`).
5. **Docker volumes**: `db/`، `.thumbs/`، `settings.json`، `feedback.json`، ومجلد صور المضيف `C:/Users/MASSAYA/Downloads:/data/Downloads` (`docker-compose.yml:15-33`) — أي نسخة Docker تحتاج تعديل المسارات حسب الجهاز.
6. **لا توجد واجهات خارجية أخرى**: لا REST API، لا خدمات سحابية، لا قاعدة SQL تقليدية — التكامل كله محلي (يؤكد وصف «تصنيف محلي»).

## 8) تقييم الصحة

### ✅ قوة
- **فصل معماري واضح في النواة الحديثة**: Brain منسق، AI/DB/Album محركات متخصصة بذات معلنة في docstrings (`brain.py:14-19`، `database_engine.py:34-39`، `album_engine.py:5-9`).
- **خط قرار تصنيفي متعدد الطبقات ذكي**: override المستخدم → قواعد امتدادات/أسماء → كشف مستندات heuristic → CLIP ensemble، مع تخطي غير المتغير عبر mtime (`brain.py:30-139`).
- **أداء**: دفعات AI مجمعة (chunk 8/16) وfetch مفهرس في استدعاء واحد (`brain.py:236-276`)، كاش مصغرات، كاش ألبومات TTL 300s (`main.py:172-180`).
- **دفاعية (Defensive design)**: fallback موديل CLIP عند فشل ViT-L-14 (`ai_engine.py:301-306`)، fallback cairosvg، retry بالمراقب، fallback لنسختي ChromaDB API (`database_engine.py:44-60`)، و`final_check.py` لفحص توافق pydantic/chromadb/streamlit.
- **حلقة تعلم من المستخدم**: overrides دائمة في feedback.json + شاشة مراجعة للثقة المنخفضة + إعادة تصنيف ذكي — كلها في UI مباشرة.
- **جاهزية نشر**: Docker كامل مع healthcheck على `/_stcore/health` (`Dockerfile:58-59`).

### 🧱 ديون تقنية
1. **`logic/processor.py` كود ميت مكرر** (581 سطر): نسخة قديمة من كل شيء، لكنها تعمل على **نفس collection** `elnagar_gallery` (`processor.py:213`) وتستوردها 3 ملفات test_* فقط — خطر تشويش وتلوث بيانات.
2. **requirements.txt بلا تثبيت إصدارات**: كل سطر اسم مجرد؛ والمثبت chromadb **0.3.23** قديم جدًا مقارنة بـ API الحديث (PersistentClient) — الكود يحمل fallbackين لسد الفجوة (`database_engine.py:44-60`)، لكن أي `pip install -r` جديد على Python حديث سيسحب chromadb حديثًا ويغيّر السلوك.
3. **`logic/` بلا `__init__.py`** مع الاعتماد على `sys.path.insert` في كل نقطة دخول — هش إذا تغير مجلد التشغيل.
4. **main.py مونوليث UI**: 797 سطرًا تخلط العرض والمنطق والCSS (~130 سطر CSS مدمج س27-156).
5. **استثناءات صامتة واسعة**: bare `except:` متكرر (مثل `main.py:280-281`، `brain.py:137-139`، `processor.py:347-348`) يعقّد تشخيص الأخطاء.
6. **バイナries داخل Git**: التزام «Initial commit» يضم 3 نماذج ذكاء اصطناعي غير مستخدمة (~127MB في test/) **وحالة ChromaDB كاملة** (parquet + مؤشرات HNSW + pkl — تحققت بـ git ls-files) بينما .gitignore لا يستثني test/ ولا db/*.parquet.
7. **تفاوت البيئات**: venv على Python 3.14.0 بينما Docker على 3.11، وpydantic مثبت بنسختين متعارضتين (1.10.26 + core 2.41.5) داخل نفس البيئة.
8. **settings.json يحمل مسار جهاز آخر** (`C:\Users\MASSAYA\Downloads`) — يحتاج تعديلًا قبل أول تشغيل على هذا الجهاز.

### ⚠️ مخاطر (بدليل)
1. **حذف لا رجعة فيه من القرص بلا تأكيد في وضع الشبكة**: زر 🗑️ داخل كارت الصورة ينفذ `brain.delete_from_disk` فورًا (`main.py:507-509`) — يمر عبر `os.remove` (`album_engine.py:219-240`). تأكيد نصي موجود فقط لمسح القاعدة بالكامل (`main.py:774-786`)، وليس لحذف الملفات الفردية.
2. **قاعدة البيانات بلا نسخ احتياطي + مسح كامل من UI**: `wipe_database()` يحذف الـ collection ويعيد إنشاءها (`database_engine.py:133-143`)؛ زرها في شاشة الإدارة محمي بتأكيد نصي فقط، والحالة ملتزمة في Git مرة واحدة (لقطة قديمة بمرور الوقت).
3. **feedback.json بلا حماية**: تصحيحات المستخدم الدائمة (overrides/aliases) كلها في ملف JSON واحد يُكتب كاملًا في كل تعديل (`save_feedback` في database_engine.py:29-31) — لا قفل ولا نسخ؛ فقدانه = فقدان كل تعلم المستخدم.
4. **خطأ دفعي يعطي ثقة زائفة 100%**: فشل `predict_batch` يعيد `[("متفرقات", 1.0, 1.0)]` (`ai_engine.py:453-455`) — ملفات كثيرة قد تدخل «متفرقات» بثقة كاملة فتغيب عن شاشة المراجعة (التي تفرز حسب confidence — `brain.py:390-407`).
5. **سباق كتابة الملفات**: `on_modified` قد يمسك ملفًا أثناء الكتابة؛ فحص `getsize>0` لا يضمن الاكتمال (`watcher.py:54-74`) — قد يُصنّف الملف الناقص ويبقى التصنيف حتى تغيّر الـ mtime أو reclassify يدوي.
6. **اختبارات تلوث الإنتاج**: `test_ai.py`/`test_engine.py`/`test_processor_init.py` تستخدم `ElnagarProcessor` ضد نفس collection وdb/ الفعلي — تشغيلها هنا سيعيد تنزيل/تحميل الموديلات ويكتب في قاعدة الإنتاج.
7. **مراقبة واسعة النطاق**: المسار الافتراضي في settings هو مجلد Downloads كامل بمراقبة recursive (`watcher.py:119`) — كل صورة تُحمَّل تُؤرشف وتُصنّف تلقائيًا.

## 9) جاهزية التطوير — خريطة دخول للوكيل

**الترتيب المقترح للقراءة (ساعة واحدة تكفي):**
1. `main.py:1-30` ثم `logic/brain.py` كاملًا — يكشفان 90% من البنية (من يستدعي من، وماهية المخازن).
2. `logic/ai_engine.py:17-296` — فئات التصنيف وقواعد الأسماء (قلب المنتج).
3. `logic/database_engine.py` (قصير) ثم `logic/album_engine.py` عند الحاجة لعمليات القرص.

**قواعد ذهبية قبل أي تعديل:**
- **لا تعتمد على `processor.py`**: main يستخدم `ElnagarBrain` فقط (`main.py:12-13`). أي تطوير يبدأ من brain/ai_engine. اعتبر processor.py أرشيفًا.
- **إضافة فئة جديدة** = تحديث متزامن في 3 أماكن: `CATEGORY_TEMPLATES` في `ai_engine.py:17-218` (8 قوالب عربي/إنجليزي على الأقل) + قاموس `ICONS` في `main.py:296-300` + (اختياري) `NAME_RULES` في `ai_engine.py:223-288`. الفئة بلا أيقونة تسقط إلى 📁.
- **المعرّف في DB = المسار المطلق للملف** (`brain.py:36`) — أي منطق نقل/إعادة تسمية يجب أن يحدّث السجل وإلا صار مسارًا مفقودًا (تُنظف من زر «تنظيف المسارات المفقودة»).
- **collection واحدة باسم `elnagar_gallery`** مشتركة بين النواة الحديثة وprocessor القديم — لا تشغّل سكربتات test_* على جهاز الإنتاج قبل عزل db.
- **متطلبات التشغيل هنا**: venv جاهز كامل (Python 3.14 + torch cpu)؛ عدّل أولًا `settings.json` لمسارات هذا الجهاز، أو أضف المسارات من شاشة الإدارة بالواجهة.
- **تشغيل آمن للتجربة**: `streamlit run main.py` من الجذر (لأن sys.path وsettings.json وfeedback.json نسبية لمجلد التشغيل — `watcher.py:90`، `main.py:211`).
- **أول تشغيل بطيء**: تنزيل نماذج CLIP من HuggingFace (~2GB) — بعدها محلي تمامًا.
- **لا تجدد تثبيتات pip بهجينة**: `pip install -r requirements.txt` على بيئة جديدة سيسحب chromadb حديثًا — الكود محصّن بـ fallback لكن اختبر `DatabaseEngine` بعده (`final_check.py` جاهز لهذا الغرض).

**ما يحتاجه المشروع ليصبح جاهزًا للنقل/التطوير المستمر (بالترتيب):** عزل `test/` و`db/` عن Git وتثبيت إصدارات في requirements.txt → إزالة/أرشفة `processor.py` → فصل `__init__.py` → تقييد استثناءات bare except → إضافة تأكيد قبل حذف الملفات الفردية.

## 10) فهرس الملفات المهمة

| الملف | دوره | أبرز ما يلزم معرفته |
|---|---|---|
| `main.py` | واجهة Streamlit الكاملة (4 شاشات، 797 سطر) | مونوليث UI+CSS؛ sys.path.insert س11؛ كل الأزرار تنادي brain مباشرة؛ استدعاء explorer.exe س201 |
| `logic/brain.py` | المُنسق الرئيسي ElnagarBrain | خط المعالجة والدفعات والبحث والتشابه وoverride؛ الـ metadata يتشكل هنا س123-130 |
| `logic/ai_engine.py` | محرك التصنيف CLIP | 19 فئة ×8 قوالب؛ NAME_RULES؛ ViT-L-14 + fallback B-32؛ detect_document heuristic؛ SVG عبر cairosvg؛ عتبة متفرقات 0.04 |
| `logic/database_engine.py` | غلاف ChromaDB + feedback.json | fallback API قديم/جديد؛ collection `elnagar_gallery`؛ تعطيل telemetry؛ ملف feedback خارج Git |
| `logic/album_engine.py` | الألبومات + عمليات القرص الحقيقية | امتدادات الملفات المرجعية هنا س11-12؛ export copy/move بمنع overwrite؛ حذف من القرص س219 |
| `logic/watcher.py` | المراقبة الحية watchdog | retry 5×2s؛ scan في thread؛ monkey-patch لprint؛ له `__main__` مستقل |
| `logic/processor.py` | ⚠️ نسخة قديمة ميتة (581 سطر) | يستوردها test_* فقط؛ تعمل على نفس collection — لا تطور فيها |
| `requirements.txt` | 7 مكتبات، بلا تثبيت إصدارات | chromadb الفعلي المثبت 0.3.23 — انتبه عند إعادة التثبيت |
| `settings.json` | مسارات المراقبة | يشير لمجلد Downloads على جهاز آخر (MASSAYA) — عدّله قبل التشغيل |
| `Dockerfile` + `docker-compose.yml` | نشر الحاوية | python:3.11، منفذ 8501، healthcheck، volumes للبيانات + كاش موديلات ~2GB |
| `run_app.bat` | تشغيل Windows بخطوة واحدة | يفعّل venv\ ثم streamlit run main.py — يجب التشغيل من جذر المشروع |
| `test_ai.py` / `test_engine.py` / `test_processor_init.py` | اختبارات المعالج القديم | ⚠️ تكتب في db الإنتاج — لا تشغّلها بجهاز العمل |
| `test_settings.py` | اختبار تحميل إعدادات watcher | يكتب/يحذف settings.json مؤقتًا أثناء التشغيل (س11-14, 30-33) |
| `diagnose_ai.py` | تشخيص: تهيئة brain + reclassify_all | سكربت console بترميز UTF-8 قسري |
| `final_check.py` | فحص توافق بيئة (pydantic/chromadb/streamlit) | يكشف مشكلة pydantic v1/v2 المعروفة مع chromadb |
| `create_dummy_image.py` | توليد صورة اختبار حمراء | يكتب في photos/test_red.jpg |
| `db/` | قاعدة ChromaDB الفعلية (4.3MB sqlite + parquet + مؤشر HNSW) | حالة ملتزمة في Git — لقطة قديمة تتضخم مع كل التزام |
| `photos/` | مجلد المراقبة الافتراضي | 6 صور؛ مُستثنى من Git |
| `test/` | نماذج ONNX/pb ~127MB | غير مستوردة في أي كود (بقايا تجارب سابقة) لكنها داخل Git |
| `venv/` | Python 3.14.0 مثبتة كاملة | torch 2.9.1+cpu، chromadb 0.3.23، streamlit 1.53.0، pydantic مزدوج |

---

*عدد ملفات المصادر التي قُرئت فعليًا بالكامل: 21 ملفًا (14/14 ملف Python + 7 ملفات إعداد/دعم). لم يُقرأ من venv سوى pyvenv.cfg وقائمة site-packages (قراءة فقط)، ولم تُفتح الملفات الثنائية (صور/nnx/sqlite).*
