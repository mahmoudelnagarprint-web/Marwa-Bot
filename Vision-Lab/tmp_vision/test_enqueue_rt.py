# -*- coding: utf-8 -*-
"""`enqueue` بيكتب الكيبورد في jsonb و`flush` بقراه — رحلة كاملة، صفر تليجرام."""
import json
import sys

sys.path.insert(0, r"G:\ai\Naggar Print POS Agent\Vision-Lab\projects\notebook-v2")

from nb import db, proactive   # noqa: E402

TAG = "vision-test-rt"
out = {}
try:
    ok = proactive.enqueue(561770354, "[vision-test] رحلة", "reminder",
                           dedupe_key=TAG, keyboard=proactive.capture_kb(11))
    out["enqueue_ok"] = ok
    row = db.q("SELECT id, kind, keyboard FROM outbox WHERE dedupe_key=%s", (TAG,), one=True)
    out["stored_raw"] = str(row["keyboard"])[:120]
    out["decoded_keys"] = [c for r in proactive._decode_kb(row["keyboard"]) for _, c in r]

    # إعادة إدخال بنفس المفتاح = مرفوضة (منع التكرار)
    out["duplicate_rejected"] = proactive.enqueue(561770354, "نسخة تانية", "reminder",
                                                  dedupe_key=TAG)
    # رسالة بلا كيبورد
    proactive.enqueue(561770354, "[vision-test] بلا أزرار", "plain", dedupe_key=TAG + "-plain")
    plain = db.q("SELECT keyboard FROM outbox WHERE dedupe_key=%s", (TAG + "-plain",), one=True)
    out["plain_keyboard_is_null"] = plain["keyboard"] is None
finally:
    db.x("DELETE FROM outbox WHERE dedupe_key LIKE %s", (TAG + "%",))
    left = db.q("SELECT count(*) AS c FROM outbox WHERE dedupe_key LIKE %s", (TAG + "%",))
    out["leftovers"] = left[0]["c"]

print(json.dumps(out, ensure_ascii=True, indent=1, default=str))
