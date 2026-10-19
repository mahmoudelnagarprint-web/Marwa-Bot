# -*- coding: utf-8 -*-
"""اختبار عميل آلي حقيقي: subprocess + json.loads على stdout — زي الليد بالحرف.

العيب اللي اتقاس: `config.log` بيكتب على stdout، فـ`add`/`chat` بيخلطوا
سطر لوج مع الـJSON ويكسّروا `json.loads` عند العميل الآلي.
هنا بنشغّل كل أمر كعملية مستقلة ونتأكد: stdout = JSON نضيف، واللوج على stderr.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "projects" / "notebook-v2"
PY = ROOT / ".venv" / "Scripts" / "python.exe"
CLI = ROOT / "scripts" / "dsh_bridge.py"

OUT = {"results": [], "all_stdout_clean": True, "all_parse_ok": True,
       "all_logs_on_stderr": True}


def run(args, expect_json=True):
    p = subprocess.run([str(PY), str(CLI)] + args, capture_output=True,
                       text=True, encoding="utf-8", errors="replace",
                       cwd=str(ROOT), timeout=180)
    rec = {"args": args, "rc": p.returncode,
           "stdout_first_line": (p.stdout or "").splitlines()[:1],
           "stderr_len": len(p.stderr or "")}
    if expect_json:
        try:
            parsed = json.loads(p.stdout)
            rec["parsed_type"] = type(parsed).__name__
            rec["json_ok"] = True
        except Exception as exc:
            rec["json_ok"] = False
            rec["json_error"] = f"{type(exc).__name__}: {exc}"
            OUT["all_parse_ok"] = False
        # أي stdout مش JSON = عيب في العقد
        if (p.stdout or "").strip() and not rec.get("json_ok"):
            OUT["all_stdout_clean"] = False
    OUT["results"].append(rec)
    return p


# --- الأوامر الخالصة
run(["stats", "--json"])
run(["list", "--json", "--limit", "3"])
run(["today", "--json"])
run(["status", "--json"])
run(["search", "ليزر", "--json"])

# --- الأوامر اللي بتلوج فعلًا (هنا كان العيب): chat و add
#     "هاي" = تحية محلية (بتروح للبوابة وبتلوج) — ومابتحفظش صف
chat_p = run(["chat", "هاي", "--json"])
#     نص فيه إشارة التقاط لكن بلا تليجرام — بننضّف الصف بعدين
add_p = run(["add", "VISION JSON TEST فكرني بكرة الساعة 5", "--json"])

# ندوّر على الصف اللي اتكتب ونمسحه
sys.path.insert(0, str(ROOT))
from nb import db  # noqa: E402

rows = db.q("SELECT id FROM captures WHERE title LIKE %s OR body LIKE %s",
            ("%VISION JSON TEST%", "%VISION JSON TEST%")) or []
OUT["scratch_ids"] = [r["id"] for r in rows]
for r in rows:
    db.x("DELETE FROM captures WHERE id=%s", (r["id"],))
OUT["scratch_left"] = int(db.scalar(
    "SELECT count(*) FROM captures WHERE title LIKE %s OR body LIKE %s",
    ("%VISION JSON TEST%", "%VISION JSON TEST%")))

# نجمع عنوان نص الرد من add لو الـJSON نضيف
try:
    add_parsed = json.loads(add_p.stdout)
    OUT["add_saved"] = add_parsed.get("saved")
    OUT["add_intent"] = add_parsed.get("intent")
except Exception:
    OUT["add_saved"] = None

OUT["chat_stderr_has_log"] = "ai_router" in (chat_p.stderr or "") or \
                             "intent" in (chat_p.stderr or "")
OUT["chat_stderr_sample"] = (chat_p.stderr or "").splitlines()[:2]

# --- التأكد إن مفيش `print` تاني في البريدج غير `_emit`
import re  # noqa: E402
src = (ROOT / "scripts" / "dsh_bridge.py").read_text(encoding="utf-8")
prints = [ln.strip() for ln in src.splitlines() if re.search(r"(?<!\w)print\(", ln)]
OUT["print_calls"] = prints
OUT["print_calls_only_in_emit"] = all("file=stream" in ln for ln in prints)

# --- الوضع البشري (بلا --json) لازم يفضل شغال
h = run(["stats"], expect_json=False)
OUT["human_mode_rc"] = h.returncode
OUT["human_mode_out"] = (h.stdout or "").splitlines()[:1]

print(json.dumps(OUT, ensure_ascii=True, indent=2, default=str))
