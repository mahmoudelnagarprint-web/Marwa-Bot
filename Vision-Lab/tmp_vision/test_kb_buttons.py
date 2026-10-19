# -*- coding: utf-8 -*-
"""اختبار أزرار الكيبورد السفلي — **بلا أي كتابة في قاعدة البيانات**.

⚠️ درس: `_do_pomodoro` بيكتب صف في `outbox` فعليًا. أول نسخة من الاختبار ده
شغّلته من غير stub فأنشأ بومودورو حقيقي (اتلغى بعدها، وصفر رسائل اتبعتت).
القاعدة: أي معالج فيه كتابة يتعمله stub في الاختبار.
"""
import json
import sys
import time

sys.path.insert(0, r"G:\ai\Naggar Print POS Agent\Vision-Lab\projects\notebook-v2")

from nb import bot   # noqa: E402


class FakeTG:
    """عميل وهمي: بيسجّل النداءات بدل ما يرسل — صفر تليجرام."""
    def __init__(self):
        self.calls = []

    def send(self, *a, **k):
        self.calls.append((a, k))
        return {"ok": True}

    def typing(self, *a, **k):
        pass


# stub على الدالة اللي بتكتب في outbox
_orig_pomodoro = bot._do_pomodoro
bot._do_pomodoro = lambda tg, cid, minutes: f"[stub] pomodoro {minutes} دقيقة"

RESULTS = []
for label in ["🧠 أفكاري", "📋 مهام اليوم", "🔧 الورشة", "🍅 بومودورو", "بومودورو 50"]:
    tg = FakeTG()
    t0 = time.time()
    try:
        res = bot._handle_command(tg, 561770354, label)
        RESULTS.append({
            "btn": label,
            "matched": res is not None,
            "out_head": (res[0][:60] if isinstance(res, tuple) else (res or "")[:60]),
            "kb": (res[1] if isinstance(res, tuple) else None),
            "seconds": round(time.time() - t0, 2),
            "sent_to_telegram": len(tg.calls),
        })
    except Exception as e:
        RESULTS.append({"btn": label, "error": f"{type(e).__name__}: {str(e)[:150]}"})

bot._do_pomodoro = _orig_pomodoro
print(json.dumps(RESULTS, ensure_ascii=True, indent=1))
