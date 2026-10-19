# -*- coding: utf-8 -*-
"""يفحص عمود outbox.keyboard — النوع والقيم الموجودة."""
import json
import sys

sys.path.insert(0, r"G:\ai\Naggar Print POS Agent\Vision-Lab\projects\notebook-v2")

from nb import db   # noqa: E402

cols = db.q("""SELECT column_name, data_type FROM information_schema.columns
               WHERE table_name='outbox' ORDER BY ordinal_position""") or []
print(json.dumps({"cols": [[c["column_name"], c["data_type"]] for c in cols]},
                 ensure_ascii=True))
rows = db.q("SELECT id, kind, keyboard, left(body,40) AS body FROM outbox ORDER BY id DESC LIMIT 10") or []
print(json.dumps([[r["id"], r["kind"], r["keyboard"], r["body"]] for r in rows],
                 ensure_ascii=True, default=str))
