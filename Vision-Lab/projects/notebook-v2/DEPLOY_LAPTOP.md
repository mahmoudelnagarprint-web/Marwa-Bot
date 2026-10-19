# 💻 تحديث اللابتوب — أفكاري v2 (Surface Pro 4)

> **الأمر المباشر من المالك:** «ولا تنسه تحديث النوت ع الاب توب».
> هذا الملف هو خطوات تنفيذ ذلك الأمر — على جهاز اللابتوب، مرة واحدة.

---

## 0. الحقائق المثبتة قبل البدء (لا تفترض، هذه مقيسة)

| الحقيقة | القيمة | كيف عرفنا |
|---|---|---|
| مسار اللابتوب | `G:\Marwa-Bot` | `STATUS.md` 2026-10-16: «المستودع مستنسخ في `G:\Marwa-Bot`» |
| مسار الورشة | `G:\ai\Naggar Print POS Agent` | هذا الجهاز — فيه `Vision-Lab/projects/notebook-v2/` |
| آلية النقل | **git autosync** — الورشة ترفع كل ≤15 دقيقة | `scripts/git_autosync.py --loop --interval 900`، واللوق يثبت الرفع |
| المستودع | `github.com/mahmoudelnagarprint-web/Marwa-Bot` (خاص) | `git remote -v` |
| الفرع | `main` | `git rev-parse --abbrev-ref HEAD` |
| `notebook-v2/` مُتتبَّع؟ | **نعم** — الـ44 ملف كلهم داخل Git | `git ls-files --error-unmatch .../nb/db.py` نجح |
| `NODE_ID` على اللابتوب | **`LAPTOP`** | `config.py:56` — الافتراضي `LAPTOP` أصلًا، و`.env` غير موجود بيخليه كده |
| دور اللابتوب | **`surface_laptop`** (غطاء/standby) | `config.py:57-58` |
| `LAPTOP_SECRET_KIT.md` | موجود في المستودع **ومحمي بـ`.gitignore`** | لا يُرفع أبدًا — يُنقل يدويًا |

**نتيجة مهمة:** ولا ملف واحد محتاج نقل يدوي للأكواد. `git pull` واحد بيكفي. الحاجة الوحيدة اللي **مش** بتيجي بـgit هي `.env` (لأنه محمي أصلًا — وده صح).

---

## 1. تحديث الكود (على اللابتوب)

```powershell
cd G:\Marwa-Bot

# 1) تأكد إن مفيش تعديلات محلية هتتعارض (لو فيه: ارفعها أو اتراجع عنها الأول)
git status --short

# 2) اسحب آخر نسخة
git pull origin main

# 3) تأكد إنك فعلاً جبت نسخة أفكاري الجديدة
Test-Path .\Vision-Lab\projects\notebook-v2\nb\persona.py
Test-Path .\Vision-Lab\projects\notebook-v2\nb\intent.py
Test-Path .\Vision-Lab\projects\notebook-v2\scripts\dsh_bridge.py
```

التلاتة لازم يكونوا `True`. لو أي واحد `False` → السحب لسه ماوصلش النسخة الجديدة، استنى دورة المزامنة أو `git pull` تاني.

---

## 2. مزامنة القاعدة (قبل التشغيل — إلزامي)

القاعدة **واحدة ومشتركة** (Supabase) — اللابتوب مايحتاجش نسخ بيانات. بس محتاج يتأكد إن السكيمة محدّثة:

```powershell
cd G:\Marwa-Bot\Vision-Lab\projects\notebook-v2

# .venv على اللابتوب — لو مش موجود:
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# فحص السكيمة (قراءة فقط — بلا أي كتابة)
.\.venv\Scripts\python.exe db\migrate.py --check
```

`--check` لازم يرجّع كل الجداول المطلوبة ومنها الجديد: **`conversations`**.
لو ناقص، طبّق الترحيل:

```powershell
.\.venv\Scripts\python.exe db\migrate.py
```

> الترحيل **idempotent** — تشغيله مرتين ما يكسرش حاجة. ولو اللابتوب لقى القاعدة لسه فاضية، `start_node.py` بيطبّقه تلقائيًا (سطر 37-41).

---

## 3. متغيّرات البيئة

`.env` **مش** جاي مع git (محمي — وده صح). على اللابتوب محتاج:

```powershell
# تحقق: هل .env موجود وعلى أي هوية؟
Get-Content G:\Marwa-Bot\.env | Select-String '^NODE_ID'
```

- **لو `.env` موجود** وفيه `NODE_ID="LAPTOP"` → تمام، ما تعملش حاجة.
- **لو `.env` مش موجود** → استعمله من `LAPTOP_SECRET_KIT.md` (اللي جاي من الورشة يدويًا — فلاش/واتساب لنفسك):

