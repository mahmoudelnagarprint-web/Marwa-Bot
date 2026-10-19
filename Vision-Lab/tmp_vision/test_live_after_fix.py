# -*- coding: utf-8 -*-
"""تأكيد إن المسار السحابي السليم لسه شغال بعد تعديل مسار الفشل.

نداء **واحد** بالتوالي (البوابة بترفض الطلبات المتوازية → 429).
"""
import io
import json
import sys

sys.path.insert(0, r"G:\ai\Naggar Print POS Agent\Vision-Lab\projects\notebook-v2")
from nb import persona  # noqa: E402

out = []
for text in ["ايه أخبار الشغل النهاردة؟"]:
    body, meta = persona.reply(text, chat_id=561770354, timeout=40)
    out.append({"in": text, "out": body, "len": len(body),
                "used_fallback": bool(meta.get("fallback")),
                "raw_had_think": bool(meta.get("raw_had_think")),
                "model": meta.get("model"), "provider": meta.get("provider"),
                "error": meta.get("error")})

io.open(r"G:\ai\Naggar Print POS Agent\Vision-Lab\tmp_vision\live_after.json",
        "w", encoding="utf-8").write(json.dumps(out, ensure_ascii=False, indent=1))
print("done")
