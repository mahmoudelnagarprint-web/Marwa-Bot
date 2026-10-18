# 🏗️ ملخص معماري: DSH (مساحة أدوات Harness)

> دراسة بقلم فيجن (الوكيل الأم) مباشرة — وكيل الدراسة انقطع.
> تاريخ: 2026-10-18 ~02:25 | المنهجية: جرد هيكلي كامل بـ pwsh (مستويان) + سياق الجلسات السابقة — المجلد فيه ~10,006 مسارًا أغلبها SDK ثنائي مكرر، فاعتمدت الجرد العملي على الملفات النصية الحقيقية.

## 1) الغرض الوظيفي
ليس مشروعًا واحدًا بل **مساحة أدوات لتحليل وتوسيع DeepSeek Harness (DSH)** وتشغيل مكونات مساعدة: عكس هندسة core (asar)، مشروع Omnibox (JARVIS)، جسر تليجرام لوكيل elnagarprint، وfreeapi — كلها تخدم تشغيل مساعدات AI على جهاز الورشة.

## 2) الهيكل العام (مقيس فعليًا)
```
G:\ai\DSH\
├── (جذر) أدوات عكس/تحليل asar: dsh-main.js, cordis-lib.js, client-modules.js,
│   connection-host.js, store-pkg.json, primitives-pkg.json, asar-*.cjs/txt,
│   make_invoice.py + فاتورة_مبيعات_INV-2026-0001.xlsx
├── omnibox\            ← مشروع JARVIS Omnibox (الإضافة + Native Companion)
├── elnagarprint-telegram-bridge\  ← جسر تليجرام لوكيل elnagarprint
├── freeapi\            ← مكون Home Assistant (hacs.json) + vercel.json
├── freeapi-mcp\        ← server.js (غلاف MCP)
├── arabic-design\      ← poster.html/png
└── deepseek flash\     ← فارغ
```

## 3) الوحدات الرئيسية
1. **omnibox** (جوهرة المجلد): إضافة DSH (cordis.patch.yml + lib/index.js + locale) + **native**: Companion.cs/.exe — عملية C# مع WebView2 (SDK مضمّن + webview2-sdk.zip) لعرض Webview عائم (Alt+Space) — مع نسخة مكررة "DSH bar" وvariant «hermas» وREPORT-final.md + توثيق-الإضافة.md (لها patch cordis معتمد).
2. **elnagarprint-telegram-bridge**: خدمة جسر تليجرام (Node start.mjs + Python bot.py + cordis agent-profile patch + run_service) بحالات في state\ (جلسات/دردشات/bridge_state) — جسر تحكم بوكيل DSH عبر تليجرام.
3. **freeapi**: مكون Home Assistant (hacs.json) + نسخة Vercel — مع **freeapi-mcp\server.js** كغلاف MCP — يوفر API مجاني لأدوات AI (README + .env).
4. **جذر**: أدوات تحليل asar (asar-list/asar-debug/asar-files) + client-modules/connection-host/cordis-lib — أدوات فهم وتوسيع DSH + مولد فاتورة (make_invoice.py).

## 4) مخازن البيانات
state\ في الجسر (chats.json/agent_sessions.json/runtime) • .env للجسر وfreeapi (أسرار — لا تُطبع) • ملفات asar-txt (قوائم فك الحزمة).

## 5) التكاملات
DSH core (cordis.patch.yml — إضافات profile) • WebView2 native (Companion.exe للـomnibox) • تليجرام (الجسر) • Home Assistant (freeapi) • MCP (freeapi-mcp).

## 6) تقييم الصحة (بدليل)
🟢 أدوات تحليل وتوسيع DSH فعلية (asar-debug/list + client/store/connection modules) — أساس عمل الإضافات.
🟡 **تكرار شجرة SDK**: `omnibox\DSH bar\native\webview2-sdk` و`omnibox\native\webview2-sdk` نسختان كاملتان (~10 آلاف ملف DLL/lib) + نسخة zip مكررة — مرشحة للتوحيد (توفير عشرات الميجا).
🟡 نسخ مكررة للمشروع نفسه: `omnibox\` و`omnibox\DSH bar\` و`hermas\` (3 نسخ متوازية) + lib-backup قديم.
🟡 ملف غريب بالجذر اسمه «0» (يُفحص لاحقًا — صفر بايتات على الأغلب).
🟡 `.env` في الجسر وfreeapi (تُعامل كأسرار — لم تُفتح).

## 7) خريطة دخول للتطوير
1. omnibox\README.md + REPORT-final.md + توثيق-الإضافة.md (الأحدث) ثم lib\index.js ثم native\Companion.cs.
2. الجسر: elnagarprint-telegram-bridge\README.md + config\config.json (سر التوكن هناك — لا يُطبع).
3. أدوات asar: الجذر (dsh-main.js…).

## 8) فهرس الملفات المهمة
| المسار | دوره | ملاحظة |
|--------|------|--------|
| omnibox\ (patch + native companion) | Omnibox JARVIS — Alt+Space overlay | مرجع الجلسة 2026-10-03 |
| omnibox\REPORT-final.md | تقرير إنهاء المشروع | نقطة بداية موثقة |
| elnagarprint-telegram-bridge\ | جسر تليجرام ↔ وكيل elnagarprint | Node + Python + patch |
| freeapi\ + freeapi-mcp\ | API مجاني + غلاف MCP | مكون HASS |
| الجذر: dsh-main.js, cordis-lib.js, asar-*.cjs | أدوات عكس هندسة DSH | + مولد فاتورة |
| arabic-design\ | ملصق عربي HTML/PNG | — |

---
*الجاهزية: 85% (جرد هيكلي كامل؛ الدراسة عميقة لكل فرع تُطلب عند الحاجة).*
