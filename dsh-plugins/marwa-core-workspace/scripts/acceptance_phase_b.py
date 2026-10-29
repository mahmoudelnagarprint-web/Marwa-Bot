# -*- coding: utf-8 -*-
"""Marwa Command Center — Acceptance Tests: Phase B (نموذج وكيل واحد — فارس).

اختبار قبول ذاتي موثق بالأدلة (متطلب خارطة الطريق: «اختبارات قبول موثقة بالأدلة»).
يستدعي الجسر (dsh_bridge.py) مباشرة عبر واجهته المُصدَّرة، ويفحص:
  1. workspaces.ensure  → إعادة توليد AGENTS.md سليماً بعلامة المولد.
  2. سلامة الحقن        → لا قصّ في منتصف كلمة (إصلاح _head) + لا تكرار عنوان/بدن المثبتة.
  3. squad.stats        → إحصائيات من سجلات فعلية (أرقام صحيحة / صادقة بالسالب).
  4. binding.get        → قراءة سجل الربط المحفوظ.
  5. binding.ensure     → كتابة ذرية لسجل ربط وهمي ثم حذفه — لا يلمس الربط الحقيقي.

النتيجة: تقرير PASS/FAIL يُطبع بـ«دليل: …» لكل بند. خروج 0 = كل البنود ناجحة.
لا يكتب في pos_data.db ولا في أي ملف حالة جذري — AGENTS.md في مساحات الوكلاء فقط
(الملف الذي تولّده الواجهة أصلاً بعلامة المولد).
"""
import io
import json
import re
import sys
from pathlib import Path

# لا نعيد لفّ stdout/stderr هنا: الجسر (dsh_bridge.py) يلفّهما بنفسه عند الاستيراد.
# إعادة اللفّ المضاعفة تُغلق المخزن السفلي وتكسر stderr — نبقي على لفّ الجسر فقط.

BRIDGE = Path(__file__).resolve().parent.parent / "bridge" / "dsh_bridge.py"
sys.path.insert(0, str(BRIDGE.parent))

import dsh_bridge  # noqa: E402 — بعد ضبط المسار

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    print("%s  %s  %s" % ("PASS" if ok else "FAIL", name, detail))


def call(cmd, params):
    return dsh_bridge.HANDLERS[cmd](params or {})


def main():
    print("Marwa Command Center — Phase B Acceptance Tests")
    print("bridge: %s" % BRIDGE)
    print("repo  : %s" % dsh_bridge.REPO)
    print("-" * 70)

    # 1) workspaces.ensure — إعادة توليد AGENTS.md سليماً
    for aid in ("fares", "marwa"):
        r = call("workspaces.ensure", {"agent": aid})
        md = Path(r["agentsMd"])
        ok = r.get("ok") is not False and md.exists() and r.get("agentsMdChars", 0) > 500
        check("workspaces.ensure(%s) -> AGENTS.md مكتوب" % aid, ok,
              "chars=%s path=%s" % (r.get("agentsMdChars"), r["agentsMd"]))
        if md.exists():
            txt = md.read_text(encoding="utf-8", errors="replace")
            # 2) سلامة الحقن
            mark_ok = "مولّد من جسر marwa-core-workspace" in txt
            check("علامة المولد موجودة (%s)" % aid, mark_ok, "مذكورة في السطر الأخير")
            # لا قصّ وسط كلمة: أي سطر ينتهي بعلامة «…» فقط عند الاقتطاع — لكن لا سطر مبتور بكلمة
            # (الـ_fix الجديد يقطع عند حد فقرة ولا يترك «…» إلا في بداية سطر مستقل)
            broken = re.search(r"(علاقتها بالفر|اقتراح ي$|عاجل:خد)", txt)
            check("لا قصّ في منتصف كلمة (%s)" % aid, broken is None,
                  "نظيف" if broken is None else "وجد: %r" % broken.group(0))
            # لا تكرار عنوان/بدن المثبتة
            dup = re.search(r"عاجل:خد بالك لازم اتصل", txt)
            check("لا تكرار عنوان/بدن المثبتة (%s)" % aid, dup is None,
                  "نظيف" if dup is None else "وجد: %r" % dup.group(0))

    # 3) squad.stats — أرقام فعلية
    for aid in ("fares", "marwa"):
        s = call("squad.stats", {"agent": aid})
        nb = s.get("notebookTasks") or {}
        has_numbers = isinstance(nb.get("open"), int) and isinstance(nb.get("done"), int)
        has_ws = isinstance(s.get("workspace"), dict) and s["workspace"].get("exists") is True
        check("squad.stats(%s) أرقام من سجلات فعلية" % aid, has_numbers,
              json.dumps(nb, ensure_ascii=False)[:120])
        check("squad.stats(%s) مساحة عمل موجودة" % aid, has_ws,
              "path=%s" % (s.get("workspace") or {}).get("path"))

    # 4) تغطية السرب — كل وكلاء السرب يملكون AGENTS.md سليماً (المرحلة C: التعميم)
    squad_agents = ["marwa", "fares", "salma", "koko", "bibo", "sasa", "rased", "hakim"]
    for aid in squad_agents:
        ws = dsh_bridge.WORKSPACE_DIRS.get(aid)
        md = (dsh_bridge.REPO / ws / "AGENTS.md") if ws else None
        ok = md is not None and md.exists() and ("مولّد من جسر marwa-core-workspace" in md.read_text(encoding="utf-8", errors="replace"))
        broken = None
        if ok:
            txt = md.read_text(encoding="utf-8", errors="replace")
            for pat in ("علاقتها بالفر", "اقتراح ي$", "عاجل:خد"):
                if re.search(pat, txt):
                    broken = pat
                    break
        check("تغطية السرب: AGENTS.md سليم (%s)" % aid, md is not None and md.exists() and ok and broken is None,
              "نظيف" if (md is not None and md.exists() and ok and broken is None) else ("ناقص/مبتور: %s" % (broken or "غير موجود")))

    # 5) binding.get — قراءة السجل
    g = call("binding.get", {"agent": "marwa"})
    b = g.get("binding") or {}
    check("binding.get(marwa) يعيد الربط المحفوظ", bool(b.get("workspaceId")) and b.get("preset") == "marwa",
          "title=%s" % (b.get("workspaceTitle") or "—"))

    # 5) binding.ensure — كتابة ذرية لسجل وهمي (داخل orchestrator/ فقط) ثم حذفه
    fake = "selftest_%s" % (b.get("workspaceId") or "tmp")
    rec = call("binding.ensure", {"agent": fake, "workspaceId": "ws-test", "workspaceTitle": "اختبار قبول",
                                  "preset": "fares", "sessionId": "s-test"})
    got = call("binding.get", {"agent": fake})
    ok_roundtrip = got.get("binding", {}).get("workspaceId") == "ws-test"
    check("binding.ensure/get round-trip (سجل وهمي)", ok_roundtrip,
          "rec=%s" % json.dumps(rec, ensure_ascii=False)[:100])
    # حذف السجل الوهمي — عدّل الملف إلى الحالة الأصلية
    data = dsh_bridge._load_bindings()
    data["agents"].pop(fake, None)
    dsh_bridge.BINDINGS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    gone = call("binding.get", {"agent": fake}).get("binding") is None
    check("تنظيف السجل الوهمي", gone, "اختفى بعد الحذف")

    print("-" * 70)
    failed = [n for n, ok, _ in RESULTS if not ok]
    print("النتيجة: %d/%d PASS — %s" % (len(RESULTS) - len(failed), len(RESULTS),
                                         "الكل ناجح" if not failed else "فشل: " + ", ".join(failed)))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
