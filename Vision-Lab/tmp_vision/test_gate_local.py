# -*- coding: utf-8 -*-
"""فحص بوابة النوايا محليًا (بلا أي نداء شبكة) — خارج المشروع."""
import json
import sys

sys.path.insert(0, r"G:\ai\Naggar Print POS Agent\Vision-Lab\projects\notebook-v2")

from nb import intent, persona, providers   # noqa: E402
import nb.ai_router as ai_router            # noqa: E402

CASES = [
    # (نص، النية المتوقعة، تحية صافية؟)
    ("هاي", "chat", True),
    ("أهلاً", "chat", True),
    ("صباح الخير", "chat", True),
    ("شكرا يا فوفا", "chat", True),
    ("سلام", "chat", True),
    # الأسئلة: محادثة، لكن **مش** مسار التحية الجاهز ← لازم تروح للموديل
    ("عامل ايه النهاردة؟", "chat", False),
    ("ازيك يا فوفا؟", "chat", False),
    ("مين انت؟", "chat", False),
    ("إيه الأخبار؟", "chat", False),
    ("انت بتعرف تعمل ايه؟", "chat", False),
    # التقاط
    ("فكرني بكرة الساعة 5 أسلم الطلب", "capture", False),
    ("احفظ: العميل طلب 20 درع ليزر", "capture", False),
    ("لازم أشتري خشب MDF", "capture", False),
    ("حطها في ملف فكرني", "capture", False),
    ("سلم الطلب بكرة", "capture", False),
]

HIST = [{"role": "user", "content": "العميل أحمد طلب 20 درع ليزر"},
        {"role": "assistant", "content": "تمام يا أفكار"}]

out, failed = [], 0
for text, expected, pure in CASES:
    past = HIST if intent.is_reference(text) else []
    res = intent.gate(text, chat_id=None, history=past, use_cloud=False)
    greeting = intent.looks_like_greeting(text)
    ok = (res["intent"] == expected) and (greeting == pure)
    failed += 0 if ok else 1
    out.append({"text": text, "intent": res["intent"], "expected": expected,
                "greeting_trap": greeting, "expect_pure_greeting": pure,
                "ok": ok, "reason": res["reason"]})

# ردود النماذج: تأكيد إن التفكير بيتشال قبل العرض
out.append({"check": "strip_reasoning(<think>)",
            "value": providers.strip_reasoning(
                "<think>أفكر في الإجابة… المستخدم بيقول هاي</think>أهلاً يا محمود!")[:80]})
out.append({"check": "strip_reasoning(unclosed)",
            "value": providers.strip_reasoning("<think>لسه بفكر ومقطوع")[:80]})
out.append({"check": "extract_json(json + كلام بعده)",
            "value": ai_router.extract_json('{"kind":"task"}\n# تذكير\n- حاجة\n')})
out.append({"check": "extract_json(كائنين ورا بعض)",
            "value": ai_router.extract_json('{"kind":"note"}{"kind":"task"}')})

print(json.dumps(out, ensure_ascii=True, indent=1))
print("FAILED:", failed, "of", len(CASES))
