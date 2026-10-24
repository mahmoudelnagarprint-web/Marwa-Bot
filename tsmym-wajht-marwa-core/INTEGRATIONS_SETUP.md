# 🔐 دليل إعداد التكاملات الخارجية — Google + Canva
## MARWA CORE task-6 (أمر المالك 2026-10-24) — ربط الوكلاء بالعالم الخارجي عبر OAuth 2.0

> **الهدف:** تمكين الوكلاء (فارس/سلمى/كوكو/بيبو) من العمل نيابة عنك: إنشاء جداول، جدولة مواعيد تسليم، قراءة إيميلات، توليد تصميمات — **دون تدخلك في كل مرة** (رموز التحديث تُجدد تلقائياً).
> **القاعدة الأمنية الذهبية:** رموز الوصول والتحديث **تُحفظ مشفرة (AES-256-GCM) في خزنة السيرفر فقط** (`.integrations/tokens.enc` — gitignored) ولا تمر عبر الواجهة ولا تُعرض أبداً.

---

## القسم 1 — Google Cloud Console (Sheets / Calendar / Gmail / Drive / Docs)

### الخطوة 1: إنشاء المشروع
1. افتح https://console.cloud.google.com وسجل بحساب جوجل الخاص بالورشة
2. من القائمة العلوي → **New Project** → الاسم: `Marwa-Core` → Create
3. تأكد أن المشروع الجديد مختار في الشريط العلوي

### الخطوة 2: تفعيل الـ APIs المطلوبة
من القائمة الجانبية → **APIs & Services → Library** → فعّل كل واحدة بالبحث عنها والضغط **Enable**:
- ✅ **Google Sheets API**
- ✅ **Google Calendar API**
- ✅ **Gmail API**
- ✅ **Google Drive API**
- ✅ **Google Docs API**

### الخطوة 3: شاشة الموافقة (OAuth Consent Screen)
1. **APIs & Services → OAuth consent screen** → User Type: **Internal** (لو حساب Workspace) أو **External** → Create
2. App name: `Marwa Core` • Email: بريدك • Logo: اختياري
3. **Scopes** → Add or Remove Scopes → أضف:
   ```
   https://www.googleapis.com/auth/spreadsheets
   https://www.googleapis.com/auth/calendar
   https://www.googleapis.com/auth/gmail.readonly
   https://www.googleapis.com/auth/drive.file
   https://www.googleapis.com/auth/documents
   ```
4. **Test users** → أضف بريدك (في وضع External/Testing — الحسابات المضافة فقط تستطيع الموافقة)

### الخطوة 4: إنشاء بيانات الاعتماد (Client ID + Secret)
1. **APIs & Services → Credentials → Create Credentials → OAuth client ID**
2. Application type: **Web application**
3. Name: `Marwa Core Web`
4. **Authorized redirect URIs** → أضف **بالضبط**:
   ```
   http://localhost:3000/api/integrations/callback/google
   http://192.168.1.15:3000/api/integrations/callback/google
   ```
   (السطر الثاني يسمح بالربط حتى لو فتحت الواجهة من الموبايل على الشبكة)
5. Create → انسخ **Client ID** و **Client Secret**

---

## القسم 2 — Canva Developer (Connect API)

1. افتح https://www.canva.com/developers/apps → **Create an app**
2. App name: `Marwa Core` → الاتفاقية → Create
3. من إعدادات التطبيق → **Authentication** → اختر **OAuth 2.0 + PKCE** (لا يحتاج client_secret في الواجهة — لكننا سنستخدم secret في التبادل السيرفري)
4. **App credentials** → انسخ **Client ID** و **Client Secret**
5. **Add an App → Connect API** (أو من خانة الـScopes): فعّل النطاقات:
   ```
   design:content:write    (إنشاء/تعديل تصاميم من القوالب)
   design:content:read     (قراءة التصاميم)
   asset:write             (رفع شعارات وصور الورشة)
   ```
6. **Redirect URLs** → أضف **بالضبط**:
   ```
   http://localhost:3000/api/integrations/callback/canva
   http://192.168.1.15:3000/api/integrations/callback/canva
   ```
7. احفظ — التطبيق في وضع Development يعمل لحسابك فقط (كافٍ تماماً)

> ⚠️ ملاحظة مراجعة Canva: التطبيقات في وضع Development تحتاج موافقة نشر فقط لو ستخدمها حسابات أخرى — لحسابك لا شيء إضافي.

---

## القسم 3 — Google Custom Search (البحث السريع — بلا OAuth)

1. https://programmablesearchengine.google.com → **Add** → المواقع للبحث: **البحث في الويب كله** (فعّل "Search the entire web") → Create
2. من إعدادات المحرك → انسخ **Search engine ID (cx)**
3. https://console.cloud.google.com/apis/library/customsearch.googleapis.com → Enable (نفس مشروع القسم 1)
4. **Credentials → Create Credentials → API key** → انسخ **API Key**
5. الحصص المجانية: 100 بحث/يوم مجاناً — تكفي بحث أسعار الخامات اليومي

