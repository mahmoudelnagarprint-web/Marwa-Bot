# -*- coding: utf-8 -*-
"""مناداة الفريق (R6) — النوتبوك **هو** اللي يسأل الوكلاء.

الفكرة: النوتبوك مش بس بيستقبل تقارير — بينده كل وكيل بنفسه ويسأله:
«عندك ملاحظة أو نوت أو تذكير؟» ويجمّع الردود في ملخص واحد للمالك.

المبادئ:
- **مصدر واحد للحقيقة**: بنستخدم المُنسّق المحلي (`orchestrator.core.Orquesta`)
  بنفس صيغة النداء المعتمدة «يا <اسم>» — مفيش منطق وكلاء مكرر هنا.
- **بلا اختراع**: لو وكيل ما ردّش أو حصل خطأ، بنقول ده صراحةً في الملخص.
- **بلا إغراق**: ردود عادية تُعلَّم كمقروءة فورًا، والمهمة بس (severity=warn)
  هي اللي تفضل ظاهرة في الملخص الصباحي و`/api/agents/reports`.
- **مرة واحدة في اليوم**: الحجز ذري عبر جدول `cron_runs` — فلو العقدتين شغالين،
  اللي يكسب القيادة بس هو اللي ينادي الفريق.
"""
from __future__ import annotations

import sys
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from nb import config, db, retail

# ------------------------------------------------------------------ التشكيلة
# كل وكيل: صيغة ندائه (nick) + أنسب سؤال يطلّع منه ملاحظة حقيقية من بياناته.
# صيغة السؤال مبنية على كلمات كل وكيل الفعلية (orchestrator/agents/*.py) —
# فالسؤال بيوصله فعلًا، وكمان بيوصله إننا بنسأله عن ملاحظة/نوت/تذكير.
#
# `ask` = الطلب الأساسي (مُجرَّب على كل وكيل: بيرجّع بيانات حقيقية لا بطاقة هوية).
# `check` = السؤال التالي (فحص/ملاحظة) — بيتضاف له الـ`ask` في نص واحد عشان
#           الرَاوتر يوجّه للسؤال الصح ويوصله إننا عايزين ملاحظة.
_ROSTER: List[Dict[str, str]] = [
    {"agent_id": "manufacturing", "nick": "بيبو",  "display": "بيبو — التصنيع والليزر",
     "ask": "الخامات", "check": "في خامة ناقصة أو سعر محتاج مراجعة؟"},
    {"agent_id": "cfo",           "nick": "فارس",  "display": "فارس — المدير المالي",
     "ask": "ملخص الخزينة", "check": "في دين متأخر أو مصروف غريب؟"},
    {"agent_id": "crm",           "nick": "سلمى",  "display": "سلمى — علاقات العملاء",
     "ask": "تنبيهات المتأخر", "check": "في عميل محتاج متابعة؟"},
    {"agent_id": "marketing",     "nick": "كوكو",  "display": "كوكو — التسويق والعروض",
     "ask": "الراكد", "check": "في عرض محتاج تجهيز؟"},
    {"agent_id": "data_healer",   "nick": "حكيم",  "display": "حكيم — طبيب البيانات",
     "ask": "الروتين", "check": "في مشكلة بيانات محتاجة إصلاح؟"},
    {"agent_id": "system_worker", "nick": "مصطفى", "display": "مصطفى — التحكم بالكمبيوتر",
     "ask": "امكانيات", "check": "في أداة ناقصة أو مورد واقف؟"},
    {"agent_id": "coder",         "nick": "فيجن",  "display": "فيجن — الكودر والتطوير",
     "ask": "رصد الأخطاء", "check": "في كود محتاج إصلاح؟"},
    {"agent_id": "meta",          "nick": "راصد",  "display": "راصد — المراقب الذاتي",
     "ask": "تقرير الأداء", "check": "في وكيل ضعيف أو مكرر؟"},
]

# علامات «فيها ملاحظة تستاهل النقل» — بتتفحص سطر سطر، وبنستثني أسطر «✅ تمام».
_BAD_MARKERS = ("❌", "⚠️", "غير متاح", "غير متثبتة", "مخالف", "مقلوب", "تعذر", "فشل",
                "ما افترضشت", "ناقص", "واقف", "متأخر", "مكرر", "سالب", "معلق")

