# -*- coding: utf-8 -*-
# تنظيف تعارض RASED_SENTINEL_STATE.md (دمج نظيف بلا علامات تعارض ولا --------- مكررة)
import io

P = r"G:\ai\Naggar Print POS Agent\RASED_SENTINEL_STATE.md"
with io.open(P, "r", encoding="utf-8", errors="replace") as f:
    lines = f.readlines()

# 1) حذف الست '---' المكررة (سطور 247-252 فهرس 246-251) — فقط لو متتالية قبل التعارض
# نبحث عن التسلسل: '---' ×6 متتالية
cleaned = []
i = 0
n = len(lines)
while i < n:
    # كشف 6 '---' متتالية
    if lines[i].strip() == "---" and i+5 < n and all(lines[i+k].strip() == "---" for k in range(6)):
        # نتحقق أن قبلهم سطر حالة، وبعدهم التعارض
        # ننزّلهم (نحتفظ بواحد أو بلا شيء) — الأفضل حذفهم كلهم
        i += 6
        continue
    cleaned.append(lines[i])
    i += 1

# 2) استبدال منطقة التعارض (<<<<<<< ... >>>>>>>) بنسخة نظيفة
# نجمع النص كامل بعد تنظيف الـ---
joined = "".join(cleaned)

start = joined.find("<<<<<<< Updated upstream")
end = joined.find(">>>>>>> Stashed changes")
if start == -1 or end == -1:
    print("تحذير: لم أجد علامات التعارض. محتوى الملف ربما تغير.")
    # رغم ذلك نعرض حالة العلامات
    print("start:", start, "end:", end)
    import sys; sys.exit(0)

# النص قبل التعارض
before = joined[:start]
# النص بعد التعارض (مع إزالة السطر الفارغ بعد >>>>>>>)
after = joined[end + len(">>>>>>> Stashed changes"):]
# إزالة سطر فارغ زائد في بداية after إن وُجد
if after.startswith("\n\n"):
    after = after[1:]

clean_block = (
    "## 🔄 رصد المزامنة اليومي — 2026-10-27 09:45\n\n"
    "### الورشة (WORKSHOP) ← المصدر الرسمي\n"
    "| المسار | الحالة |\n"
    "|--------|--------|\n"
    "| Git push | ✅ 1ba337 — experience_ledger — 09:40 |\n"
    "| Supabase Push | ✅ 7 جداول upserted |\n"
    "| Supabase Pull | ✅ 0 pending |\n\n"
    "### اللابتوب (LAPTOP) — عقدة فرعية\n"
    "| المسار | الحالة |\n"
    "|--------|--------|\n"
    "| Git auto-sync | ⏳ آخر sync 08:12 — محتاج يسحب 1ba337 |\n"
    "| Supabase | مقصورة على pull فقط |\n\n"
    "### ⚠️ ملاحظة\n"
    "- Vision-Lab/projects/MarwaNotebook: تطبيق Flask بمساره الخاص (gitlab nested) — لا يتبع الـ parent\n"
    "- **إجراء مطلوب من اللابتوب**: git pull origin main لجلب 1ba337\n\n"
    "## 14) تنبيه إلى راصد-الورشة: لوج rased_daily_autosync غائب على اللابتوب (أمر مروة — تنفيذ اللابتوب 2026-10-27 ~10:12)\n\n"
    "**الأمر المنفذ (بأمر مروة: فحص ومزامنة فورية):**\n"
    "1. `git fetch origin` + `git rebase origin/main` → **\"Current branch main is up to date\"** — بلا أي تعارض (unmerged=0)، الشجرة نظيفة.\n"
    "2. ✅ كوميت `e1ba337` «feat: update experience_ledger with agent lessons (RASED 2026-10-27 09:40)» **موجود** وسلف (ancestor) لرأس الفرع.\n"
    "3. ⚠️ **التنبيه الجوهري:** `logs/rased_daily_autosync.log` **غير موجود على عقدة اللابتوب** — رغم أن `scripts/rased_daily_autosync.py` مُعدّ للكتابة فيه (`LOG_FILE = logs/rased_daily_autosync.log`)، وموجود بجواره قفل `LOGS/rased_daily_autosync.lock` بالتصميم. آخر تقرير «توليد آلي» بالدفتر أعلاه صادر من **عقدة WORKSHOP 01:22** — أي أن السكربت لا يعمل/لا يسجّل على اللابتوب. ملفات اللوج الفعلية على اللابتوب: `git_autosync.log` (سليم — آخر دورة 10:12 push OK) و`autopull.log` و`proactive_alerts.log` و`notebook_bot.log`.\n"
    "4. نظافة: أُزيل غياران (stash) قديمان يخصان ملفات وقت تشغيل سريعة التغيرة (`proactive_alerts_state.json` وأثر rebase تعارض قديم من 10/18) — المستودع نظيف: HEAD `3d4f088` = origin/main، ahead=0/behind=0.\n"
    "5. **المطلوب من راصد-الورشة:** مراجعة سبب عدم إنشاء اللوج على اللابتوب (هل `rased_daily_autosync.py` مجدول على الورشة فقط عمداً؟ أم يلزم جدولته على اللابتوب؟) وتوثيق القرار في هذا الدفتر.\n\n"
    "*التوقيع: راصد اللابتوب (حارس النظام) — 2026-10-27 ~10:12 — تنفيذاً لأمر مروة*\n"
)

new_content = before + clean_block + after

# نسخة احتياطية
with io.open(P + ".bak-conflict", "w", encoding="utf-8") as f:
    f.write(joined)

with io.open(P, "w", encoding="utf-8") as f:
    f.write(new_content)

# تحقق نهائي
with io.open(P, "r", encoding="utf-8") as f:
    final = f.read()
print("علامات تعارض متبقية:", final.count("<<<<<<<"), final.count(">>>>>>>"))
print("عدد الأسطر بعد:", final.count("\n"))
print("حسن: لا توجد علامات <<<<<<< أو >>>>>>>" if "<<<<<<<" not in final and ">>>>>>>" not in final else "لا يزال هناك تعارض!")
