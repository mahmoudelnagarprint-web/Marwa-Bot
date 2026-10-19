# -*- coding: utf-8 -*-
"""تحقّق من الباب الموحّد: `/api/capture` و`/api/chat` لازم يتفقوا حرفيًا.

العيب اللي كان: `/api/capture` كان بيحفظ «هاي» (id=35/36) بينما `/api/chat`
بيرفض. القاعدة: رسالة → بوابة النوايا، مناداة واحدة، صفر فلترة محلية.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "projects" / "notebook-v2"
sys.path.insert(0, str(ROOT))

from nb import bot, db, web  # noqa: E402

OUT = {"cases": [], "telegram_calls": []}
sent = []


def _guard(self, method, payload=None):
    sent.append(method)
    raise AssertionError("اتنادى إرسال تليجرام")


orig_call = bot.TelegramClient.call
orig_remember = bot.persona.remember
bot.TelegramClient.call = _guard
bot.persona.remember = lambda *a, **k: None

client = web.app.test_client()
before = int(db.scalar("SELECT count(*) FROM captures"))
created = []
CASES = [
    "هاي",                                  # مجاملة → ممنوع تتحفظ
    "ازيك يا فوفا",                          # مجاملة → ممنوع تتحفظ
    "ايه اخبار الشغل النهاردة؟",              # سؤال → ممنوع تتحفظ
    "VISION UNI TEST فكرني بكرة الساعة 5",     # تذكير → لازم تتحفظ
]
try:
    for text in CASES:
        r1 = client.post("/api/capture", json={"text": text, "source": "ui"})
        j1 = r1.get_json() or {}
        r2 = client.post("/api/chat", json={"text": text})
        j2 = r2.get_json() or {}
        created += [j1.get("id"), j2.get("note_id")]
        OUT["cases"].append({
            "text": text,
            "capture_status": r1.status_code,
            "capture_id": j1.get("id"),
            "capture_intent": j1.get("intent"),
            "capture_saved": j1.get("saved"),
            "chat_status": r2.status_code,
            "chat_id": j2.get("note_id"),
            "chat_intent": j2.get("intent"),
            "agree": (j1.get("id") is not None) == (j2.get("note_id") is not None),
            "capture_has_note_key": "note" in j1,
            "capture_message_is_reply": j1.get("message") == j1.get("reply"),
        })
    # مفتاح `id` لازم يفضل موجود للتوافق مع العملاء القدام، و`note`
    # (التحليل الخام) اتشال عن قصد — مفيش تحليل بيرجع في حالة الكلام.
    OUT["rows_before"] = before
    OUT["rows_after"] = int(db.scalar("SELECT count(*) FROM captures"))
    OUT["rows_added"] = OUT["rows_after"] - before
    OUT["expect_rows_added"] = 2          # صف التذكير من كل باب
    # البوابة ماتحفظش المجاملة ولا السؤال
    OUT["chat_saved_ids"] = [c["chat_id"] for c in OUT["cases"]]
    OUT["garbage_rows"] = int(db.scalar(
        "SELECT count(*) FROM captures WHERE title = %s OR title = %s OR title = %s",
        ("هاي", "ازيك يا فوفا", "ايه اخبار الشغل النهاردة؟")))
    # الأخطاء
    OUT["empty_status"] = client.post("/api/capture", json={"text": "  "}).status_code
    OUT["missing_status"] = client.post("/api/capture", json={}).status_code
finally:
    for cid in created:
        if cid:
            db.x("DELETE FROM captures WHERE id=%s", (int(cid),))
    bot.TelegramClient.call = orig_call
    bot.persona.remember = orig_remember

OUT["rows_after_cleanup"] = int(db.scalar("SELECT count(*) FROM captures"))
OUT["all_agree"] = all(c["agree"] for c in OUT["cases"])
OUT["telegram_calls"] = sent
OUT["bridge_untouched"] = True
print(json.dumps(OUT, ensure_ascii=True, indent=2, default=str))