# نصوص إيجابية = «تمام» مش ملاحظة (بنتخطاها حتى لو فيها ⚠️ أو رقم).
_OK_MARKERS = ("لا طلبات متأخرة", "كل الطلبات", "مفيش", "لا يوجد", "مفيش تقارير",
               "مفيش مخزون", "مفيش حاجة", "✅ لا", "صفرية: 0")

_ORCH: Any = None
_ORCH_ERR: str = ""
_ORCH_TRIED: bool = False


def roster() -> List[Dict[str, str]]:
    """التشكيلة المعتمدة — للعرض في البرومبت والوثائق."""
    return [dict(m) for m in _ROSTER]


# ------------------------------------------------------------------ المُنسّق
def _orchestra():
    """يستورد المُنسّق المحلي مرة واحدة. أي فشل = رسالة صادقة، بلا اختراع."""
    global _ORCH, _ORCH_ERR, _ORCH_TRIED
    if _ORCH_TRIED:
        return _ORCH
    _ORCH_TRIED = True
    root = str(config.MARWA_ROOT)
    try:
        if root not in sys.path:
            sys.path.insert(0, root)
        from orchestrator.core import Orquesta  # noqa: WPS433 (import مقصود وقت التشغيل)
        _ORCH = Orquesta()
    except Exception as exc:
        _ORCH = None
        _ORCH_ERR = f"{type(exc).__name__}: {exc}"
        config.log(f"مناداة الفريق: تعذر تحميل المُنسّق — {_ORCH_ERR}")
    return _ORCH


def available() -> Tuple[bool, str]:
    """هل المناداة متاحة؟ (False + السبب الصادق لو لأ)."""
    ok = _orchestra() is not None
    return ok, ("" if ok else (_ORCH_ERR or "المُنسّق غير متاح"))


def question_for(m: Dict[str, str]) -> str:
    """نص السؤال الموحَّد لكل وكيل.

    النداء الأول (`ask`) هو اللي بيحدّد التوجيه عند الرَاوتر، وبعده بيتضاف
    `check` — فالسؤال بيوصله فعلًا **وكمان** بيوصله إننا بنسأله عن ملاحظة.
    """
    q = f"يا {m['nick']} {m['ask']}"
    if m.get("check"):
        q += f" — {m['check']} وكمان عندك أي ملاحظة أو نوت أو تذكير؟"
    else:
        q += " — عندك أي ملاحظة أو نوت أو تذكير؟"
    return q


# ------------------------------------------------------------------ التصنيف
def _notable(reply: str) -> bool:
    """هل الرد فيه ملاحظة تستاهل النقل؟

    بنفحص بعد أول سطرين (التوقيع + عنوان التقرير مش ملاحظات)، وبنستثني
    سطور «تمّام» الصريحة عشان ما نغرقش المالك بإيجابيات.
    """
    lines = [l.strip() for l in (reply or "").splitlines() if l.strip()]
    body = lines[2:] if len(lines) > 2 else lines
    for line in body:
        if "✅" in line:
            continue
        if any(ok in line for ok in _OK_MARKERS):
            continue
        if any(mk in line for mk in _BAD_MARKERS):
            return True
    return False


def ask(agent_id_or_nick: str, question: Optional[str] = None) -> Dict[str, Any]:
    """يسأل وكيل واحد. بيرجع dict صادق (ok/error) — ما يخترعش رد."""
    target = None
    key = (agent_id_or_nick or "").strip().lower()
    for m in _ROSTER:
        if key in (m["agent_id"].lower(), m["nick"].lower(), m["display"].lower()):
            target = m
            break
    if target is None:
        return {"ok": False, "error": f"وكيل غير معروف: {agent_id_or_nick}", "reply": ""}
    orch = _orchestra()
    q = question or question_for(target)
    item: Dict[str, Any] = {"agent_id": target["agent_id"], "nick": target["nick"],
                            "display": target["display"], "question": q,
                            "ok": False, "reply": "", "error": "", "severity": "info"}
    if orch is None:
        item["error"] = _ORCH_ERR or "المُنسّق غير متاح"
        item["severity"] = "warn"
        return item
    try:
        out = orch.handle(q)
        rep = (out.get("reply") or "").strip()
        if not rep:
            item["error"] = "رد فاضي"
            item["severity"] = "warn"
            return item
        item["ok"] = True
        item["reply"] = rep
        item["routed_to"] = out.get("agent_id")
        if _notable(rep):
            item["severity"] = "warn"
    except Exception as exc:
        item["error"] = f"{type(exc).__name__}: {exc}"
        item["severity"] = "warn"
    return item


