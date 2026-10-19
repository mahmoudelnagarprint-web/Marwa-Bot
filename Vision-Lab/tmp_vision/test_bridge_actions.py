# -*- coding: utf-8 -*-
"""اختبار الجسر: أفعال الكتابة على صف مؤقت + إثبات صفر إرسال تليجرام.

قواعد السلامة المطبقة هنا:
- العقدة الحيّة شغّالة (PID 19956) وبتعمل polling، فأي صف بميعاد قريب
  ممكن البوت يبعت بيه تذكير لمحمود. عشان كده: الصف المؤقت **بلا due_at**،
  والـsnooze بـ600 دقيقة (10 ساعات) — يعني مستحيل يكون «مستحق» خلال الاختبار.
- `bot.TelegramClient.call` متبوّض بحارس بيرمي لو اتنادى → أي إرسال حقيقي
  بيفشل الاختبار فورًا. الحارس بيتشال في `finally`.
- الصف المؤقت بيتمسح في `finally` وبنتأكد إنه مش موجود بعدها.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "projects" / "notebook-v2"
sys.path.insert(0, str(ROOT))

from nb import bot, bridge, db  # noqa: E402

OUT = {}
sent = []


def _guard_call(self, method, payload=None):
    sent.append({"method": method, "payload": payload})
    raise AssertionError(f"الجسر حاول يبعت تليجرام: {method}")


original = bot.TelegramClient.call
bot.TelegramClient.call = _guard_call

cid = None
try:
    # 1) صف مؤقت بلا أي ميعاد — مش ممكن يطلع تذكير
    cid = db.add_capture({
        "title": "VISION BRIDGE TEST — اتمسح بعد ثواني",
        "body": "صف اختبار للجسر",
        "kind": "task",
        "category": "غير مصنف",
        "priority": "normal",
        "source": "bridge-test",
        "confidence": 0.5,
        "routed_by": "rules",
    })
    OUT["created_id"] = cid

    # 2) done
    OUT["done"] = bridge.done(cid)
    OUT["status_after_done"] = db.scalar(
        "SELECT status FROM captures WHERE id=%s", (cid,))

    # 3) reopen
    OUT["reopen"] = bridge.reopen(cid)
    OUT["status_after_reopen"] = db.scalar(
        "SELECT status FROM captures WHERE id=%s", (cid,))

    # 4) snooze 600 دقيقة (بعيد جدًا → مستحيل يبقى مستحق)
    OUT["snooze"] = bridge.snooze(cid, 600)
    OUT["remind_at_after_snooze"] = str(db.scalar(
        "SELECT remind_at FROM captures WHERE id=%s", (cid,)))

    # 5) category
    OUT["category"] = bridge.category(cid, "ليزر")
    OUT["category_after"] = db.scalar(
        "SELECT category FROM captures WHERE id=%s", (cid,))
    OUT["needs_clar_after"] = bool(db.scalar(
        "SELECT needs_clarification FROM captures WHERE id=%s", (cid,)))

    # 6) action على معرف مش موجود → changed=False بصدق (مش نجاح كدب)
    OUT["done_missing"] = bridge.done(99999999)
    OUT["category_empty"] = bridge.category(cid, "   ")

    # 7) list باريتي تاني بعد التعديلات
    listed = bridge.list_captures(limit=50, status="all")
    OUT["list_all_has_scratch"] = any(r.get("id") == cid for r in listed)

finally:
    if cid is not None:
        bridge.delete(cid)
    bot.TelegramClient.call = original

OUT["scratch_left"] = int(db.scalar(
    "SELECT count(*) FROM captures WHERE id=%s", (cid,))) if cid else None
OUT["telegram_calls_attempted"] = sent

# كمان: البريدج نفسه مابيعملش poll ولا بيستورد حاجة بتبعت
OUT["bridge_has_send"] = any(n in ("send", "send_message", "broadcast")
                             for n in dir(bridge))

print(json.dumps(OUT, ensure_ascii=True, indent=2, default=str))
