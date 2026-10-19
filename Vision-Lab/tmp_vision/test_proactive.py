# -*- coding: utf-8 -*-
"""اختبار `proactive.flush` — التزام بالعقد + الكيبوردات.

**بلا أي تليجرام وبلا أي كتابة دائمة**: بنُنشئ صفوف outbox بمفتاح dedupe
مؤقت، وبعدين **نمسحها** في `finally`. صفر إرسال حقيقي.
"""
import json
import sys

sys.path.insert(0, r"G:\ai\Naggar Print POS Agent\Vision-Lab\projects\notebook-v2")

from nb import db, proactive   # noqa: E402

TAG = "vision-test-flush"
created = []


def cleanup():
    for i in created:
        db.x("DELETE FROM outbox WHERE id=%s", (i,))


results = {}
try:
    # 1) أشكال الكيبورد المتوقعة لكل نوع
    results["keyboards"] = {
        "reminder": proactive.keyboard_for("reminder", note_id=7),
        "task": proactive.keyboard_for("task", note_id=3),
        "briefing": proactive.keyboard_for("briefing"),
        "squad": proactive.keyboard_for("squad"),
        "pomodoro": proactive.keyboard_for("pomodoro"),
        "radar": proactive.keyboard_for("radar", project_id=5),
        "plain": proactive.keyboard_for("plain"),
        "reminder_no_id": proactive.keyboard_for("reminder"),
    }
    results["keys_reminder"] = [c for row in proactive.capture_kb(7) for _, c in row]
    results["keys_capture_kb_4"] = [c for row in proactive.capture_kb(4) for _, c in row]

    # 2) `_decode_kb`: jsonb → list-of-tuples، والقيم الفاسدة تتجاهل
    results["decode"] = {
        "none": proactive._decode_kb(None),
        "empty": proactive._decode_kb("[]"),
        "str": proactive._decode_kb('[ [["تم","cap:done:1"]] ]'),
        "bad": proactive._decode_kb("not json"),
        "list": proactive._decode_kb([[["تم", "cap:done:9"]]]),
    }

    # 3) الالتزام بالعقد: sender بالأرجمنتين (زي أي عميل قديم)
    seen_old = []

    def old_sender(chat_id, body):
        seen_old.append((chat_id, body))
        return True

    db.x("""INSERT INTO outbox(chat_id, body, kind, dedupe_key, keyboard, due_at)
            VALUES (%s,%s,%s,%s,%s, now() - interval '1 min') RETURNING id""",
         (561770354, "[vision-test] reminder", "reminder", TAG + "-old",
          json.dumps(proactive.capture_kb(1), ensure_ascii=False)))
    created.append(db.q("SELECT id FROM outbox WHERE dedupe_key=%s", (TAG + "-old",), one=True)["id"])
    results["sent_with_old_sender"] = proactive.flush(old_sender)
    results["old_sender_calls"] = seen_old
    results["sender_kb_flag"] = proactive._SENDER_TAKES_KB

    # 4) sender بيقبل kb= (زي TelegramClient.send الحقيقي)
    proactive._SENDER_TAKES_KB = None
    seen_new = []

    def new_sender(chat_id, body, kb=None, reply_kb=None):
        seen_new.append({"chat_id": chat_id, "kb": kb, "has_kb": bool(kb)})
        return True

    db.x("""INSERT INTO outbox(chat_id, body, kind, dedupe_key, keyboard, due_at)
            VALUES (%s,%s,%s,%s,%s, now() - interval '1 min')""",
         (561770354, "[vision-test] briefing", "briefing", TAG + "-new",
          json.dumps(proactive.BRIEFING_KB, ensure_ascii=False)))
    created.append(db.q("SELECT id FROM outbox WHERE dedupe_key=%s", (TAG + "-new",), one=True)["id"])
    results["sent_with_kb_sender"] = proactive.flush(new_sender)
    results["kb_sender_received"] = seen_new
    results["sender_kb_flag_after"] = proactive._SENDER_TAKES_KB

    # 5) sig حقيقي: هل TelegramClient.send بيقبل kb= فعلاً؟
    import inspect

    from nb import bot
    results["telegram_send_sig"] = str(inspect.signature(bot.TelegramClient.send))
    results["telegram_send_accepts_kb"] = "kb" in inspect.signature(
        bot.TelegramClient.send).parameters
finally:
    cleanup()
    left = db.q("SELECT count(*) AS c FROM outbox WHERE dedupe_key LIKE %s", (TAG + "%",))
    results["leftovers_after_cleanup"] = left[0]["c"] if left else None

print(json.dumps(results, ensure_ascii=True, indent=1, default=str))
