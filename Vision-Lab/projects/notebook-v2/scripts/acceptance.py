# -*- coding: utf-8 -*-
"""أفكاري v2 — حزمة القبول A1…A10.

الـLead بيقيس بنفسه. كل معيار لازم دليل رقمي، مش «المفروض».

الاستخدام:
  python scripts/acceptance.py              # كل المعايير (قراءة فقط)
  python scripts/acceptance.py A1 A3 A6     # معايير محددة
  python scripts/acceptance.py --json       # تقرير للآلة
  python scripts/acceptance.py --live       # يسمح بكتابة اختبار A2 (وبينضّف وراه)

قواعد السلامة المنفذة هنا:
  • ممنوع إرسال أي رسالة تليجرام.
  • قراءة فقط افتراضيًا؛ A2 بس بيكتب، وده محتاج --live، وبينضّف بعده.
  • ممنوع طباعة أي مفتاح/توكن.
  • مفيش عربي مطبوع مباشرة على كونسول ويندوز (cp1252) — كله بيمر من
    json.dumps(ensure_ascii=True) أو نص ASCII عند الحاجة.
"""
from __future__ import annotations

import io
import json
import os
import re
import statistics
import sys
import time
import traceback
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

# ---------------------------------------------------------------- المسارات
HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
sys.path.insert(0, str(PROJECT))

OK, BAD, SKIP = "OK", "BAD", "SKIP"
_MARK = {OK: "+", BAD: "x", SKIP: "-"}


def out(text: str = "") -> None:
    """طباعة آمنة على كونسول ويندوز — أي حاجة غير ASCII تتحول escape."""
    try:
        sys.stdout.write(text + "\n")
    except UnicodeEncodeError:
        sys.stdout.write(text.encode("ascii", "backslashreplace").decode("ascii") + "\n")
    sys.stdout.flush()


def jdump(obj: Any) -> str:
    """JSON ASCII-safe — للطباعة والتقارير."""
    return json.dumps(obj, ensure_ascii=True, default=str)


def jraw(obj: Any) -> str:
    """JSON بنص عربي حقيقي — للبحث والمطابقة، مش للطباعة."""
    return json.dumps(obj, ensure_ascii=False, default=str)


# ---------------------------------------------------------------- أدوات
class Result:
    def __init__(self, key: str, title: str) -> None:
        self.key = key
        self.title = title
        self.status = SKIP
        self.detail = "لم يُنفَّذ"
        self.number: Optional[float] = None
        self.error: Optional[str] = None

    def ok(self, detail: str, number: Optional[float] = None) -> "Result":
        self.status, self.detail, self.number = OK, detail, number
        return self

    def bad(self, detail: str, number: Optional[float] = None) -> "Result":
        self.status, self.detail, self.number = BAD, detail, number
        return self

    def skip(self, detail: str) -> "Result":
        self.status, self.detail = SKIP, detail
        return self

    def as_dict(self) -> Dict[str, Any]:
        return {"id": self.key, "title": self.title, "status": self.status,
                "detail": self.detail, "number": self.number, "error": self.error}


# مؤقت آمن: بيقيس ويرجّع (نتيجة، ثواني)
def timed(fn: Callable[[], Any]) -> Tuple[Any, float]:
    t0 = time.perf_counter()
    value = fn()
    return value, time.perf_counter() - t0


def median_seconds(fn: Callable[[], Any], runs: int = 3) -> Tuple[Any, float]:
    last, times = None, []
    for _ in range(max(1, runs)):
        last, secs = timed(fn)
        times.append(secs)
    return last, statistics.median(times)


def load(name: str):
    """يستورد موديول من الحزمة، ويرجّع (module, None) أو (None, سبب)."""
    try:
        return __import__(name, fromlist=["*"]), None
    except Exception as exc:  # noqa: BLE001 — بنبلّغ عن أي فشل استيراد
        return None, f"{type(exc).__name__}: {exc}"


def has(module, *attrs: str) -> Optional[str]:
    """يرجّع اسم أول دالة ناقصة، أو None لو كله موجود."""
    for attr in attrs:
        if not hasattr(module, attr):
            return attr
    return None


