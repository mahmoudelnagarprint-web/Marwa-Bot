# -*- coding: utf-8 -*-
"""A8 — باريتي الجسر مع القاعدة، نفس فحص scripts/acceptance.py بالحرف."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "projects" / "notebook-v2"))

from nb import bridge, db  # noqa: E402

rows = db.q("SELECT id FROM captures WHERE status IS DISTINCT FROM 'done' "
            "ORDER BY id DESC LIMIT 10")
ids = [r["id"] for r in rows]
listed = bridge.list_captures(limit=10, status="open")
bridged = [r.get("id") for r in listed if isinstance(r, dict)]
print(json.dumps({
    "db_ids": ids,
    "bridge_ids": bridged,
    "type_is_list": isinstance(listed, list),
    "match": sorted(bridged) == sorted(ids),
}, ensure_ascii=True))
