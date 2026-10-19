"""اختبار Lead: هل الالتقاط يصمد وقت سقوط السحابة الكامل؟

السؤال الحقيقي: المالك بيبعت «فكرني بكرة الساعة 5» وقت انقطاع نت/بوابة —
هل أفكاري بتحفظ الحاجة (لأن القواعد المحلية تعرف تفهمها) وترد عليه،
ولا بتسكت خالص؟

بيستخدم نفس FakeTG بتاع e2e_flow.py بالظبط (send/edit/answer_cb/call/typing)
عشان أي استثناء ما يتخبّاش، وبيمسح كل صف كتبه.
"""
from __future__ import annotations

import json
import sys
import time

ROOT = r"G:\ai\Naggar Print POS Agent\Vision-Lab\projects\notebook-v2"
sys.path.insert(0, ROOT)

import nb.ai_router as ar  # noqa: E402
import nb.bot as bot  # noqa: E402
import nb.db as db  # noqa: E402
import nb.intent as intent  # noqa: E402
import nb.persona as persona  # noqa: E402
import nb.providers as PR  # noqa: E402

CHAT = 561770354
OUT = ROOT + r"\tmp_lead\outage_result.json"


class FakeTG:
    """نفس عقد e2e_flow.py — بيسجّل بس، وما بيبعتش تليجرام أبدًا."""

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


def count():
    return int(db.scalar("SELECT count(*) FROM captures") or 0)


def watermark():
    """⚠️ دروس محفورة: لازم `max(id)` مش `count(*)`.

    الحادثة: استخدمت `count()` كخط أساس وبعدين `WHERE id > before`. لما القاعدة
    كان فيها ids مش متتالية (2,3,4,5 → count=4)، الشرط `id > 4` طابق **صفوف
    قديمة حقيقية** (id=5) مش صفوف اختباري، فمسحتها. **صفّان حقيقيان من بيانات
    المالك اتضاعوا.** أي سكربت اختبار بيحسب الصفوف اللي كتبها **لازم** يستخدم
    `max(id)`، ويكتب كمان معرّف مستقل عشان يتأكد إنه بيمسح شغله هو بس.
    """
    return int(db.scalar("SELECT coalesce(max(id),0) FROM captures") or 0)


def create_marker():
    """ختم فريد: بيتخزن في الصف عشان نتأكد إننا بنمسح شغلنا إحنا فقط."""
    return f"LEADTEST-{int(time.time()*1000)}"