```powershell
# من داخل G:\Marwa-Bot — يبني .env من خزينة العقل السحابية، وبيحط NODE_ID=LAPTOP تلقائيًا
python tools\laptop_sync.py --restore-env
```

> `--restore-env` بيرفض يستبدل `.env` موجود إلا بـ`--force`. ده مقصود.
> **⚠️ `LAPTOP_SECRET_KIT.md` ممنوع يترفع على أي مستودع أو سحابة — وبعد الزرع امسحه من مصدر النقل.**

### المفاتيح الجديدة اللي ممكن تحتاجها على اللابتوب

افتح `G:\ai\Naggar Print POS Agent\Vision-Lab\projects\notebook-v2\.env.example` على الورشة وشوف الأسماء.
القيم الحقيقية في `.env` الجذر. أهم الجديد:

| الاسم | معناه | لو ناقص |
|---|---|---|
| `AI_VAULT_MASTER_KEY` | فتح تشفير مفاتيح الـAI | اللابتوب مش هيقدر يفك تشفير مفاتيح المزودين — **نفس المفتاح لازم يكون على الجهازين** وإلا التشفير ما يتقريش |
| `TELEGRAM_AFKARY_TOKEN` | توكن @Afkary22Bot | البوت مش هيشتغل خالص |
| `NB2_DB_URL` أو `POOLER_URL` | القاعدة المشتركة | مفيش عقل مشترك |
| `OWNER_TELEGRAM_ID` | `561770354` | `0` = البوت يرفض الجميع (fail-closed) |

**`AI_VAULT_MASTER_KEY` مهمة بالذات:** لو الورشة شفّرت مفتاح مزود بمفتاح رئيسي، واللابتوب عنده مفتاح رئيسي **تاني**، اللابتوب هيفشل يفك التشفير وهيرجع للقواعد المحلية بصمت. **لازم نسخة واحدة على الجهازين.**

---

## 4. التشغيل

```powershell
cd G:\Marwa-Bot\Vision-Lab\projects\notebook-v2
.\.venv\Scripts\python.exe scripts\start_node.py
```

المتوقع في اللوج:

```
[LAPTOP] العقدة LAPTOP (Surface Pro 4) بدأت — القلب النابض يعمل
```

**وسلوكه الصح:** اللابتوب **مايشغّلش** البوت طالما الورشة قائدة. ده مش عطل — ده التصميم:

```
[LAPTOP] العقدة LAPTOP (Surface Pro 4) بدأت
   (بلا سطر «⚡ حصلت على عقدة القيادة»)   ← الورشة قائدة، اللابتوب غطاء
```

لو اللابتوب شغّل البوت **أثناء** الورشة شغّالة، معنى كده الورشة فقدت الإيجار. **اتنين poller على نفس التوكن = خطأ 409** (موثق في STATUS.md) — فلو حصل ده، شوف الورشة الأول.

---

## 5. التحقق — إثبات إن اللابتوب بقى جزء من المنظومة

### 5.1 اللابتوب مسجّل في القاعدة؟

من أي جهاز (استعلام قراءة فقط):

```sql
SELECT node_id, role, last_seen, now() - last_seen AS age FROM nodes ORDER BY last_seen DESC;
```

**قبل التحديث:** صف واحد بس (`WORKSHOP`).
**بعد التحديث:** لازم يظهر **`LAPTOP`** بـ`age` أقل من ~20 ثانية.
لو ظهر `WORKSHOP` بس → اللابتوب مش شغّال أو `config` فشل.

### 5.2 جسر الـDSH شغّال على اللابتوب؟

```powershell
cd G:\Marwa-Bot\Vision-Lab\projects\notebook-v2
.\.venv\Scripts\python.exe scripts\dsh_bridge.py status --json
```

### 5.3 نفس البيانات من التلاتة (اختبار الباريتي)

المطلوب: **نفس** الصفوف من اللابتوب، ومن الورشة، ومن البوت.
```powershell
.\.venv\Scripts\python.exe scripts\dsh_bridge.py list --json
```
قارن الناتج مع `http://<الورشة>:8110/` — لازم يطابقوا. ده الاختبار الحقيقي لمصدر الحقيقة الواحد.

### 5.4 الواجهة شغّالة؟

```powershell
(Invoke-WebRequest 'http://127.0.0.1:8110/health' -UseBasicParsing -TimeoutSec 8).Content
```

---

## 6. اختبار الفيلوفر الحقيقي (اختياري — بعد إذن المالك)

**ده بيقطع البوت مؤقتًا، فمتعملهوش إلا بموافقة المالك وبوقت هادي.**

1. على الورشة: أوقف العقدة بـ`Ctrl+C` (إيقاف مرتب — بيسلّم القيادة).
2. على اللابتوب: خلال **≤45 ثانية** لازم اللوج يقول:
   ```
   [LAPTOP] ⚡ حصلت على عقدة القيادة — تشغيل بوت @Afkary22Bot + المحرك الاستباقي
   ```
