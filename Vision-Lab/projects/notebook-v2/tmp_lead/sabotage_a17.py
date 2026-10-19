# -*- coding: utf-8 -*-
"""اختبار عدائي لـA17 — **هل البند يقدر يفشل؟**

بند قبول عمره ما فشل = ختم مطاطي مش قياس. فالسكربت ده بيرجّع العيب
القديم **عن قصد** (باب بيسجّل «هاي» من غير ما يعدّي البوابة) وبيتأكد إن
A17 بيقول **BAD** — وبعدين بيرجّع كل حاجة زي ما كانت.

الأهم: السكربت **مش بيكتب صف حقيقي**. الأبواب بتتنادى و`db.add_capture`
مستبدَل بـspy جوّه A17 نفسه، فالتسجيل الوهمي بيتعدّ ومش بينزل قاعدة.
كمان بنتأكد في الآخر إن عدد الصفوف ما اتغيّرش.

التشغيل:
    .venv\\Scripts\\python.exe tmp_lead\\sabotage_a17.py
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(PROJECT / "scripts"))


def jdump(obj):
    return json.dumps(obj, ensure_ascii=True, default=str)


def main():
    import acceptance as acc
    import nb.bot as bot
    import nb.db as db

    report = {"scenarios": [], "verdict": None}

    def rows():
        try:
            return int(db.scalar("SELECT count(*) FROM captures") or 0)
        except Exception as exc:
            return f"error: {type(exc).__name__}"

    rows_before = rows()
    real_process = bot.process_text

    # ---------------------------------------------------------- 1) خط الأساس
    r = acc.A17_gate_all_doors(False)
    report["scenarios"].append({
        "name": "خط الأساس (الكود الحالي)",
        "status": r.status, "detail": r.detail[:150],
        "expect": "OK", "ok": r.status == "OK",
    })

    # ------------------------------------------- 2) تخريب: باب بيسجّل الكلام
    # ده بالظبط العيب القديم: الباب بيحفظ من غير بوابة. بنقلّد السلوك
    # بنداء `db.add_capture` مباشرة — واللي A17 بيحرسه بـspy.
    def sabotaged_process_text(text, chat_id=None, source="test", **kw):
        db.add_capture(text, kind="note", source=source)  # ← التخريب
        return {"ok": True, "intent": "capture", "note_id": 999999,
                "reply": "اتحفظ (مزيف)"}

    bot.process_text = sabotaged_process_text
    try:
        r2 = acc.A17_gate_all_doors(False)
        report["scenarios"].append({
            "name": "تخريب: باب بيسجّل من غير البوابة",
            "status": r2.status, "detail": r2.detail[:220],
            "expect": "BAD", "ok": r2.status == "BAD",
        })
    finally:
        bot.process_text = real_process

    # ------------------------------------------ 3) الرجوع: البند يرجع أخضر
    r3 = acc.A17_gate_all_doors(False)
    report["scenarios"].append({
        "name": "بعد الرجوع",
        "status": r3.status, "detail": r3.detail[:150],
        "expect": "OK", "ok": r3.status == "OK",
    })

    rows_after = rows()
    report["rows_before"] = rows_before
    report["rows_after"] = rows_after
    report["no_real_row_written"] = rows_before == rows_after
    report["all_scenarios_ok"] = all(s["ok"] for s in report["scenarios"])
    report["verdict"] = ("A17 بيفشل لما يلاقي عيب ويرجع ينجح لما يتصلح"
                         if report["all_scenarios_ok"] and report["no_real_row_written"]
                         else "فيه سيناريو مش زي المتوقع")
    print(jdump(report))
    return 0 if report["all_scenarios_ok"] and report["no_real_row_written"] else 1


if __name__ == "__main__":
    sys.exit(main())