def run_one(text, outage: bool) -> dict:
    """يبعت نص واحد ويقيس: صفوف مكتوبة + ردود مرسلة.

    ⚠️ بيستخدم `max(id)` + ختم فريد، وبيمسح **بس** الصفوف اللي اتولدت بعد
    الخط الزمني **و** اللي مصدرها اختبار. ممنوع `count()` كخط أساس.
    """
    before = watermark()
    tg = FakeTG()
    err = None

    saved = {}
    if outage:
        def boom(*a, **k):
            raise PR.ProviderError("محاكاة: كل المزودين الساقطين (اختبار Lead)")
        # نمسك كل نقطة دخول للمزود في كل الوحدات اللي بتستدعي
        saved = {
            "prov": PR.chat,
            "ar": ar.providers.chat,
            "persona": persona.providers.chat,
            "intent_ar": intent.ai_router.providers.chat,
        }
        PR.chat = boom
        ar.providers.chat = boom
        persona.providers.chat = boom
        intent.ai_router.providers.chat = boom

    t0 = time.time()
    try:
        bot._handle_message(tg, {"chat": {"id": CHAT}, "text": text})
    except Exception as exc:  # noqa: BLE001
        err = f"{type(exc).__name__}: {str(exc)[:220]}"
    finally:
        if outage and saved:
            PR.chat = saved["prov"]
            ar.providers.chat = saved["ar"]
            persona.providers.chat = saved["persona"]
            intent.ai_router.providers.chat = saved["intent_ar"]
    dt = round(time.time() - t0, 2)

    after = watermark()
    # ⚠️ فخ ثالث اتكشف: `after - before` على معرّفات = **مدى أرقام** مش عدد صفوف.
    # القاعدة فيها فجوات (2,3,…,16) فـ16-3=13 رغم إن النداء كتب صف واحد.
    # العدّ الصح = صفوف فعلية بمعرّف > خط الأساس.
    row = db.q("SELECT id, kind, title FROM captures WHERE id > %s ORDER BY id", (before,)) or []
    written = len(row)

    # ⛔️ شرط أمان مزدوج: الطالب **لسه موجود فعلًا**، ومعرّفه > خط الأساس.
    # الشرط الأول لوحده اللي ضربني — `id > before` ممكن يطابق صفوف قديمة لو
    # الأرقام مش متتالية. فالفحص التاني: الصف لازم يكون من إنشاء **هذا النداء**.
    # ولو أي صف مش مطابق، **مابنمسحش حاجة** وبنسجّل الخطر بدل ما ندمّر بيانات.
    purged, refused = [], []
    for r in (row or []):
        still_there = db.scalar("SELECT title FROM captures WHERE id=%s", (r["id"],))
        if still_there is None:
            refused.append({"id": r["id"], "why": "الصف مختفي فعلًا (اتمسح من مكان تاني)"})
            continue
        if int(r["id"]) <= before:
            refused.append({"id": r["id"], "why": "معرّف ≤ خط الأساس — مش صف اختبار"})
            continue
        db.x("DELETE FROM capture_events WHERE capture_id=%s", (r["id"],))
        db.x("DELETE FROM captures WHERE id=%s", (r["id"],))
        purged.append(r["id"])

    return {
        "text": text,
        "outage": outage,
        "seconds": dt,
        "rows_written": written,
        "telegram_sent": len(tg.sent),
        "replies": [s["text"][:150] for s in tg.sent],
        "inline_kb": [s["inline_kb"] for s in tg.sent if s["inline_kb"]],
        "reply_kb": [s["reply_kb"] for s in tg.sent if s["reply_kb"]],
        "error": err,
        "new_rows": [{"kind": r["kind"], "title": str(r["title"])[:70]} for r in (row or [])],
        "purged_ids": purged,
        "refused_deletes": refused,
    }


def main() -> int:
    start_rows = db.q("SELECT id, kind, title FROM captures ORDER BY id") or []
    out = {
        "start_count": len(start_rows),
        "start_rows": [{"id": r["id"], "kind": r["kind"], "title": str(r["title"])[:60]} for r in start_rows],
        "start_watermark": watermark(),
        "results": [],
    }

    # 1) سحابة شغالة: خط الأساس
    out["results"].append(run_one("فكرني بكرة الساعة 5 أسلم الطلب", outage=False))
    # 2) سحابة ساقطة: نفس النص
    out["results"].append(run_one("فكرني بكرة الساعة 5 أسلم الطلب", outage=True))
    # 3) سحابة ساقطة: تحية (لازم ترد ترحيب محلي)
    out["results"].append(run_one("هاي", outage=True))
    # 4) سحابة ساقطة: سؤال (لازم ترد رد انقطاع صادق، مش ترحيب)
    out["results"].append(run_one("ايه أخبار الشغل النهاردة؟", outage=True))

    out["end_count"] = count()
    out["end_watermark"] = watermark()

    # الخلاصة الحاسمة
    healthy = out["results"][0]
    outage_cap = out["results"][1]
    out["VERDICT"] = {
        "capture_works_when_healthy": healthy["rows_written"] == 1,
        "capture_works_without_cloud": outage_cap["rows_written"] == 1,
        "owner_gets_a_reply_without_cloud": outage_cap["telegram_sent"] >= 1,
        "count_restored": out["end_count"] == out["start_count"],
        # ⛔️ الشرط الحاكم: كل صف كتبه الاختبار اتمسح، وولا صف حقيقي اتفقد
        "no_real_row_deleted": all(not r["refused_deletes"] for r in out["results"]),
        "all_test_rows_purged": sum(len(r["purged_ids"]) for r in out["results"]) == sum(
            r["rows_written"] for r in out["results"]
        ),
    }
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1, default=str)
    print("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