3. ابعت رسالة للبوت — لازم يرد.
4. رجّع الورشة: `start_node.py` تاني. الورشة أو اللابتوب هي تجدد الإيجار — المهم **بوت واحد بس** بيشتغل في أي لحظة.

**الفشل المتوقع لو اللابتوب ما التقطش القيادة في 45 ثانية:**
- اللابتوب واقف → شغّله.
- اللابتوب شغّال بس ما التقطش → شوف لوج اللابتوب: `خطأ HA: ...`. أشهر سبب: **الاتصال بالقاعدة بيفشل من اللابتوب** (شبكة/`sslmode`/الـpooler).

---

## 7. تحديث اللابتوب تلقائيًا من دلوقتي (اختياري)

عشان ما تنساش تاني — خلي المزامنة تعمل لوحدها:

```powershell
$py = "G:\Marwa-Bot\Vision-Lab\projects\notebook-v2\.venv\Scripts\pythonw.exe"
$script = "G:\Marwa-Bot\scripts\start_node.py"

schtasks /Create /TN "Afkary_Laptop_Autosync" /SC MINUTE /MO 15 /F `
  /TR "\"$py\" \"$script\""
```

> ⚠️ **انتبه:** ده **مش** نفس حزمة `install_services.ps1` (اللي بتثبّت `MarwaBot_NotebookV2` + `MarwaBot_SyncV2`). النسختين مع بعض = عمليتين على نفس المنفذ.
> `start_node.py` بيحمي نفسه: لو المنفذ 8110 مشغول بيخرج بهدوء بلا تشغيل نسخة تانية (سطر 65-67). **بس متشغّلش الاتنين.**
> على الورشة، حزمة `install_services.ps1` **مش مثبّتة** حاليًا (`schtasks /Query /TN MarwaBot_NotebookV2` → غير موجودة) — العقدة شغّالة يدويًا. لو قررت تثبّتها على أي جهاز، ثبّتها على **جهاز واحد** بس، وسيب التاني يدوي أو بـautosync.

---

## 8. الملفات اللي بتتحدّث على اللابتوب

| الملف | إيه اللي بيتغير |
|---|---|
| `nb/persona.py` | **جديد** — شخصية «فوفا» واسم «أفكاري» |
| `nb/intent.py` | **جديد** — بوابة النوايا (أهم إصلاح: «هاي» مش بتتحفظ) |
| `nb/cache.py` | **جديد** — كاش داخلي 45ث |
| `nb/bridge.py` | **جديد** — الجسر الموحد |
| `scripts/dsh_bridge.py` | **جديد** — CLI للـDSH |
| `nb/db.py` | `dashboard()` + محادثات + أداء |
| `nb/bot.py` | الأزرار + بوابة النوايا |
| `nb/web.py` + `templates/` + `static/` | واجهة RTL Glassmorphism |
| `nb/ai_router.py` + `nb/providers.py` | إصلاح التفكير + التعافي |
| `nb/ha.py` | تصلّب التوفّر العالي |
| `db/schema_pgvector.sql` | `conversations` + المفاتيح الأجنبية |

---

## 9. لو حصلت مشكلة

| العرض | السبب المرجّح | الحل |
|---|---|---|
| `ModuleNotFoundError: psycopg2` | بتستعمل `python` العام مش `.venv` | استعمل `.\.venv\Scripts\python.exe` |
| `UnicodeEncodeError: 'charmap'` | طباعة عربي على كونسول ويندوز | مش عطل حقيقي — شغّل من PowerShell، أو استعمل `--json` |
| اللابتوب مش ظاهر في `nodes` | العقدة واقفة أو القاعدة مش موصولة | شوف لوج اللابتوب |
| الاتنين بيسحبوا تليجرام (409) | الورشة فقدت الإيجار واللابتوب خده | طبيعي في الفيلوفر — بس اتأكد إن واحد بس شغّال |
| اللابتوب بيرد بقواعد محلية بس | `AI_VAULT_MASTER_KEY` مختلف بين الجهازين | اتأكد إن المفتاح الرئيسي **نسخة واحدة** على الجهازين |
| الواجهة بطيئة | كاش 45ث لسه ما اشتغلش / أول تحميل | تاني تحميل لازم يبقى أسرع |

---

## 10. آخر خطوة — أعِد الذاكرة

بعد ما اللابتوب يقوم، ادفع الذاكرة عشان الورشة تعرف:

```powershell
python tools\laptop_sync.py --push-brain
```

---

*آخر تحديث: 2026-10-19 · الورشة (NODE_ID=WORKSHOP) · الفريق: فيجن + راصد + الـLead*
