# -*- coding: utf-8 -*-
"""موجّه الذكاء — R5 (AI Router).

الطبقة الأولى: قواعد عربية محلية منقولة من notebook/brain.py (v1) — تعمل بلا
إنترنت وبلا مفاتيح. الطبقة الثانية: تحسين سحابي عبر providers.chat() بـJSON
محكم — تُستخدم عند توفر مزود افتراضي وتفشل بصمت إلى القواعد.

الأنواع: task / idea / note / reminder / program_idea / home_item / workshop_need
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from nb import config, db, providers

# ------------------------------------------------------------------ تطبيع
_TASHKEEL = re.compile(r"[\u0617-\u061A\u064B-\u0652\u0640]")
_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


def normalize(text: str) -> str:
    t = (text or "").strip()
    t = t.translate(_AR_DIGITS)
    t = _TASHKEEL.sub("", t)
    t = (t.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ٱ", "ا")
          .replace("ى", "ي").replace("ة", "ه").replace("ؤ", "و").replace("ئ", "ي"))
    return re.sub(r"\s+", " ", t).lower()


# ------------------------------------------------------------------ مفردات
KINDS = ("note", "task", "idea", "reminder", "program_idea", "home_item", "workshop_need")
KIND_LABELS = {
    "note": "📝 نوت", "task": "✅ مهمة", "reminder": "⏰ تذكير", "idea": "💡 فكرة",
    "program_idea": "🚀 فكرة برنامج", "home_item": "🏠 قائمة بيت", "workshop_need": "🔧 احتياج ورشة",
}
PRIORITY_LABELS = {"low": "منخفضة", "normal": "عادية", "high": "مهمة", "urgent": "عاجلة"}

PROGRAM_IDEA = ["فكره برنامج", "فكرة برنامج", "فكره تطبيق", "فكرة تطبيق", "برنامج جديد",
                "تطبيق جديد", "مشروع برنامج", "مشروع تطبيق", "سيستم جديد", "نظام جديد"]
REMINDER_WORDS = ["فكرني", "ذكرني", "افتكرني", "تذكير", "متنساش", "متنسانيش",
                  "كل يوم", "يوميا", "كل اسبوع", "اسبوعيا", "كل شهر", "شهريا"]
TASK_VERBS = ["اعمل", "كلم", "اتصل", "رن علي", "جهز", "سلم", "اشتري", "ادفع", "راجع",
              "ابعت", "روح", "خد", "هات", "صلح", "ركب", "احجز", "اسال", "شوف", "اتاكد",
              "تابع", "اكتب", "سجل", "احسب", "اعرض", "اطبع", "احفر", "اقطع"]
TASK_HINTS = ["لازم", "مطلوب", "ضروري", "مهمه", "تاسك", "todo", "تسليم", "موعد", "التزام"]
IDEA_WORDS = ["فكره", "فكرة", "اقتراح", "لو نعمل", "ممكن نعمل", "نفكر في", "تخيل"]
HOME_WORDS = ["سوق", "بقاله", "بقاله البيت", "خراج البيت", "خبز", "لبن", "حفاضات", "غسيل",
              "مطبخ", "عيش", "سكر", "شاي", "زبادي", "فاكهه", "خضار", "احتياجات البيت"]
WORKSHOP_WORDS = ["ليزر", "cnc", "حفر", "جرافير", "خشب", "mdf", "اكليريك", "اكريليك",
                  "استيكر", "فينيل", "ماكينه", "ورشه", "عميل الورشه", "خامات"]

PRIORITY_URGENT = ["عاجل", "حالا", "فورا", "ضروري جدا", "مهم جدا", "طوارئ", "asap", "urgent"]
PRIORITY_HIGH = ["مهم", "ضروري", "متاخرش"]
PRIORITY_LOW = ["لو فاضي", "مش مستعجل", "عادي", "وقت ما تقدر", "لاحقا"]

CATEGORY_KEYWORDS = [
    ("ليزر", ["ليزر", "laser", "قص", "حفر", "جرافير", "rdworks", "قدره"]),
    ("طباعة", ["طباعه", "طابعه", "طبع", "ورق", "a4", "a3", "كروت", "بنر", "استيكر", "فينيل"]),
    ("خامات", ["خام", "خامات", "خشب", "mdf", "اكليريك", "اكريليك", "بلاستيك", "لوح", "فوم"]),
    ("تصميم", ["تصميم", "ديزاين", "فوتوشوب", "كورل", "اوتوكاد", "psd"]),
    ("عملاء", ["عميل", "زبون", "طلب", "جهااد", "اهداء", "توصيل"]),
    ("حسابات", ["حساب", "فلوس", "دفع", "فاتوره", "دين", "رصيد", "مصروف", "ايراد", "خزنه"]),
    ("مشتريات", ["اشتري", "شراء", "مورد", "بضاعه", "توريد"]),
    ("صيانة", ["صيانه", "عطل", "باظ", "مكسور", "تصليح", "قطعه غيار", "ماكينه"]),
    ("برامج", ["برنامج", "كود", "تطبيق", "سكربت", "داتا", "database", "api", "سيستم", "نظام"]),
    ("شخصي", ["بيت", "شخصي", "عيال", "الاهل", "صحه", "دكتور", "دوا", "مناسبه", "سفر"]),
]

WEEKDAYS = {"السبت": 5, "الاحد": 6, "الاثنين": 0, "الاتنين": 0, "الثلاثاء": 1,
            "التلات": 1, "الاربعاء": 2, "الاربع": 2, "الخميس": 3, "الجمعه": 4}
PERIOD_HOURS = {"الصبح": 9, "الفجر": 5, "الظهر": 13, "بعد الضهر": 14, "العصر": 16,
                "المغرب": 18, "بالليل": 21, "الليل": 21, "المسا": 19}
TITLE_FILLERS = ["فكرني", "ذكرني", "افتكرني", "لازم", "مطلوب", "من فضلك", "لو سمحت",
                 "يا مروه", "يا فيجن", "مروه", "فيجن"]


def _has(text: str, phrases: List[str]) -> int:
    return sum(1 for p in phrases if p in text)


def _first_sentence(text: str, limit: int = 120) -> str:
    raw = (text or "").strip()
    for sep in ("\n", ".", "،", "؛"):
        if sep in raw:
            raw = raw.split(sep)[0]
            break
    raw = raw.strip()
    for filler in TITLE_FILLERS:
        raw = re.sub(rf"^\s*{re.escape(filler)}\s*", "", raw, flags=re.IGNORECASE)
    return raw[:limit].strip() or (text or "").strip()[:limit]


# ------------------------------------------------------------------ التواريخ (منقولة من v1)
def _parse_time(text: str) -> Optional[Tuple[int, int]]:
    hour, minute, period = None, 0, None
    m = re.search(r"(?:الساعه|عند|في)\s*(\d{1,2})(?::(\d{2}))?\s*"
                 r"(ص|م|صباحا|صباحًا|مساء|مساءً|بالليل|العصر|الظهر|الصبح|الفجر)?", text)
    if m:
        hour, minute, period = int(m.group(1)), int(m.group(2) or 0), m.group(3)
    else:
        m = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(ص|م|صباحا|صباحًا|مساء|مساءً|بالليل|العصر|الظهر|الصبح)\b", text)
        if m:
            hour, minute, period = int(m.group(1)), int(m.group(2) or 0), m.group(3)
    if hour is None:
        for word, h in PERIOD_HOURS.items():
            if word in text:
                return h, 0
        return None
    if not (0 <= hour <= 23):
        return None
    if period:
        p = period.strip()
        if p in ("ص", "صباحا", "صباحًا", "الصبح", "الفجر"):
            if hour == 12:
                hour = 0
        elif p in ("م", "مساء", "مساءً", "بالليل", "العصر", "الظهر"):
            if hour < 12:
                hour += 12
    elif 1 <= hour <= 7:
        hour += 12  # «الساعة 5» = 5 العصر — عُرف المواعيد عندنا
    return hour, max(0, min(59, minute))


def _parse_date(text: str, base: datetime) -> Optional[datetime]:
    m = re.search(r"\b(20\d{2})[-/](\d{1,2})[-/](\d{1,2})\b", text)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    m = re.search(r"\b(\d{1,2})[-/](\d{1,2})(?:[-/](20\d{2}))?\b", text)
    if m:
        day, month = int(m.group(1)), int(m.group(2))
        year = int(m.group(3)) if m.group(3) else base.year
        if 1 <= day <= 31 and 1 <= month <= 12:
            try:
                candidate = datetime(year, month, day)
                if candidate.date() < base.date() and not m.group(3):
                    candidate = candidate.replace(year=year + 1)
                return candidate
            except ValueError:
                return None
    if "بعد بكره" in text or "بعد بكرة" in text:
        return base + timedelta(days=2)
    if any(w in text for w in ("النهارده", "النهاردة", "اليوم", "today")):
        return base
    if any(w in text for w in ("بكره", "بكرة", "بكرا", "غدا", "tomorrow")):
        return base + timedelta(days=1)
    m = re.search(r"بعد\s+(\d{1,3})\s*(يوم|ايام|ساعه|ساعات|اسبوع|اسابيع|شهر|شهور)", text)
    if m:
        amount, unit = int(m.group(1)), m.group(2)
        if "ساع" in unit:
            return base + timedelta(hours=amount)
        if "اسبوع" in unit:
            return base + timedelta(weeks=amount)
        if "شهر" in unit:
            return base + timedelta(days=30 * amount)
        return base + timedelta(days=amount)
    for name, idx in WEEKDAYS.items():
        if name in text:
            days_ahead = (idx - base.weekday()) % 7 or 7
            return base + timedelta(days=days_ahead)
    return None


def parse_when(text: str, base: Optional[datetime] = None) -> Dict[str, Any]:
    """ميعاد/تذكير من نص عربي — يرجع datetimes متحيّزة أو None."""
    base = base or datetime.now().astimezone()
    norm = normalize(text)
    result: Dict[str, Any] = {"due_at": None, "remind_at": None,
                              "remind_every": "none", "when_text": None}
    every = "none"
    if any(w in norm for w in ("كل يوم", "يوميا", "daily")):
        every = "daily"
    elif any(w in norm for w in ("كل اسبوع", "اسبوعيا", "weekly")):
        every = "weekly"
    elif any(w in norm for w in ("كل شهر", "شهريا", "monthly")):
        every = "monthly"
    result["remind_every"] = every

    date_part = _parse_date(norm, base.replace(tzinfo=None))
    time_part = _parse_time(norm)
    if date_part is None and time_part is None:
        if every != "none":
            due = base.replace(second=0, microsecond=0)
            result["due_at"] = result["remind_at"] = due
            result["when_text"] = "متكرر"
        return result

    due = date_part or base.replace(tzinfo=None)
    if time_part:
        due = due.replace(hour=time_part[0], minute=time_part[1], second=0, microsecond=0)
    else:
        due = due.replace(hour=9, minute=0, second=0, microsecond=0)
    if date_part is None and time_part is not None and due < base.replace(tzinfo=None):
        due = due + timedelta(days=1)

    due = due.astimezone()  # متحيّز بالتوقيت المحلي
    remind = due - timedelta(hours=1) if not (due.hour == 9 and time_part is None) else due
    if remind < base:
        remind = base + timedelta(minutes=5)
    result["due_at"] = due
    result["remind_at"] = remind
    result["when_text"] = due.strftime("%Y-%m-%d %H:%M")
    return result


# ------------------------------------------------------------------ تحليل محلي
def classify_kind(text: str) -> Tuple[str, int]:
    n = normalize(text)
    scores = {
        "program_idea": _has(n, PROGRAM_IDEA) * 3 + (2 if "فكره" in n or "فكرة" in n else 0),
        "reminder": _has(n, REMINDER_WORDS),
        "task": _has(n, TASK_VERBS) * 2 + _has(n, TASK_HINTS),
        "idea": _has(n, IDEA_WORDS),
        "home_item": _has(n, HOME_WORDS),
        "workshop_need": _has(n, WORKSHOP_WORDS),
    }
    if _has(n, PROGRAM_IDEA):
        scores["program_idea"] += 3
    if _has(n, TASK_HINTS) and _has(n, TASK_VERBS):
        scores["task"] += 2
    best_kind, best_score = "note", 0
    for kind, score in scores.items():
        if score > best_score:
            best_kind, best_score = kind, score
    return best_kind, best_score


def classify_category(text: str) -> Tuple[str, bool]:
    raw = text or ""
    explicit = re.search(r"(?:تصنيف|قسم|فولدر)\s*[:：]\s*([\w\u0600-\u06FF ]{2,25})", raw)
    if explicit:
        return explicit.group(1).strip(), True
    n = normalize(raw)
    best, best_hits = "", 0
    for name, words in CATEGORY_KEYWORDS:
        hits = _has(n, [normalize(w) for w in words])
        if hits > best_hits:
            best, best_hits = name, hits
    return (best, True) if best_hits else ("غير مصنف", False)


def classify_priority(text: str) -> str:
    n = normalize(text)
    if _has(n, [normalize(w) for w in PRIORITY_URGENT]):
        return "urgent"
    if _has(n, [normalize(w) for w in PRIORITY_HIGH]):
        return "high"
    if _has(n, [normalize(w) for w in PRIORITY_LOW]):
        return "low"
    return "normal"


def extract_tags(text: str) -> List[str]:
    return [t.strip("#") for t in re.findall(r"#([\w\u0600-\u06FF_]+)", text or "")][:8]


def analyze_local(text: str, source: str = "ui") -> Dict[str, Any]:
    raw = (text or "").strip()
    if not raw:
        return {"ok": False, "error": "النص فاضي"}
    kind, kind_score = classify_kind(raw)
    category, cat_confident = classify_category(raw)
    priority = classify_priority(raw)
    when = parse_when(raw)
    tags = extract_tags(raw)
    if kind == "program_idea":
        category, cat_confident = "أفكار برامج", True

    question, needs = None, False
    if kind == "note" and kind_score == 0 and len(raw) > 25:
        question = "ده نوت للذكرى ولا مهمة ليها ميعاد؟"
        needs = True
    elif kind == "task" and not when.get("due_at"):
        question = "المهمة دي ليها ميعاد؟ اكتب مثلًا: «بكرة الساعة 5»."
        needs = True
    elif not cat_confident:
        question = "أحطها في أنهي تصنيف؟ (ليزر / حسابات / عملاء / شخصي…)"
        needs = True

    confidence = min(1.0, 0.45 + 0.15 * kind_score) if kind_score else 0.4
    return {
        "ok": True, "kind": kind, "title": _first_sentence(raw), "body": raw,
        "category": category, "priority": priority,
        "due_at": when.get("due_at"), "remind_at": when.get("remind_at"),
        "remind_every": when.get("remind_every") or "none",
        "tags": tags, "confidence": round(confidence, 2),
        "needs_clarification": needs, "question": question,
        "source": source, "meta": {}, "routed_by": "rules",
    }


# ------------------------------------------------------------------ تحسين سحابي
_CLOUD_PROMPT = """أنت مصنّف ملاحظات شخصية عربية. صنّف النص التالي وأعد JSON خامًا فقط (بلا شرح) بالحقول:
kind: واحد من ["task","idea","note","reminder","program_idea","home_item","workshop_need"]
category: تصنيف عربي قصير (مثل: ليزر، طباعة، حسابات، عملاء، شخصي) أو null
priority: واحد من ["low","normal","high","urgent"]
tags: قائمة كلمات مفتاحية قصيرة (أو [])
due_hint: لو في موعد بالنص أعد صياغته واضحة (مثل: "غدًا 17:00") وإلا null

