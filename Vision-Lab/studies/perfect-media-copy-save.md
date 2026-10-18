# 🏗️ ملخص معماري: perfect-media-copy-save

> دراسة بقلم فيجن (الوكيل الأم) مباشرة — الوكلاء انقطعوا 3 مرات قبل الإنهاء (هيكلهم الأولي استُبدل بهذه النسخة).
> تاريخ: 2026-10-18 ~02:25 | الملفات المقروءة فعليًا: 6 من 12 (manifest.json كامل، background.js أول 60/388، api_server.py أول 159 من 673، content.js أول 50/1212، requirements.txt كامل، setup_autostart.ps1 كامل).

## 1) الغرض الوظيفي
«Perfect Media Copy & Save PRO v8.0» — نظام ثنائي الطبقات لتحميل ونسخ الوسائط بأعلى جودة (يوتيوب/فيسبوك/إنستجرام + دعم MP3): إضافة كروم تلتقط الوسائط في الصفحة وتزرع أزرارًا عائمة، وسيرفر Flask محلي (منفذ 5888) يستخدم yt-dlp + ffmpeg المضمّن لتحميل الفيديو والتحويل لـMP3 (manifest.json:5).

## 2) نقاط الدخول والتشغيل
- **السيرفر**: `api_server.py` (673 سطرًا) — Flask + CORS * على **http://localhost:5888**.
- **الإضافة**: تُحمَّل كإضافة كروم غير معبأة (MV3) — content.js على كل المواقع عند document_idle.
- **الاستمرارية**: `setup_autostart.ps1` ينشئ اختصار PMCS_Server.lnk في Startup يُشغّل `silent_server_launcher.vbs` (سيرفر صامت عند كل تسجيل دخول) — setup_autostart.ps1:3-8.
- `scratch\test_server.py` تجارب؛ `perfect-image-copy-save.rar` نسخة مغلقة (لا تُفتح).

## 3) الهيكل العام
| الملف | الدور |
|-------|------|
| manifest.json (18 سطرًا) | MV3 v8.0 — صلاحيات downloads/activeTab/clipboardWrite/storage/notifications/**cookies** + `<all_urls>` + localhost:5888 |
| content.js (1,212 سطرًا) | حقن أزرار عائمة فوق الوسائط (تحميل/نسخ/Supreme/download-all + شريط إنستجرام خاص) بخط Cairo |
| background.js (388 سطرًا) | Service Worker: تمديد الصيغ (MIME > DataURL > URL) + سجل تحميل + Download All + تتبع تقدم |
| api_server.py (673 سطرًا) | Flask: POST /dl → yt-dlp (mp4 أو MP3 320k) بتقدم حي وسجل 50 عنصرًا + كشف صور بالتوقيع السحري |
| ffmpeg\ | ffmpeg/ffplay/ffprobe مضمّنة (yt-dlp يستخدمها — api_server.py:100) |
| setup_autostart.ps1 + silent_server_launcher.vbs | تشغيل صامت دائم عند الإقلاع |
| scratch\test_server.py / rar | تجارب / نسخة مؤرشفة |

## 4) الوحدات الرئيسية
1. content.js: كشف وسائط + أزرار عائمة (تحميل/نسخ/Supreme/download-all) + شريط إنستجرام + لوحة تحميلات.
2. background.js (388 سطرًا): أفضل امتداد (MIME > DataURL > URL — background.js:54)، تجميع Download All، سجل.
3. api_server.py: /dl → yt-dlp: فيديو `bestvideo[ext=mp4]+bestaudio[ext=m4a]` أو MP3 320kbps عبر FFmpegExtractAudio (أسطر 113-125) + تقدم حي في `download_progress` + سجل 50 عنصرًا (45-48) + توقيعات بايتات للصور (36-42) + UA كروم وreferer فيسبوك.
4. الإضافة↔السيرفر عبر localhost:5888 فقط.

## 5) المكتبات (requirements.txt — 4 أسطر بلا تثبيت إصدارات)
flask | flask-cors | yt-dlp | requests — وffmpeg مضمّن محليًا.

## 6) مخازن البيانات
مجلد التحميلات المحلي • سجل في الذاكرة فقط (download_progress/history — يُفقد بالإغلاق) • storage الإضافة.

## 7) التكاملات
يوتيوب/فيسبوك/إنستجرام (yt-dlp + UA مزيف + referer فيسبوك) → مجلد محلي • الحافظة • الإشعارات • بدء تلقائي بويندوز (Startup).

## 8) تقييم الصحة (بدليل)
🟢 قوة: بنية ناضجة (v8.0)، تحديد نوع الملف بتوقيع بايتات حقيقي، تقدم حي، UTF-8 للعربية في الكونسول (api_server.py:14-20).
🟡 **صلاحيات مفرطة**: `<all_urls>` + `cookies` + content script على كل المواقع (manifest.json:6-7,12).
🟡 السيرفر بلا مصادقة + CORS * — أي صفحة في المتصفح تطلب تحميلات من localhost:5888.
🟡 yt-dlp بـ `nocheckcertificate` + `ignoreerrors` (تجاهل شهادات وأخطاء).
🟡 تبعية هشة لمواقع متغيرة (yt-dlp يحتاج تحديثًا مستمرًا).

## 9) خريطة دخول للتطوير
1. api_server.py (673 سطرًا) — منطق yt-dlp والتقدم والمسارات.
2. content.js (1,212 سطرًا) — واجهة الأزرار لكل موقع.
3. background.js — الجسر والتنزيلات المباشرة.

## 10) فهرس الملفات المهمة
| الملف | دوره | ملاحظة |
|-------|------|--------|
| api_server.py (673 سطرًا) | سيرفر :5888 + yt-dlp + ffmpeg | بلا مصادقة + CORS * |
| content.js (1,212 سطرًا) | حقن أزرار على كل المواقع | أثقل ملف |
| background.js (388) | SW الإضافة + سجل + Download All | — |
| setup_autostart.ps1 | اختصار بدء تلقائي | يعمل عند كل تسجيل دخول |
| ffmpeg\ | ffmpeg مضمّن | للتحويل MP3 |

---
*الجاهزية للعودة للتطوير: 85% (لم تُقرأ: باقي background/content/api_server — البنية والدور كاملان).*
