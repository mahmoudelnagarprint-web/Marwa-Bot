# -*- coding: utf-8 -*-
"""تأكيد إن واجهات راصد وصلت بالشكل المجمّد: cache + dashboard + المحادثات."""
import inspect
import json
import sys

sys.path.insert(0, r"G:\ai\Naggar Print POS Agent\Vision-Lab\projects\notebook-v2")

from nb import cache, db   # noqa: E402

out = {"cache_sig": {}, "db_sig": {}}
for fn in ("get_or_set", "invalidate", "stats"):
    f = getattr(cache, fn, None)
    out["cache_sig"][fn] = str(inspect.signature(f)) if f else "MISSING"
for fn in ("dashboard", "log_message", "recent_messages", "count_messages"):
    f = getattr(db, fn, None)
    out["db_sig"][fn] = str(inspect.signature(f)) if f else "MISSING"

# مفاتيح dashboard
d = db.dashboard()
out["dashboard_type"] = type(d).__name__
out["dashboard_keys"] = sorted(d.keys()) if isinstance(d, dict) else str(d)[:200]
for k in ("stats", "captures", "due", "late", "need_help", "projects", "radar", "events", "ws_stats"):
    v = d.get(k) if isinstance(d, dict) else None
    out.setdefault("dashboard_shapes", {})[k] = (
        f"{type(v).__name__}[{len(v)}]" if isinstance(v, (list, dict)) else repr(v)[:40])

# المحادثات: نتأكد إن الدوال شغالة على chat_id اختباري من غير ما نلوّث سجل المالك
TEST_CHAT = 999999999
n0 = db.count_messages(TEST_CHAT)
mid = db.log_message(TEST_CHAT, "user", "[vision-check] ping", {"src": "vision"})
msgs = db.recent_messages(TEST_CHAT, limit=12)
n1 = db.count_messages(TEST_CHAT)
out["conv"] = {
    "count_before": n0,
    "inserted_id": mid,
    "count_after": n1,
    "returned": len(msgs),
    "oldest_first_ok": (len(msgs) > 0 and msgs[0]["content"].startswith("[vision-check]")),
    "row_keys": sorted(msgs[0].keys()) if msgs else None,
}
db.x("DELETE FROM conversations WHERE chat_id=%s", (TEST_CHAT,))
out["conv"]["count_after_cleanup"] = db.count_messages(TEST_CHAT)

# persona بيتكلم مع نفس الدوال؟
from nb import persona   # noqa: E402

out["persona_bridges"] = {k: persona._has(k) for k in
                          ("log_message", "recent_messages", "count_messages")}
print(json.dumps(out, ensure_ascii=True, indent=1, default=str))