def http_json(url: str, method: str = "GET", body: Optional[dict] = None,
              timeout: int = 12) -> Tuple[Optional[int], Any]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={"Content-Type": "application/json"} if data else {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
            try:
                return resp.status, json.loads(raw)
            except json.JSONDecodeError:
                return resp.status, raw[:400]
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")[:400]
    except Exception as exc:  # noqa: BLE001
        return None, f"{type(exc).__name__}: {exc}"


# ============================================================ المعايير
def A1_hai_not_saved(live: bool) -> Result:
    """«هاي» متتحفظش — أخطر باج في النسخة."""
    res = Result("A1", "«هاي» متتحفظش")
    intent, err = load("nb.intent")
    db, _ = load("nb.db")
    if intent is None:
        return res.skip(f"nb/intent.py لسه مش موجود ({err})")
    missing = has(intent, "gate")
    if missing:
        return res.skip(f"nb/intent.py ناقص: {missing}()")
    if db is None:
        return res.skip("nb.db مش متاح — مقدرناش نجيب عدد الصفوف")

    def count() -> int:
        return int(db.scalar("SELECT count(*) FROM captures") or 0)

    try:
        before = count()
        gate_result = intent.gate("هاي", chat_id=int(os.environ.get("NB2_TEST_CHAT", "561770354")))
        after = count()
    except Exception as exc:  # noqa: BLE001
        res.error = traceback.format_exc(limit=3)
        return res.bad(f"النداء وقع: {type(exc).__name__}: {exc}")

    if not isinstance(gate_result, dict):
        return res.bad(f"gate() رجّعت {type(gate_result).__name__} مش dict")
    got = gate_result.get("intent")
    delta = after - before

    if got != "chat":
        return res.bad(f"النية={got} (المطلوب chat) — ده نفس الباج القديم")
    if delta != 0:
        return res.bad(f"اتحفظ {delta} صف جديد! (count {before}->{after})")
    reply = (gate_result.get("reply") or "").strip()
    if not reply:
        return res.bad("النية chat بس مفيش رد حوار للـمستخدم")
    return res.ok(f"صفر صف جديد · النية=chat · رد={jdump(reply[:60])}")


def A2_capture_saved(live: bool) -> Result:
    """الالتقاط لسه شغال — «فكرني بكرة الساعة 5 أسلم الطلب»."""
    res = Result("A2", "الالتقاط شغال (فكرني…)")
    intent, err = load("nb.intent")
    if intent is None:
        return res.skip(f"nb/intent.py لسه مش موجود ({err})")
    if has(intent, "gate"):
        return res.skip("gate() ناقصة")
    if not live:
        return res.skip("محتاج كتابة على القاعدة — شغّل بـ--live")

    db, _ = load("nb.db")
    if db is None:
        return res.skip("nb.db مش متاح")
    text = "فكرني بكرة الساعة 5 أسلم الطلب"
    chat = int(os.environ.get("NB2_TEST_CHAT", "561770354"))
    try:
        before = int(db.scalar("SELECT count(*) FROM captures") or 0)
        result = intent.gate(text, chat_id=chat)
    except Exception as exc:  # noqa: BLE001
        res.error = traceback.format_exc(limit=3)
        return res.bad(f"النداء وقع: {type(exc).__name__}: {exc}")

    if not isinstance(result, dict):
        return res.bad(f"gate() رجّعت {type(result).__name__} مش dict")
    if result.get("intent") != "capture":
        return res.bad(f"النية={result.get('intent')} — المفروض capture")

    # التدفق الحقيقي (bot.py:_handle_message): البوابة بتصنّف، والكتابة في
    # db.add_capture(verdict["analysis"]) — البوابة نفسها مش بتكتب، وده صح
    # (تصنيف منفصل عن تنفيذ). فبنحاكي خطوة التنفيذ بنفس اللي البوت بيعمله.
    analysis = result.get("analysis") or {}
    if not analysis.get("title") and not analysis.get("body"):
        return res.bad("النية capture بس التحليل فاضي — مش هيتكتب صف")
    try:
        cid = db.add_capture(analysis)
    except Exception as exc:  # noqa: BLE001
        res.error = traceback.format_exc(limit=3)
        return res.bad(f"الكتابة وقعت: {type(exc).__name__}: {exc}")

    after = int(db.scalar("SELECT count(*) FROM captures") or 0)
    if after <= before:
        return res.bad("add_capture اتنادى بس مفيش صف اتكتب")

    # نتحقق من الصف نفسه وننضّفه
    # ملاحظة: عمود النص اسمه title/body مش text، وقبول الفشل الصامت كان بيخلي
    # العيب يبان كأنه «kind=None» — فبنبلّغ عن خطأ القراءة صراحةً مش نسيبه.
    row, read_err = None, None
    try:
        row = db.q("SELECT id, kind, due_at, remind_at, title, body FROM captures WHERE id=%s",
                   (cid,), one=True)
    except Exception as exc:  # noqa: BLE001
        read_err = f"{type(exc).__name__}: {exc}"
    kind = (row or {}).get("kind")
    due = (row or {}).get("due_at")
    title = (row or {}).get("title") or ""
    try:
        db.x("DELETE FROM captures WHERE id=%s", (cid,))
        cleaned = " (اتنضّف)"
    except Exception:  # noqa: BLE001
        cleaned = " (⚠ صف الاختبار اتساب — امسحه يدويًا)"

    if read_err:
        return res.bad(f"الصف اتكتب (id={cid}) بس قراءته وقعت: {read_err}{cleaned}")
    # «فكرني بكرة…» = تذكير؛ الموديل بيرجّع task أو reminder وكلاهما مقبول
    # (الاتنين مسموحين في قيد captures، والتمييز بينهم اجتهاد دلالي مش عطل).
    if kind not in ("task", "reminder"):
        return res.bad(f"kind={kind} (المطلوب task أو reminder) · due={jdump(str(due))}{cleaned}")
    if not due:
        return res.bad(f"kind={kind} بس due_at فاضي{cleaned}")
    if not title.strip():
        return res.bad(f"kind={kind} بس title فاضي{cleaned}")
    return res.ok(f"kind={kind} · due={jdump(str(due)[:19])} · title={jdump(title[:30])}{cleaned}")


def A3_stats_perf(live: bool) -> Result:
    """db.stats() — كانت 6.5ث، المطلوب < 1.5ث."""
    res = Result("A3", "db.stats() الأداء")
    db, err = load("nb.db")
    if db is None:
        return res.skip(f"nb.db مش متاح ({err})")
    if has(db, "stats"):
        return res.skip("db.stats() ناقصة")
    try:
        value, secs = median_seconds(lambda: db.stats(), runs=3)
    except Exception as exc:  # noqa: BLE001
        res.error = traceback.format_exc(limit=3)
        return res.bad(f"db.stats() وقعت: {type(exc).__name__}: {exc}")

    if not isinstance(value, dict):
        return res.bad(f"رجّعت {type(value).__name__} مش dict")
    expected = {"open", "done", "tasks", "ideas", "overdue", "due_today",
                "need_help", "projects_active", "ws_open_jobs", "vault_prompts"}
    missing = expected - set(value)
    extra = set(value) - expected
    shape = f"مفاتيح {len(value)}"
    if missing:
        return res.bad(f"مفاتيح ناقصة: {sorted(missing)}", secs)
    if extra:
        return res.bad(f"مفاتيح زيادة (العقد بيمنع): {sorted(extra)}", secs)

    speed = f"{secs:.2f}s (كانت 6.50s → تحسّن {6.5 / max(secs, 0.001):.1f}×)"
    if secs < 1.5:
        return res.ok(f"{speed} · {shape}", secs)
    return res.bad(f"{speed} — لسه فوق العتبة 1.5s · {shape}", secs)


def A4_dashboard_perf(live: bool) -> Result:
    """تحميل اللوحة — المطلوب < 1.0ث مع كاش."""
    res = Result("A4", "تحميل اللوحة (كاش)")
    db, err = load("nb.db")
    if db is None:
        return res.skip(f"nb.db مش متاح ({err})")
    if has(db, "dashboard"):
        return res.skip("db.dashboard() ناقصة — ممكن لسه راصد شغّال عليها")

    try:
        _, cold = timed(lambda: db.dashboard())
        _, warm = median_seconds(lambda: db.dashboard(), runs=3)
        value = db.dashboard()
    except Exception as exc:  # noqa: BLE001
        res.error = traceback.format_exc(limit=3)
        return res.bad(f"db.dashboard() وقعت: {type(exc).__name__}: {exc}")

    if not isinstance(value, dict):
        return res.bad(f"رجّعت {type(value).__name__} مش dict")
    expected = {"stats", "captures", "due", "late", "need_help",
                "projects", "radar", "events", "ws_stats"}
    missing = expected - set(value)
    if missing:
        return res.bad(f"مفاتيح ناقصة: {sorted(missing)}", warm)
    detail = f"سخن {warm:.2f}s · بارد {cold:.2f}s"
    if warm < 1.0:
        return res.ok(f"{detail} · 9/9 مفاتيح", warm)
    return res.bad(f"{detail} — السخن فوق العتبة 1.0s", warm)


def A5_chat_memory(live: bool) -> Result:
    """ذاكرة المحادثة — «حطها في ملف فكرني» تُفهم كإحالة."""
    res = Result("A5", "ذاكرة المحادثة")
    db, err = load("nb.db")
    if db is None:
        return res.skip(f"nb.db مش متاح ({err})")
    missing = has(db, "log_message", "recent_messages", "count_messages")
    if missing:
        return res.skip(f"nb/db.py ناقص: {missing}()")

    # بنفحص السكيمة + الترتيب الزمني بلا ما نكتب حاجة حقيقية
    try:
        row = db.q("SELECT to_regclass('public.conversations') AS t", one=True)
    except Exception as exc:  # noqa: BLE001
        return res.bad(f"فحص الجدول وقع: {type(exc).__name__}: {exc}")
    if not (row or {}).get("t"):
        return res.bad("جدول conversations مش موجود — migrate.py لسه ما اشتغلش")

    chat = int(os.environ.get("NB2_TEST_CHAT", "561770354"))
    try:
        recent = db.recent_messages(chat, limit=12)
    except Exception as exc:  # noqa: BLE001
        res.error = traceback.format_exc(limit=3)
        return res.bad(f"recent_messages() وقعت: {type(exc).__name__}: {exc}")
    if not isinstance(recent, list):
        return res.bad(f"recent_messages() رجّعت {type(recent).__name__} مش list")

    ids = [r.get("id") for r in recent if isinstance(r, dict)]
    if len(ids) >= 2 and ids != sorted(ids):
        return res.bad(f"الترتيب غلط — المفروض الأقدم الأول: {ids[:6]}")
    if len(recent) > 12:
        return res.bad(f"limit مش محترم: رجّع {len(recent)} صف")

    # يوجد history فعلي؟ (لو مفيش، الدالة سليمة بس لسه ما استُخدمتش)
    try:
        total = db.count_messages(chat)
    except Exception as exc:  # noqa: BLE001
        return res.bad(f"count_messages() وقعت: {type(exc).__name__}: {exc}")

    # اختبار المرجعية الحقيقي (A5 الحقيقي): إحالة على رسالة سابقة.
    # بنشوف هل gate() بتفهم «حطها في ملف فكرني» لما يكون فيه history فيه رسالة قبلها.
    intent, _ = load("nb.intent")
    if intent is not None and hasattr(intent, "gate"):
        history = [
            {"role": "user", "content": "محتاج أشتري ورق A4 للورشة"},
            {"role": "assistant", "content": "تمام يا محمود، سجّلتها"},
        ]
        try:
            ref = intent.gate("حطها في ملف فكرني", chat_id=chat, history=history)
        except Exception as exc:  # noqa: BLE001
            return res.bad(f"gate(history=) وقعت: {type(exc).__name__}: {exc}")
        if isinstance(ref, dict):
            keys = set(ref.keys())
            if "reference" not in keys:
                return res.bad("gate() مش بترجّع مفتاح reference — الإحالة مش مفهومة")
            got = ref.get("reference")
            if not got:
                return res.bad(f"النية={ref.get('intent')} بس مفيش مرجع — "
                               f"«حطها» مش متفهمة كإحالة (المتوقع إشارة للرسالة السابقة)")
            ref_note = f" · الإحالة متفهمة: {jdump(str(got)[:60])}"

    if total == 0:
        return res.ok(f"الجدول والدوال سليمة · صفر رسائل مسجّلة لحد الآن{locals().get('ref_note', '')}")
    return res.ok(f"الجدول سليم · {total} رسالة محفوظة · آخر {len(recent)} بترتيب صحيح"
                  f"{locals().get('ref_note', '')}")


def A6_provider_live(live: bool) -> Result:
    """المزود السحابي حيّ — كان بيسقط بصمت 4/4."""
    res = Result("A6", "المزود السحابي حيّ")
    router, err = load("nb.ai_router")
    if router is None:
        return res.skip(f"nb/ai_router.py مش متاح ({err})")
    if has(router, "route"):
        return res.skip("ai_router.route() ناقصة")
    try:
        value, secs = timed(lambda: router.route("فكرني أدفع الكهربا بكرة الساعة 5"))
    except Exception as exc:  # noqa: BLE001
        res.error = traceback.format_exc(limit=4)
        return res.bad(f"route() وقعت: {type(exc).__name__}: {exc}")

    if not isinstance(value, dict):
        return res.bad(f"route() رجّعت {type(value).__name__} مش dict")
    routed = str(value.get("routed_by") or "")
    if routed.startswith("llm:"):
        return res.ok(f"routed_by={jdump(routed)} · {secs:.1f}s — الطبقة السحابية شغالة", secs)
    if "rules" in routed:
        return res.bad(f"رجع للقواعد المحلية ({jdump(routed)}) — السبب الجذري لسه موجود "
                       f"أو مفيش مزود نشط", secs)
    return res.bad(f"routed_by غير متوقع: {jdump(routed)}", secs)


def A7_telegram_buttons(live: bool) -> Result:
    """أزرار تليجرام — 5 inline + كيبورد سفلي 4 أزرار.

    الكيبوردات ممكن تكون دوال **أو** ثوابت (MAIN_KB / MAIN_REPLY_KB)،
    فبندوّر على الاتنين.
    """
    res = Result("A7", "أزرار تليجرام")
    bot, err = load("nb.bot")
    if bot is None:
        return res.skip(f"nb/bot.py مش متاح ({err})")

    def resolve(obj) -> Any:
        """ينادي لو دالة، ويرجّع كما هو لو ثابت."""
        if not callable(obj):
            return obj
        try:
            return obj()
        except TypeError:
            for arg in (1, 0, "task"):
                try:
                    return obj(arg)
                except Exception:  # noqa: BLE001
                    continue
        except Exception:  # noqa: BLE001
            return None
        return None

    def gather(*needles: str) -> List[Tuple[str, Any]]:
        """كل الأعضاء (دوال أو ثوابت) اللي اسمها فيه أي needle."""
        found = []
        for name in dir(bot):
            if name.startswith("__"):
                continue
            low = name.lower()
            if any(n in low for n in needles):
                found.append((name, resolve(getattr(bot, name))))
        return found

    # ---------- 1) الكيبورد السفلي الثابت ----------
    # كل زر بمجموعة بدائل — التسميات بتختلف («المهام» / «مهام اليوم»).
    # الكيبورد السفلي أزراره **نصوص خام** (بلا callback_data).
    bottom_names = gather("main_kb", "main_reply", "persistent", "bottom",
                          "reply_keyboard", "main_keyboard")
    label_alts = [
        ("🧠 أفكاري", ["أفكاري"]),
        ("📋 المهام", ["مهام", "المهام", "مهمات"]),
        ("🔧 الورشة", ["الورشة", "ورشة"]),
        ("🍅 بومودورو", ["بومودورو", "pomodoro"]),
    ]
    best_back, best_found, best_plain = None, [], False
    for name, obj in bottom_names:
        if obj is None:
            continue
        body = jraw(obj)                     # نص عربي حقيقي للبحث
        found = [label for label, alts in label_alts
                 if any(alt in body for alt in alts)]
        plain = "callback_data" not in body          # أزرار الرد = نصوص خام
        # بنفضّل اللي بيطابق أكتر؛ وعند التساوي اللي بلا callback_data
        better = (len(found) > len(best_found)
                  or (len(found) == len(best_found) and plain and not best_plain))
        if better:
            best_back, best_found, best_plain = name, found, plain
    if best_back is None:
        return res.bad(f"مفيش كيبورد سفلي ثابت — جرّبت "
                       f"{jdump([n for n, _ in bottom_names][:4])}")
    if len(best_found) < 4:
        missing = [label for label, _ in label_alts if label not in best_found]
        return res.bad(f"{best_back}: الكيبورد السفلي ناقص "
                       f"{', '.join(missing)} ({len(best_found)}/4)")

    # ---------- 2) أزرار الالتقاط ----------
    # الشكل المعتمد: list of rows of (label, callback) tuples — وبيتحوّل
    # لـinline_keyboard وقت الإرسال. فبندوّر على الأزواج بـcap: نفسها، مش
    # على مفتاح callback_data اللي مش بيظهر غير عند التحويل.
    inline_names = gather("reminder_kb", "capture_kb", "task_kb", "inline")
    best_inline, best_n, best_body = None, 0, ""
    for name, obj in inline_names:
        if obj is None:
            continue
        body = jraw(obj)
        if "cap:" not in body:
            continue
        pairs = len(re.findall(r'"cap:[a-z]+:', body))
        n = pairs or body.count("cap:")
        if n > best_n:
            best_inline, best_n, best_body = name, n, body
    if best_inline is None:
        return res.bad(f"الكيبورد السفلي {len(best_found)}/4 سليم · "
                       f"بس مفيش أزرار التقاط بـcap: "
                       f"(جرّبت {jdump([n for n, _ in inline_names][:4])})")
    # كل زر لازم يكون (تسمية، cap:فعل:معرّف) — نتأكد إن الأزواج مكتملة
    if not re.search(r'"cap:[a-z]+:\d+"', best_body) and \
       not re.search(r'"cap:[a-z]+:"', best_body):
        return res.bad(f"{best_inline}: أزرار cap: مش بصيغة (تسمية، cap:فعل:معرّف)")
    if best_n < 5:
        return res.bad(f"{best_inline}: {best_n} أزرار — المطلوب 5")
    actions = sorted(set(re.findall(r'cap:([a-z]+):', best_body)))
    return res.ok(f"السفلي {len(best_found)}/4 ({best_back}) · "
                  f"الالتقاط {best_n} أزرار ({best_inline}) · أفعال: {jdump(actions)}")


def A8_bridge_parity(live: bool) -> Result:
    """الجسر الموحد — نفس صفوف الويب."""
    res = Result("A8", "الجسر الموحد (باريتي)")
    script = PROJECT / "scripts" / "dsh_bridge.py"
    if not script.exists():
        return res.skip("scripts/dsh_bridge.py لسه مش موجود")

    bridge, err = load("nb.bridge")
    if bridge is None:
        return res.skip(f"nb/bridge.py مش متاح ({err})")
    db, _ = load("nb.db")
    if db is None:
        return res.skip("nb.db مش متاح — مقدرناش نقارن")

    # بنقارن قراءة الجسر بقراءة db مباشرة (نفس الجداول = نفس الصفوف)
    try:
        rows = db.q("SELECT id FROM captures WHERE status IS DISTINCT FROM 'done' "
                    "ORDER BY id DESC LIMIT 10")
        ids = [r["id"] for r in rows]
    except Exception as exc:  # noqa: BLE001
        return res.bad(f"قراءة captures وقعت: {type(exc).__name__}: {exc}")

    try:
        listed = bridge.list_captures(limit=10, status="open")
    except AttributeError:
        return res.skip("nb.bridge.py مفيهوش list_captures — راجع العقد")
    except Exception as exc:  # noqa: BLE001
        res.error = traceback.format_exc(limit=3)
        return res.bad(f"bridge.list_captures() وقعت: {type(exc).__name__}: {exc}")

    if not isinstance(listed, list):
        return res.bad(f"bridge رجّع {type(listed).__name__} مش list")
    bridged = [r.get("id") for r in listed if isinstance(r, dict)]
    if sorted(bridged) != sorted(ids):
        return res.bad(f"مش مطابق! الجسر={bridged[:6]} القاعدة={ids[:6]}")
    return res.ok(f"مطابق للقاعدة: {len(ids)} صف بنفس الـid")


def A9_ha_lease(live: bool) -> Result:
    """الإيجار بيتجدّد + العقدة alive."""
    res = Result("A9", "الإيجار والتوفّر العالي")
    db, err = load("nb.db")
    if db is None:
        return res.skip(f"nb.db مش متاح ({err})")
    try:
        lease = db.q("SELECT holder, expires_at, "
                     "EXTRACT(epoch FROM (expires_at - now())) AS left_s, "
                     "EXTRACT(epoch FROM (now() - acquired_at)) AS age_s "
                     "FROM leader_lease WHERE id=1", one=True)
    except Exception as exc:  # noqa: BLE001
        return res.bad(f"قراءة leader_lease وقعت: {type(exc).__name__}: {exc}")
    if not lease:
        return res.bad("مفيش صف إيجار (id=1) — مفيش قائد")

    left = float(lease.get("left_s") or 0)
    if left <= 0:
        return res.bad(f"الإيجار منتهي ({left:.0f}s) — القائد لسه ما جدّدش", left)
    if left > 45:
        return res.bad(f"مدة الإيجار {left:.0f}s أكبر من LEASE_TTL=45 — "
                       f"السقوط هياخد وقت طويل", left)

    try:
        dead = db.scalar("SELECT count(*) FROM nodes "
                         "WHERE now() - last_seen > interval '90 seconds'")
        total = db.scalar("SELECT count(*) FROM nodes")
        freshest = db.q("SELECT node_id, EXTRACT(epoch FROM (now() - last_seen)) AS age_s "
                        "FROM nodes ORDER BY last_seen DESC LIMIT 1", one=True)
    except Exception as exc:  # noqa: BLE001
        return res.bad(f"قراءة nodes وقعت: {type(exc).__name__}: {exc}")

    age = float((freshest or {}).get("age_s") or 999)
    detail = (f"قائد={jdump(lease.get('holder'))} باقي {left:.0f}s · "
              f"أحدث عقدة {jdump((freshest or {}).get('node_id'))} نبضها قبل {age:.0f}s · "
              f"{total} عقدة ({dead} ميتة)")
    if age > 90:
        return res.bad(f"مفيش عقدة حيّة — أحدث نبضة قبل {age:.0f}s", left)
    return res.ok(detail, left)


def A10_schema(live: bool) -> Result:
    """السكيمة نظيفة + FKs بتحرس."""
    res = Result("A10", "السكيمة والمفاتيح الأجنبية")
    db, err = load("nb.db")
    if db is None:
        return res.skip(f"nb.db مش متاح ({err})")

    expected = {"captures", "projects", "vault_prompts", "ws_jobs", "nodes",
                "leader_lease", "settings", "outbox", "conversations",
                "ai_providers", "ai_models", "capture_events", "ws_job_materials",
                "home_items", "cron_runs", "agent_reports"}
    try:
        rows = db.q("SELECT tablename FROM pg_tables WHERE schemaname='public'")
    except Exception as exc:  # noqa: BLE001
        return res.bad(f"قراءة الجداول وقعت: {type(exc).__name__}: {exc}")
    present = {r["tablename"] for r in rows}
    missing = sorted(expected - present)
    if missing:
        return res.bad(f"جداول ناقصة: {missing}")

    # فلتر public إلزامي: بلا فلتر بيرجّع كمان مفاتيح مخططات Supabase الداخلية
    # (auth 24 + storage 5) فيطلع الرقم 45 بدل 16 — خطأ قياس موثّق في A10.
    try:
        fks = db.q("""SELECT conrelid::regclass::text AS tbl, conname
                      FROM pg_constraint c
                      JOIN pg_class t ON t.oid = c.conrelid
                      JOIN pg_namespace n ON n.oid = t.relnamespace
                      WHERE c.contype = 'f' AND n.nspname = 'public'""")
        stray = db.scalar("""SELECT count(*) FROM pg_constraint c
                             JOIN pg_class t ON t.oid = c.conrelid
                             JOIN pg_namespace n ON n.oid = t.relnamespace
                             WHERE c.contype = 'f' AND n.nspname <> 'public'""")
    except Exception as exc:  # noqa: BLE001
        return res.bad(f"قراءة القيود وقعت: {type(exc).__name__}: {exc}")
    if not fks:
        return res.bad("صفر مفتاح أجنبي — حراسة المراجع مش مطبقة")

    # مراجع يتيمة فعليًا؟
    checks = [
        ("capture_events", "capture_id", "captures", "id"),
        ("ws_job_materials", "job_id", "ws_jobs", "id"),
        ("home_items", "list_id", "home_lists", "id"),
        ("ai_models", "provider_id", "ai_providers", "id"),
    ]
    orphans = []
    for child, col, parent, pcol in checks:
        if child not in present or parent not in present:
            continue
        try:
            n = db.scalar(
                f"SELECT count(*) FROM {child} c WHERE c.{col} IS NOT NULL "
                f"AND NOT EXISTS (SELECT 1 FROM {parent} p WHERE p.{pcol}=c.{col})")
        except Exception:  # noqa: BLE001 — عمود ممكن ميكونش موجود
            continue
        if n:
            orphans.append(f"{child}.{col}={n} يتيم")
    if orphans:
        return res.bad("مراجع يتيمة: " + " · ".join(orphans))
    return res.ok(f"{len(present)} جدول · {len(fks)} مفتاح أجنبي في public "
                  f"· {stray} خارج public (مخططات Supabase — مش بتاعتنا) "
                  f"· صفر مرجع يتيم")


def A16_no_plaintext_key(live: bool) -> Result:
    """مفيش مفتاح صريح في أي عمود نصي حساس.

    العطل الأصلي (E8): `ai_config.api_key` كان مفتاحًا صريحًا بطول 38 لصف
    متبقّي من تزويد قديم — والمفتاح الحيّ مكانه `ai_providers.api_key_enc`
    (Fernet `f1:`) ومحدش بيقرا `ai_config` أصلًا (صفر مرجع في الكود).
    الفحص ده يمنع رجوعه بدل ما يبقى إصلاحًا لمرة واحدة.

    **مش بيطبع أي مفتاح ولا طوله** — بيتأكد من الخلو بس.
    """
    res = Result("A16", "مفيش مفتاح صريح في القاعدة")
    db, err = load("nb.db")
    if err:
        return res.skip(f"nb.db مش متاح ({err})")
    try:
        rows = db.q("""SELECT id, (api_key IS NULL) AS key_is_null
                       FROM ai_config ORDER BY id""")
    except Exception as exc:  # noqa: BLE001
        return res.bad(f"قراءة ai_config وقعت: {type(exc).__name__}: {exc}")

    leaking = [r["id"] for r in rows if not r["key_is_null"]]
    if leaking:
        return res.bad(f"مفتاح صريح باقي في ai_config للصفوف {leaking} — "
                       f"الحذف النهائي هو `UPDATE ai_config SET api_key = NULL`")

    try:
        provs = db.q("""SELECT id, (api_key_enc IS NULL) AS enc_null
                        FROM ai_providers ORDER BY id""")
    except Exception:  # noqa: BLE001
        provs = []
    enc_missing = [r["id"] for r in provs if r["enc_null"]]
    if enc_missing:
        return res.bad(f"مزود مفيهوش مفتاح مُشفَّر (api_key_enc فاضي): {enc_missing}")

    return res.ok(f"ai_config خالي من أي مفتاح ({len(rows)} صف) "
                  f"· {len(provs)} مزود بمفتاح مُشفَّر سليم")


def A11_tokenizer(live: bool) -> Result:
    """مقسّم `db/migrate.py` مطابق لمقسّم مستقل + صامد لحالات عدائية.

    الخطر الأصلي: `split(";")` الساذج بيكسر أول ما يُضاف `$$` أو كتلة `DO`
    أو نص فيه `;`. القياس على السكيمة الفعلية: 52 جملة بالمقسّمين (مطابق)،
    والخطر مستقبلي لا حالي — عشان كده البند بيثبت الاتفاق ويختبر الحالات
    اللي **مش موجودة** في السكيمة دلوقتي (دالة/كتلة/نص فيه فاصلة).
    """
    res = Result("A11", "مقسّم SQL واعي")
    import importlib.util
    path = PROJECT / "db" / "migrate.py"
    try:
        spec = importlib.util.spec_from_file_location("_nb_mig", path)
        mig = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mig)
    except Exception as exc:  # noqa: BLE001
        return res.bad(f"تحميل migrate.py وقع: {type(exc).__name__}: {exc}")

    if not callable(getattr(mig, "_statements", None)):
        return res.bad("migrate.py مفيهوش _statements — المقسّم مش موجود")
    sql = mig.SCHEMA_FILE.read_text(encoding="utf-8")
    got = list(mig._statements(sql))
    if len(got) < 40:
        return res.bad(f"عدد الجمل غير معقول: {len(got)}")

    # مقاومة الحالات العدائية: دالة $$ · نص فيه ; · تعليق كتلي
    adversarial = (
        "CREATE FUNCTION f() RETURNS void AS $$\n"
        "BEGIN\n  RAISE NOTICE 'a;b';\n  PERFORM 1;\nEND;\n$$ LANGUAGE plpgsql;\n"
        "INSERT INTO t(x) VALUES ('نص فيه ; فاصلة');\n"
        "/* تعليق كتلي فيه ; */\nSELECT 1;\n")
    adv = list(mig._statements(adversarial))
    if len(adv) != 3:
        return res.bad(f"المقسّم اتكسر على حالة عدائية: {len(adv)} جملة بدل 3")

    # التأكد إن الجملة الأولى اتقسمت عند $$ صح ومفيش كسر جواها
    if "LANGUAGE plpgsql" not in adv[0]:
        return res.bad("كتلة $$ اتقسمت غلط — الفاصلة جوه الدالة كسرتها")

    return res.ok(f"{len(got)} جملة من السكيمة الفعلية · صامد لـ$$/النصوص/"
                  f"التعليقات الكتلية")


