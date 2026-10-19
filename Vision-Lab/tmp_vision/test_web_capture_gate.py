# -*- coding: utf-8 -*-
"""هل `/api/capture` (زرار الويب) بيمر على بوابة النوايا؟ — قياس مش تخمين.

A1 في العقد: «هاي» ما تتحفظش. لو صندوق الكتابة في الويب بيستدعي
`ai_router.route` مباشرة (مش `bot.process_text`)، يبقى نفس العيب E3 راجع
من باب الويب — وده بيمس «مصدر واحد للالتقاط» اللي هو بند في task-2.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "projects" / "notebook-v2"
sys.path.insert(0, str(ROOT))

from nb import bot, db, web  # noqa: E402

OUT = {}
sent = []


def _guard(self, method, payload=None):
    sent.append(method)
    raise AssertionError("اتنادى إرسال تليجرام")


orig = bot.TelegramClient.call
bot.TelegramClient.call = _guard
orig_remember = bot.persona.remember
bot.persona.remember = lambda *a, **k: None

client = web.app.test_client()
before = int(db.scalar("SELECT count(*) FROM captures"))

CASES = ["هاي", "ايه اخبار الشغل النهاردة؟", "VISION GATE TEST فكرني بكرة"]
created = []
try:
    for text in CASES:
        # (أ) مسار الويب القديم /api/capture
        r1 = client.post("/api/capture", json={"text": text, "source": "ui"})
        j1 = r1.get_json() or {}
        # (ب) المسار الموحد الجديد /api/chat
        r2 = client.post("/api/chat", json={"text": text})
        j2 = r2.get_json() or {}
        created += [j1.get("id"), j2.get("note_id")]
        OUT[text] = {
            "api_capture_status": r1.status_code,
            "api_capture_saved_id": j1.get("id"),
            "api_chat_status": r2.status_code,
            "api_chat_intent": j2.get("intent"),
            "api_chat_saved_id": j2.get("note_id"),
            "agree": bool(j1.get("id")) == bool(j2.get("note_id")),
        }
    OUT["rows_before"] = before
    OUT["rows_after"] = int(db.scalar("SELECT count(*) FROM captures"))
    OUT["rows_added"] = OUT["rows_after"] - before
finally:
    for cid in created:
        if cid:
            db.x("DELETE FROM captures WHERE id=%s", (int(cid),))
    bot.TelegramClient.call = orig
    bot.persona.remember = orig_remember

OUT["rows_after_cleanup"] = int(db.scalar("SELECT count(*) FROM captures"))
OUT["telegram_calls"] = sent
print(json.dumps(OUT, ensure_ascii=True, indent=2, default=str))
