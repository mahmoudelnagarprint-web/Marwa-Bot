"""إعادة بناء الصفوف اللي اتضررت — من السجل الرسمي `conversations` فقط.

القاعدة الحاكمة: **ممنوع نخترع قيمة**. كل صف بيتبني من نص المالك نفسه اللي
محفوظ في `conversations` + من رد البوت اللي بيقول «سجّلت (#N)» (ودي فيها
النوع والتصنيف والميعاد). لو معلومة مش موجودة، تتسجّل `None` وتبان في التقرير
بدل ما تتخمّن.
"""
from __future__ import annotations

import json
import sys

ROOT = r"G:\ai\Naggar Print POS Agent\Vision-Lab\projects\notebook-v2"
sys.path.insert(0, ROOT)
import nb.db as db  # noqa: E402

out = {}

out["captures_now"] = [
    {"id": r["id"], "kind": r["kind"], "title": str(r["title"]), "status": r["status"]}
    for r in (db.q("SELECT id, kind, title, status FROM captures ORDER BY id") or [])
]

# كل رسائل المالك + الردود اللي بعدها مباشرة (لتوصيف النوع/التصنيف/الميعاد)
rows = db.q("""
    SELECT id, role, content, created_at
    FROM conversations
    WHERE chat_id = 561770354
    ORDER BY id
""") or []

pairs = []
for i, r in enumerate(rows):
    if r["role"] != "user":
        continue
    nxt = next((x for x in rows[i + 1:] if x["role"] == "assistant"), None)
    pairs.append({
        "conv_id": r["id"],
        "at": str(r["created_at"]),
        "user_text": str(r["content"]),
        "bot_reply": str(nxt["content"])[:300] if nxt else None,
        "bot_at": str(nxt["created_at"]) if nxt else None,
    })
out["owner_messages"] = pairs

# أي رد بوت فيه «سجّلت» = صف اتكتب فعلًا
out["captures_ever_announced"] = [
    {"conv_id": p["conv_id"], "at": p["at"], "user": p["user_text"], "reply": p["bot_reply"]}
    for p in pairs
    if p["bot_reply"] and "سجّلت" in p["bot_reply"]
]

# الصفوف المفقودة المؤكَّدة من سجل الحادثة: ids 4 و 5 (كانوا موجودين وضاعوا)
out["missing_ids_from_incident"] = [4, 5]

with open(ROOT + r"\tmp_lead\rebuild_source.json", "w", encoding="utf-8") as fh:
    json.dump(out, fh, ensure_ascii=False, indent=1, default=str)
print("done")
