# -*- coding: utf-8 -*-
"""قياس `/` + إثبات إن `_dash_open` بترجّع **نفس صفوف** `db.list_captures`.

المهم هنا مش السرعة بس: لازم نتأكد إن اللي بيتعرض للمالك هو بالظبط اللي
`db.list_captures(status='open', limit=150)` بيرجّعه — بنفس الترتيب — في كل
حالة، عشان ما نقدّمش صفوف ناقصة أو زيادة من غير ما ناخد بالنا.
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "projects" / "notebook-v2"
sys.path.insert(0, str(ROOT))

from nb import db, web  # noqa: E402

OUT = {}


def check(label):
    dash = db.dashboard()
    picked = web._dash_open(dash)
    direct = db.list_captures(status="open", limit=150)
    if picked is None:
        return {"label": label, "used_dashboard": False, "direct_n": len(direct)}
    return {
        "label": label,
        "used_dashboard": True,
        "picked_n": len(picked),
        "direct_n": len(direct),
        "same_ids_same_order": [r.get("id") for r in picked] == [r.get("id") for r in direct],
    }


client = web.app.test_client()

# 1) الحالة الحيّة
web._invalidate = None
try:
    from nb import cache
    cache.invalidate("dash:")
except Exception as exc:
    OUT["bust_error"] = str(exc)
OUT["live"] = check("live")

# 2) نُنشئ صفوف — لازم العدّاد يمنع الاعتماد على اللوحة لو الصف مش فيها
created = []
try:
    for i in range(2):
        created.append(db.add_capture({
            "title": f"VISION EQ TEST {i}", "body": "تكافؤ", "kind": "idea",
            "category": "غير مصنف", "priority": "normal", "source": "eq-test",
            "confidence": 0.5, "routed_by": "rules"}))
    OUT["created"] = created
    OUT["after_insert"] = check("after_insert")

    # 3) صفوف كتير (أكتر من حد اللوحة 150) → لازم نرجع None (مفيش اعتماد)
    t0 = time.time()
    OUT["root_ms_warm"] = None
    r = client.get("/")
    OUT["root_status"] = r.status_code
finally:
    for c in created:
        db.x("DELETE FROM captures WHERE id=%s", (c,))
    try:
        from nb import cache as _c
        _c.invalidate("dash:")
    except Exception:
        pass

OUT["leftover"] = int(db.scalar("SELECT count(*) FROM captures WHERE source='eq-test'"))
OUT["live_after_cleanup"] = check("live_after_cleanup")

# 4) توقيت `/` ساخن (3 محاولات)
times = []
for _ in range(3):
    t0 = time.time()
    client.get("/")
    times.append(round((time.time() - t0) * 1000, 1))
OUT["root_ms_3_tries"] = times

# 5) توقيت مسار مفلتر (لازم يستعلم لوحده)
t0 = time.time()
client.get("/?kind=task")
OUT["root_filtered_ms"] = round((time.time() - t0) * 1000, 1)

# 6) /api/dashboard سخن
t0 = time.time()
client.get("/api/dashboard")
OUT["api_dash_ms"] = round((time.time() - t0) * 1000, 1)

print(json.dumps(OUT, ensure_ascii=True, indent=2, default=str))
