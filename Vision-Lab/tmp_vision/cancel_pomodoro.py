# -*- coding: utf-8 -*-
"""يلغي أي بومودورو بدأته اختباراتي بالغلط — صفر إرسال تليجرام."""
import json
import sys

sys.path.insert(0, r"G:\ai\Naggar Print POS Agent\Vision-Lab\projects\notebook-v2")

from nb import db, proactive   # noqa: E402

cols = db.q("""SELECT column_name FROM information_schema.columns
               WHERE table_name='outbox' ORDER BY ordinal_position""") or []
print(json.dumps({"outbox_cols": [c["column_name"] for c in cols]}, ensure_ascii=True))

before = db.q("SELECT id, kind, sent_at, due_at FROM outbox WHERE kind LIKE %s "
              "ORDER BY id DESC LIMIT 5", ("%pomodoro%",)) or []
print(json.dumps({"before": [dict(r) for r in before]}, ensure_ascii=True, default=str))
print(json.dumps({"cancelled": proactive.cancel_latest_pomodoro()}, ensure_ascii=True))
after = db.q("SELECT id, kind, sent_at, due_at FROM outbox WHERE kind LIKE %s "
             "ORDER BY id DESC LIMIT 5", ("%pomodoro%",)) or []
print(json.dumps({"after": [dict(r) for r in after]}, ensure_ascii=True, default=str))