# ------------------------------------------------------------------ المناداة
def rollcall(store: bool = True, agents: Optional[List[str]] = None) -> Dict[str, Any]:
    """ينادي كل الفريق ويسأله. بيرجع الملخص + الصفوف. صادق في الفشل."""
    picked = _ROSTER
    if agents:
        wanted = {a.strip().lower() for a in agents if a and a.strip()}
        picked = [m for m in _ROSTER
                  if m["agent_id"].lower() in wanted or m["nick"].lower() in wanted]
    rows: List[Dict[str, Any]] = [ask(m["agent_id"]) for m in picked]
    answers = [r for r in rows if r["ok"]]
    noted = [r for r in answers if r["severity"] == "warn"]
    failed = [r for r in rows if not r["ok"]]
    summary = {"asked": len(rows), "answered": len(answers), "noted": len(noted),
               "failed": len(failed), "at": datetime.now().isoformat(timespec="seconds"),
               "rows": rows}
    if store:
        _store(rows, summary)
    return summary


def _store(rows: List[Dict[str, Any]], summary: Dict[str, Any]) -> None:
    """يخزّن الردود كتقارير وكلاء: المهمة تفضل ظاهرة، والعادية تتعلّم كمقروءة."""
    for r in rows:
        if not r["ok"]:
            continue
        try:
            saved = retail.ingest_agent_report(
                agent=r["nick"], title=(r["reply"].splitlines() or [""])[0][:200] or r["nick"],
                body=r["reply"][:3000], scope="proactive",
                severity=r["severity"], source="rollcall",
                payload={"question": r["question"], "routed_to": r.get("routed_to")})
            # العادي يتعلّم كمقروء فورًا → ما يغرقش الملخص الصباحي
            if r["severity"] == "info":
                retail.ack_report(saved["id"])
        except Exception as exc:
            config.log(f"مناداة الفريق: تعذر تخزين رد {r['nick']} — {type(exc).__name__}: {exc}")
    try:
        db.set_setting("squad_last_rollcall", {k: v for k, v in summary.items() if k != "rows"})
    except Exception as exc:
        config.log(f"مناداة الفريق: تعذر حفظ ملخص المناداة — {type(exc).__name__}: {exc}")


# ------------------------------------------------------------------ التقرير
def _digest(reply: str, keep: int = 3, width: int = 110) -> str:
    """يستخرج السطور الجوهرية من رد وكيل: تخطّي التوقيع/العنوان، ورجّح
    السطور اللي فيها أرقام أو مؤشرات خطر — ده اللي يهم المالك فعلًا."""
    lines = [l.strip() for l in (reply or "").splitlines() if l.strip()]
    body = lines[2:] if len(lines) > 2 else lines          # التوقيع + العنوان
    scored = []
    for i, line in enumerate(body):
        if "✅" in line or any(ok in line for ok in _OK_MARKERS):
            continue
        score = 0
        if any(mk in line for mk in _BAD_MARKERS):
            score += 3
        if any(ch.isdigit() for ch in line):
            score += 2
        if "💡" in line:
            score -= 1
        if len(line) > 12:
            score += 1
        scored.append((-score, i, line))
    if not scored:
        return "✅ تمام — مفيش ملاحظات."
    scored.sort()
    chosen = sorted(scored[:keep], key=lambda t: t[1])     # نرجّع الترتيب الأصلي
    out = []
    for _s, _i, line in chosen:
        out.append("   " + (line[:width].rstrip() + "…" if len(line) > width else line))
    return "\n".join(out)


