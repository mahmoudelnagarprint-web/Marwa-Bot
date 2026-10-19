# -*- coding: utf-8 -*-
"""قياس حيّ: هل persona.reply بترجّع تفكير خام؟ وهل الأسئلة بتروح للموديل؟

بيشغّل الدالة الحقيقية (مش محاكاة) — الرد اللي بيتعرض للمستخدم هو اللي بيتقاس.
"""
import json
import sys
import time

sys.path.insert(0, r"G:\ai\Naggar Print POS Agent\Vision-Lab\projects\notebook-v2")

from nb import intent, persona, providers   # noqa: E402

QUESTIONS = ["عامل ايه النهاردة؟", "ازيك يا فوفا؟"]

out = []
for q in QUESTIONS:
    # 1) البوابة: النية + المسار (بلا شبكة)
    verdict = intent.gate(q, chat_id=None, history=[], use_cloud=False)
    # 2) الرد الحقيقي من فوفا
    t0 = time.time()
    answer, meta = persona.reply(q, chat_id=None)
    elapsed = round(time.time() - t0, 2)
    out.append({
        "q": q,
        "gate_intent": verdict["intent"],
        "gate_reason": verdict["reason"],
        "greeting_trap": intent.looks_like_greeting(q),
        "answer": answer,
        "answer_has_think_tag": ("<think" in (answer or "").lower()
                                 or "</think" in (answer or "").lower()),
        "answer_has_reasoning_tag": "<reasoning" in (answer or "").lower(),
        "raw_had_think": meta.get("raw_had_think"),
        "raw_len": meta.get("raw_len"),
        "answer_len": len(answer or ""),
        "fallback": meta.get("fallback"),
        "model": meta.get("model"),
        "finish_reason": meta.get("finish_reason"),
        "completion_tokens": meta.get("completion_tokens"),
        "attempts": meta.get("attempts"),
        "reasoning_stripped": meta.get("reasoning_stripped"),
        "seconds": elapsed,
    })

# 3) تنضيف نصوص مصنوعة: التفكير مايتعرضش أبدًا
out.append({"check": "strip full think block",
            "out": providers.strip_reasoning(
                "<think>المستخدم بيسأل عن حالي. لازم أرد بالمصري.</think>"
                "الحمد لله تمام يا محمود، إنت عامل ايه؟")})
out.append({"check": "strip think + preamble + answer",
            "out": providers.strip_reasoning(
                "<thinking>reasoning here</thinking>\n\nأهلاً يا أفكار!")})

print(json.dumps(out, ensure_ascii=True, indent=1))