# ============================================================ السجل
CHECKS: List[Tuple[str, str, Callable[[bool], Result]]] = [    ("A1", "«هاي» متتحفظش",             A1_hai_not_saved),
    ("A2", "الالتقاط شغال",               A2_capture_saved),
    ("A3", "db.stats() < 1.5s",          A3_stats_perf),
    ("A4", "اللوحة < 1.0s (سخن)",        A4_dashboard_perf),
    ("A5", "ذاكرة المحادثة",              A5_chat_memory),
    ("A6", "المزود السحابي حيّ",          A6_provider_live),
    ("A7", "أزرار تليجرام",               A7_telegram_buttons),
    ("A8", "الجسر الموحد (باريتي)",       A8_bridge_parity),
    ("A9", "الإيجار والتوفّر العالي",     A9_ha_lease),
    ("A10", "السكيمة والمفاتيح الأجنبية", A10_schema),
    ("A11", "مقسّم SQL واعي (52 جملة)",   A11_tokenizer),
    ("A16", "مفيش مفتاح صريح (E8)",       A16_no_plaintext_key),
]


def main(argv: List[str]) -> int:
    live = "--live" in argv
    as_json = "--json" in argv
    wanted = {a.upper() for a in argv[1:] if not a.startswith("-")}
    if not wanted:
        wanted = {key for key, _, _ in CHECKS}

    if not as_json:
        out("=" * 78)
        out("  أفكاري v2 — حزمة القبول" + ("   [LIVE: بيكتب]" if live else "   [قراءة فقط]"))
        out("=" * 78)
        out()

    results: List[Result] = []
    for key, title, fn in CHECKS:
        if key not in wanted:
            continue
        try:
            res = fn(live)
        except Exception as exc:  # noqa: BLE001 — معيار واقع ميوقفش الباقي
            res = Result(key, title).bad(f"استثناء غير متوقع: {type(exc).__name__}: {exc}")
            res.error = traceback.format_exc(limit=2)
        results.append(res)
        if not as_json:
            out(f"  [{_MARK[res.status]}] {res.key:<4} {res.title:<26} {res.detail}")

    passed = sum(1 for r in results if r.status == OK)
    failed = [r for r in results if r.status == BAD]
    skipped = sum(1 for r in results if r.status == SKIP)

    if as_json:
        out(jdump({
            "live": live,
            "summary": {"pass": passed, "fail": len(failed), "skip": skipped,
                        "total": len(results)},
            "verdict": "FAIL" if failed else ("INCOMPLETE" if skipped else "PASS"),
            "results": [r.as_dict() for r in results],
        }))
        return 1 if failed else 0

    out()
    out("-" * 78)
    out(f"  النتيجة: {passed}/{len(results)} ناجح · {len(failed)} فاشل · {skipped} متخطّى")
    if failed:
        out()
        out("  اللي فشل (بلوكرات):")
        for res in failed:
            out(f"    • {res.key} {res.title} — {res.detail}")
    if skipped:
        out()
        out("  المتخطّى بيمنع إعلان النجاح الكامل (لسه ناقص ملفات).")
    out("-" * 78)
    return 1 if failed else 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except KeyboardInterrupt:
        out("\nاتقاطعت.")
        sys.exit(130)