النص:
"""


def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    text = re.sub(r"```(json)?", "", text or "").strip()
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def cloud_refine(analysis: Dict[str, Any], text: str) -> Dict[str, Any]:
    """تحسين التصنيف بمزود سحابي — الفشل يعود للقواعد بصمت."""
    try:
        raw_answer, meta = providers.chat(
            [{"role": "user", "content": _CLOUD_PROMPT + text}],
            max_tokens=200, temperature=0.0, json_mode=True)
    except Exception as exc:
        config.log(f"ai_router: السحابة غير متاحة — قواعد محلية فقط ({type(exc).__name__})")
        return analysis
    data = _extract_json(raw_answer)
    if not isinstance(data, dict):
        return analysis
    if data.get("kind") in KINDS:
        analysis["kind"] = data["kind"]
    if isinstance(data.get("category"), str) and data["category"].strip():
        analysis["category"] = data["category"].strip()
    if data.get("priority") in ("low", "normal", "high", "urgent"):
        analysis["priority"] = data["priority"]
    if isinstance(data.get("tags"), list):
        analysis["tags"] = [str(t)[:30] for t in data["tags"][:8]]
    if data.get("due_hint"):
        when = parse_when(f"موعد {data['due_hint']}")
        if when.get("due_at"):
            analysis["due_at"] = when["due_at"]
            analysis["remind_at"] = when["remind_at"]
            if when.get("remind_every"):
                analysis["remind_every"] = when["remind_every"]
    analysis["routed_by"] = f"llm:{meta.get('provider')}:{meta.get('model')}"
    analysis["confidence"] = 0.9
    return analysis


def route(text: str, source: str = "telegram", use_cloud: bool = True) -> Dict[str, Any]:
    """المدخل الموحد: نص حر ← تحليل كامل جاهز للعرض والحفظ."""
    analysis = analyze_local(text, source=source)
    if not analysis.get("ok"):
        return analysis
    if use_cloud:
        analysis = cloud_refine(analysis, text)
    return analysis


def confirm_message(note: Dict[str, Any], note_id: int) -> str:
    """تأكيد عربي مختصر بعد الحفظ — نفس روح v1."""
    lines = [f"{KIND_LABELS.get(note.get('kind'), '📝 نوت')} — سجّلت (#{note_id}): {note.get('title')}"]
    lines.append(f"• التصنيف: {note.get('category') or 'غير مصنف'} | "
                 f"الأولوية: {PRIORITY_LABELS.get(note.get('priority'), 'عادية')}")
    if note.get("due_at"):
        due = note["due_at"]
        if isinstance(due, datetime):
            due = due.astimezone().strftime("%Y-%m-%d %H:%M")
        lines.append(f"• الميعاد: {due}")
    if note.get("remind_every") and note["remind_every"] != "none":
        lines.append(f"• التكرار: {note['remind_every']}")
    lines.append(f"• التصنيف بواسطة: {note.get('routed_by') or 'rules'}")
    if note.get("question"):
        lines.append(f"❓ {note['question']}")
    return "\n".join(lines)