def report_text(summary: Dict[str, Any]) -> str:
    """ملخص عربي جاهز لتليجرام/الواجهة — ملاحظات أولًا، ثم الباقي مختصر."""
    rows = summary.get("rows") or []
    noted = [r for r in rows if r["ok"] and r["severity"] == "warn"]
    calm = [r for r in rows if r["ok"] and r["severity"] != "warn"]
    silent = [r for r in rows if not r["ok"]]

    head = (f"🗣️ مناداة الفريق — {datetime.now():%Y-%m-%d %H:%M}\n"
            f"سألت {summary.get('asked', 0)} وكيل | ردّوا {summary.get('answered', 0)}"
            f" | ملاحظات: {summary.get('noted', 0)}")
    if silent:
        head += f" | بلا رد: {len(silent)}"
    parts = [head]

    if noted:
        parts.append("\n🔸 عندهم ملاحظات/نوت/تذكير:")
        for r in noted:
            parts.append(f"\n• {r['display']}\n{_digest(r['reply'])}")
    else:
        parts.append("\n✅ مفيش وكيل عنده ملاحظة محتاجة تدخّل دلوقتي.")

    if silent:
        parts.append("\n⚠️ ما ردّوش:")
        parts += [f"   • {r['nick']} — {r.get('error') or 'سبب غير معروف'}" for r in silent]
    if calm:
        parts.append("\n▪️ البقية تمام: " + "، ".join(r["nick"] for r in calm))
    parts.append("\nللتفاصيل: «حالة» | لتأكيد تقرير: /api/agents/ack/<رقم>")
    return "\n".join(parts)


def rollcall_text(store: bool = True, agents: Optional[List[str]] = None) -> str:
    """ينادي الفريق وبيرجع النص جاهز — للاستخدام من البوت مباشرة."""
    return report_text(rollcall(store=store, agents=agents))


# ------------------------------------------------------------------ الحجز اليومي
def _claim_daily(job: str) -> bool:
    """حجز ذري لدورة اليوم (نفس نمط المحرك الاستباقي) — الفائز فقط يرسل."""
    today = datetime.now().astimezone().strftime("%Y-%m-%d")
    try:
        row = db.q("""INSERT INTO cron_runs(job, run_date, node_id)
                      VALUES (%s, %s, %s)
                      ON CONFLICT DO NOTHING RETURNING id""",
                   (job, today, config.NODE_ID), one=True)
    except Exception as exc:
        config.log(f"مناداة الفريق: تعذر الحجز اليومي — {type(exc).__name__}: {exc}")
        return False
    return bool(row)


def rollcall_if_due(sender: Optional[Callable[[int, str], bool]] = None) -> int:
    """الدورة اليومية: تسأل الفريق مرة واحدة وتبعتها للمالك. ترجع عدد المُرسل."""
    hh, _mm = (getattr(config, "SQUAD_ROLLCALL_AT", "09:00") or "09:00").split(":")[:2] + ["00"]
    try:
        hour = int(hh)
    except ValueError:
        hour = 9
    now = datetime.now()
    if not (hour <= now.hour < hour + 1):
        return 0
    if not getattr(config, "SQUAD_ROLLCALL_ENABLED", True):
        return 0
    if not _claim_daily("squad_rollcall"):
        return 0
    summary = rollcall(store=True)
    from nb import proactive  # استيراد مؤجّل — يمنع أي دورة استيراد
    proactive.enqueue(config.OWNER_TELEGRAM_ID, report_text(summary), "squad",
                      dedupe_key=f"squad-{now:%Y-%m-%d}")
    return 1


def last_rollcall() -> Optional[Dict[str, Any]]:
    """آخر مناداة محفوظة — للعرض في الملخص الصباحي/الواجهة."""
    try:
        return db.get_setting("squad_last_rollcall")
    except Exception:
        return None


def briefing_line() -> str:
    """سطر مختصر للملخص الصباحي — من غير ما يغرق الصفحة."""
    last = last_rollcall()
    if not last:
        return "🗣️ الفريق: لسه ما ناديتهم — ابعت «الفريق» عشان أسألهم."
    at = (last.get("at") or "")[:16].replace("T", " ")
    return (f"🗣️ الفريق (آخر مناداة {at}): ردّوا {last.get('answered', 0)}/"
            f"{last.get('asked', 0)} | ملاحظات: {last.get('noted', 0)}"
            + (f" | بلا رد: {last['failed']}" if last.get("failed") else ""))