---

## القسم 4 — إضافة المفاتيح إلى البيئة

1. افتح `G:\Marwa-Bot\tsmym-wajht-marwa-core\.env.local` وأضف:
```env
# ─── التكاملات الخارجية (OAuth) ───
GOOGLE_CLIENT_ID=xxxxxxxx.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-xxxxxxxxxxxx
CANVA_CLIENT_ID=xxxxxxxxxxxxxxxx
CANVA_CLIENT_SECRET=xxxxxxxxxxxxxxxx
GOOGLE_SEARCH_API_KEY=AIzaSyxxxxxxxx
GOOGLE_SEARCH_CX=xxxxxxxxxxxxxxxx
# مفتاح تشفير خزنة الرموز — أنشئه عشوائياً ولا تغيره بعد الربط (وإلا فك التشفير يفشل)
INTEGRATIONS_SECRET=<36+ حرفاً عشوائياً>
# الأصل الذي تعود إليه موجة OAuth (اتركه فارغاً = نفس أصل الطلب)
INTEGRATIONS_BASE_URL=
```
2. أنشئ السر العشوائي بأمر واحد في PowerShell:
```powershell
-join ((48..57)+(65..90)+(97..122) | Get-Random -Count 40 | ForEach-Object {[char]$_})
```
3. **أعد تشغيل السيرفر** (أو استخدم أداة الحارس) — متغيرات البيئة تُقرأ عند الإقلاع فقط
4. المفاتيح **لا تُرفع للمستودع إطلاقاً** — `.env.local` محمي بـgitignore (تحقق: `git check-ignore .env.local`)

---

## القسم 5 — الربط الفعلي (دقيقة واحدة لكل حساب)
1. افتح الواجهة → ⚙️ الإعدادات → قسم **🌐 التكاملات الخارجية**
2. اضغط **Connect to Google** → وافق على النطاقات → ستعود للواجهة بعلامة **متصل ✓**
3. اضغط **Connect to Canva** → وافق → **متصل ✓**
4. من هذه اللحظة الوكلاء يستخدمون الأدوات تلقائياً: الرموز تتجدد ذاتياً عند الانتهاء (قبل الانتهاء بدقيقتين) — **بدون أي تدخل منك**

---

## القسم 6 — الأمان (ماذا يحدث خلف الكواليس)
| العنصر | الحماية |
|---|---|
| Refresh Tokens | مشفرة **AES-256-GCM** بمفتاح مشتق من `INTEGRATIONS_SECRET` (scrypt) في `.integrations/tokens.enc` — gitignored + صلاحيات الملف 600 |
| الواجهة | ترى **حالة الاتصال فقط** (متصل/تاريخ انتهاء) — لا رموز إطلاقاً في أي استجابة |
| المتصفح | الكوكي (state/PKCE) HttpOnly قصير العمر (10 دقائق) بلا بيانات حساسة |
| الجداول السحابية | بديل موثق أدناه — جدول بسياسة RLS **deny-all حتى service_role** |
| الحذف | زر الفصل يمسح الرموز من الخزنة فوراً — ثم فصل الإذن من حساب جوجل/كانفا (App permissions) |

### البديل السحابي (عند توفير service-role key للعامل الخلفي)
جدول Supabase (يركبه راصد/مروة-الورشة فقط):
```sql
create table integrations_tokens (
  provider text primary key,
  tokens_enc text not null,          -- نفس التشفير: iv:tag:data
  updated_at timestamptz not null default now()
);
alter table integrations_tokens enable row level security;
-- لا سياسات إطلاقاً = anon لا يقرأ ولا يكتب. العامل الخلفي يصل عبر service-role فقط.
```
طبقة `lib/tools/tokens.ts` جاهزة للتحويل: استبدل readVault/writeVault بقراءة/كتابة الجدول عبر service-role — باقي الكود بلا تغيير.

---

## القسم 7 — استكشاف الأخطاء
| المشكلة | السبب والحل |
|---|---|
| «INTEGRATIONS_SECRET غير مضبوط» | أضف المفتاح وأعد تشغيل السيرفر (القسم 4) |
| redirect_uri_mismatch | الـURI في الكونسول يجب أن يطابق حرفياً بما فيه http/https والمنفذ |
| «فشل التحقق الأمني (state)» | انتهت الكوكي (10 دقائق) أو فتحت الرابط من متصفح آخر — أعد من الزر |
| access_token منتهٍ بلا تجديد | الـrefresh_token مفقود — اضغط Disconnect ثم Connect من جديد (prompt=consent يعيده) |
| Canva «invalid_scope» | تأكد من تفعيل النطاقات الثلاثة في إعدادات تطبيق Canva |
| البحث «GOOGLE_SEARCH_API_KEY غير مضبوط» | قسم 3 — مفتاح API + cx |

---

*أُعد بأمر المالك — مروة المايسترو (عقدة LAPTOP) — 2026-10-24. أي مفتاح سر لا يُطبع ولا يُخزن في المستودع إطلاقاً.*
