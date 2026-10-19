# -*- coding: utf-8 -*-
"""تحقق: هل أي رسالة اتبعتت للمالك خلال آخر 20 دقيقة بسببي؟"""
import json
import sys

sys.path.insert(0, r"G:\ai\Naggar Print POS Agent\Vision-Lab\projects\notebook-v2")

from nb import db   # noqa: E402

rows = db.q("""SELECT id, kind, body, sent_at, due_at, created_at
               FROM outbox
               WHERE created_at > now() - interval '25 minutes'
               ORDER BY id""") or []
print(json.dumps({"recent_outbox": [dict(r) for r in rows]}, ensure_ascii=True, default=str))
print(json.dumps({"pending_unsent": [dict(r) for r in (db.q(
    "SELECT id, kind, left(body,60) AS body, due_at FROM outbox WHERE sent_at IS NULL "
    "ORDER BY id") or [])]}, ensure_ascii=True, default=str))
