"""تحقق الـLead المستقل: التدفق الكامل من نص المالك لصف القاعدة والرد.

بـ Telegram وهمي (FakeTG) — **صفر إرسال حقيقي**. بيسجّل كل نداء send بدل ما يبعته.
الغرض: أثبت إن A1 (الحوار مش بيتحفظ) وA2 (الطلبات بتتحفظ) شغالين في التدفق
الحقيقي مش في الوحدات بس.
"""
from __future__ import annotations

import json
import os
import sys
import time

PROJ = r"G:\ai\Naggar Print POS Agent\Vision-Lab\projects\notebook-v2"
sys.path.insert(0, PROJ)

import nb.bot as bot          # noqa: E402
import nb.db as db            # noqa: E402

CHAT = 561770354


class FakeTG:
    """عميل تليجرام وهمي — بيسجّل النداءات، ما بيبعتش حاجة أبدًا."""

    def __init__(self):
        self.sent = []
        self.typing_calls = 0

    def send(self, chat_id, text, kb=None, reply_to=None, reply_kb=None, kind=None):
        self.sent.append({
            "chat_id": chat_id,
            "text": text,
            "inline_kb": [[t[0] for t in row] for row in (kb or [])],
            "reply_kb": [list(r) for r in (reply_kb or [])],
            "kind": kind,
        })
        return True

    def typing(self, chat_id):
        self.typing_calls += 1

    def edit(self, *a, **k):
        return True

    def answer_cb(self, *a, **k):
        return True

    def call(self, method, payload=None):
        return {"ok": True, "result": {}}


def capture_count():
    return int(db.scalar("SELECT count(*) FROM captures") or 0)


def rows_since(before):
    return db.q("SELECT id, kind, title, status FROM captures WHERE id > %s ORDER BY id",
                (before,)) or []


def run_case(label, text, expect_intent):
    before = capture_count()
    max_before = db.scalar("SELECT coalesce(max(id),0) FROM captures") or 0
    tg = FakeTG()
    t0 = time.time()
    err = None
    try:
        bot._handle_message(tg, {"chat": {"id": CHAT}, "text": text})
    except Exception as exc:  # noqa: BLE001
        err = f"{type(exc).__name__}: {exc}"
    dt = round(time.time() - t0, 2)
    after = capture_count()
    new_rows = rows_since(max_before)
    res = {
        "label": label,
        "input": text,
        "expect": expect_intent,
        "secs": dt,
        "sent_count": len(tg.sent),
        "sent_to_telegram_real": False,
        "replies": [s["text"][:260] for s in tg.sent],
        "reply_kb_sample": tg.sent[-1]["reply_kb"] if tg.sent else None,
        "inline_kb_sample": tg.sent[-1]["inline_kb"] if tg.sent else None,
        "db_rows_written": after - before,
        "new_rows": [{"id": r["id"], "kind": r["kind"], "title": (r["title"] or "")[:48]}
                     for r in new_rows],
        "error": err,
    }
    # الحكم
    if err:
        res["verdict"] = "ERROR"
    elif expect_intent == "chat":
        res["verdict"] = "OK" if after == before else "FAIL (اتحفظ صف في الحوار!)"
    elif expect_intent == "capture":
        res["verdict"] = "OK" if after == before + 1 else "FAIL (مفيش صف اتكتب)"
    else:
        res["verdict"] = "-"
    # تنضيف أي صف اتكتب
    for r in new_rows:
        try:
            db.x("DELETE FROM captures WHERE id=%s", (r["id"],))
        except Exception:  # noqa: BLE001
            pass
    for r in new_rows:
        try:
            db.x("DELETE FROM capture_events WHERE capture_id=%s", (r["id"],))
        except Exception:  # noqa: BLE001
            pass
    return res


CASES = [
    # A1 — الحوار لازم مايتحفظش
    ("تحية «هاي»", "هاي", "chat"),
    ("سؤال «عامل ايه النهاردة؟»", "عامل ايه النهاردة؟", "chat"),
    ("مجاملة «ازيك يا فوفا»", "ازيك يا فوفا", "chat"),
    ("سؤال حر «ايه أخبار الشغل؟»", "ايه أخبار الشغل؟", "chat"),
    # A2 — الالتقاط لازم يتحفظ
    ("تذكير صريح", "فكرني بكرة الساعة 5 أسلم الطلب", "capture"),
    ("مهمة ورشة", "ليزر اعمل بوكس خشب مقاس 30", "capture"),
    ("فكرة برنامج", "فكرة برنامج لحساب الخامات", "capture"),
]

out = {"cases": [], "env": {"chat": CHAT, "cache": os.environ.get("NB2_CACHE", "default")}}
for label, text, expect in CASES:
    out["cases"].append(run_case(label, text, expect))

out["summary"] = {
    "total": len(out["cases"]),
    "ok": sum(1 for c in out["cases"] if c["verdict"] == "OK"),
    "fail": sum(1 for c in out["cases"] if c["verdict"].startswith("FAIL")),
    "error": sum(1 for c in out["cases"] if c["verdict"] == "ERROR"),
    "telegram_messages_sent": 0,
}
out["final_capture_count"] = capture_count()
print(json.dumps(out, ensure_ascii=True, default=str, indent=1))
