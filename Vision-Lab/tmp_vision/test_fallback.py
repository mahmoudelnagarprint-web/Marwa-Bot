# -*- coding: utf-8 -*-
"""عيب مسار الفشل: أي نص كان بيرجع «صباح الخير».

بنقطع السحابة صناعيًا ونقيس: التحية تفضل تحية، وأي نص تاني يرد الرد الصادق.
"""
import json
import sys

sys.path.insert(0, r"G:\ai\Naggar Print POS Agent\Vision-Lab\projects\notebook-v2")
from nb import persona, providers  # noqa: E402


def _kill_cloud(*a, **k):
    raise providers.ProviderError("شبكة مقطوعة (اختبار)")


real_chat = providers.chat
persona.providers.chat = _kill_cloud

# حالات الـLead الأربعة بالحرف + حالات إضافية تحدّي الفحص
CASES = [
    ("تحية صافية", "هاي", True),
    ("تحية + اسم", "صباح الخير يا أفكار", True),
    ("تحية + اسم تاني", "ازيك يا محمود", True),
    ("شكر", "شكرا يا فوفا", True),
    ("وداع", "سلام", True),
    ("تحية إنجليزي", "hello", True),
    ("سؤال حقيقي", "ايه أخبار الشغل؟", False),
    ("التقاط", "فكرني بكرة الساعة 5", False),
    ("طلب توليد", "اقترح 3 أفكار لتسويق الورشة", False),
    ("سؤال بلا علامة", "عامل ايه النهاردة", True),
    ("جملة طويلة بكلمة تحية", "صباح الخير يا أفكار عايز أعرف أخبار الشغل النهاردة", False),
    ("كلمة هي جوه كلام", "هي الورشة خلصت الشغلانة", False),
    ("نص فاضي", "   ", False),
    ("تحية مركّبة", "السلام عليكم يا أفكار ازيك", True),
    ("سؤال عن المهام", "عندي ايه النهاردة؟", False),
    ("تصبح على خير (وداع)", "تصبح على خير", True),
    ("تصبح على خير يا أفكار", "تصبح على خير يا أفكار", True),
    ("باي", "باي يا فوفا", True),
]

fail = 0
rows = []
try:
    for label, text, want_small in CASES:
        body, meta = persona.reply(text, chat_id=561770354)
        got_small = bool(meta.get("small_talk"))
        ok = (got_small == want_small)
        # «تصبح على خير» لازم ترد وداع، مش «صباح الخير»
        if ok and "تصبح" in text and "سلام" not in body:
            ok = False
        if not ok:
            fail += 1
        rows.append({"case": label, "in": text, "want_small_talk": want_small,
                     "got_small_talk": got_small, "ok": ok, "out": body[:70]})
finally:
    persona.providers.chat = real_chat

# اتأكد إن مفيش صف اتكتب في outbox/captures من الاختبار ده
from nb import db  # noqa: E402
leak = db.q("SELECT count(*) c FROM captures WHERE created_at > now() - interval '10 minutes'",
            one=True)
rows.append({"captures_last_10min": int(leak["c"])})

print(json.dumps({"failed": fail, "of": len(CASES), "rows": rows},
                 ensure_ascii=True, indent=1))
