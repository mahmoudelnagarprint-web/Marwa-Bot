# -*- coding: utf-8 -*-
"""النوتبوك الذكية — العقل: يفهم النص العربي الحر ويصنّفه.

بيحدد: نوع المدخل (نوت / مهمة / تذكير / فكرة / فكرة برنامج)، التصنيف (ويفتح تصنيف
جديد لو لزم)، الأولوية، الميعاد والتذكير، ولو مش فاهم بيسأل سؤال توضيحي واحد.

كل ده بالقواعد (بلا إنترنت وبلا مفتاح) — ولا يخترع معلومة غير موجودة في النص.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

# ------------------------------------------------------------------ تطبيع
_TASHKEEL = re.compile(r"[\u0617-\u061A\u064B-\u0652\u0640]")
_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


def normalize(text: str) -> str:
    t = (text or "").strip()
    t = t.translate(_AR_DIGITS)
    t = _TASHKEEL.sub("", t)
    t = (t.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ٱ", "ا")
          .replace("ى", "ي").replace("ة", "ه").replace("ؤ", "و").replace("ئ", "ي"))
    t = re.sub(r"\s+", " ", t)
    return t.lower()


# ------------------------------------------------------------------ مفردات
PROGRAM_IDEA = [
    "فكره برنامج", "فكرة برنامج", "فكره تطبيق", "فكرة تطبيق", "افكار برامج", "افكار برنامج",
    "برنامج جديد", "تطبيق جديد", "ابليكيشن جديد", "مشروع برنامج", "مشروع تطبيق",
    "عايز اعمل برنامج", "عاوز اعمل برنامج", "نفسي اعمل برنامج", "انوي اعمل برنامج",
    "فكره ابليكيشن", "برنامج يشتغل", "سيستم جديد", "نظام جديد",
]
REMINDER_WORDS = [
    "فكرني", "ذكرني", "افتكرني", "تذكير", "متنساش", "متنسانيش", "ذكرى",
    "كل يوم", "يوميا", "كل اسبوع", "اسبوعيا", "كل شهر", "شهريا", "متابعه",
]
TASK_VERBS = [
    "اعمل", "اعملي", "كلم", "اتصل", "رن علي", "رن على", "جهز", "جهزي", "سلم", "سلّم",
    "اشتري", "اشتريلي", "ادفع", "راجع", "ابعت", "ابعتي", "روح", "خد", "هات", "صلح",
    "ركب", "احجز", "اسال", "اسأل", "شوف", "اتاكد", "تابع", "اتابع", "اكتب", "وقّع",
    "سجل", "املا", "احسب", "ورّي", "اعرض", "طبّع", "اقطع", "اطبع", "احفر",
]
TASK_HINTS = ["لازم", "مطلوب", "ضروري اعمل", "مهمه", "تاسك", "task", "todo", "تسليم", "موعد", "وعد", "التزام"]
IDEA_WORDS = ["فكره", "فكرة", "اقتراح", "لو نعمل", "ممكن نعمل", "نفكر في", "تخيل"]

PRIORITY_URGENT = ["عاجل", "حالا", "حالًا", "فورا", "فورًا", "ضروري جدا", "مهم جدا", "طوارئ", "asap", "urgent"]
PRIORITY_HIGH = ["مهم", "ضروري", "مش ناقص غير", "بالذمه", "متاخرش"]
PRIORITY_LOW = ["لو فاضي", "لو فاضيين", "مش مستعجل", "عادي", "وقت ما تقدر", "لاحقا"]

# تصنيف ← كلمات مفتاحية
CATEGORY_KEYWORDS: List[Tuple[str, List[str]]] = [
    ("ليزر", ["ليزر", "laser", "قص", "حفر", "جرافير", "rdworks", "قدره", "خرومه"]),
    ("طباعة", ["طباعه", "طابعه", "طبع", "ورق", "a4", "a3", "كروت", "بنر", "استيكر", "فينيل"]),
    ("خامات", ["خام", "خامات", "خشب", "mdf", "اكليريك", "اكريليك", "بلاستيك", "لوح", "سبلميشن", "فوم"]),
    ("تصميم", ["تصميم", "ديزاين", "فوتوشوب", "photoshop", "كورل", "corel", "اوتوكاد", "psd", "اليستريتور"]),
    ("عملاء", ["عميل", "عميله", "زبون", "طلب", "طلبات", "جهااد", "اهداء", "عمولة", "توصيل"]),
    ("حسابات", ["حساب", "حسابات", "فلوس", "دفع", "دفعه", "فاتوره", "دين", "رصيد", "مصروف", "ايراد", "خزنه", "دخل"]),
    ("مشتريات", ["اشتري", "شراء", "مورد", "مشتريات", "فاتوره مشتريات", "بضاعه", "توريد"]),
    ("صيانة", ["صيانه", "عطل", "باظ", "مكسور", "بيصلح", "تصليح", "قطعه غيار", "ماكينه", "بيوقف"]),
    ("برامج", ["برنامج", "كود", "تطبيق", "ابليكيشن", "سكربت", "داتا", "داتابيز", "database", "api", "موقع", "سيستم", "نظام"]),
    ("شخصي", ["بيت", "شخصي", "عيال", "الاهل", "صحه", "دكتور", "دوا", "مناسبه", "عيد", "سفر", "فلوس البيت"]),
]

WEEKDAYS = {
    "السبت": 5, "الاحد": 6, "الاثنين": 0, "الاتنين": 0, "الثلاثاء": 1, "التلات": 1,
    "الاربعاء": 2, "الاربع": 2, "الخميس": 3, "الجمعه": 4,
}
PERIOD_HOURS = {"الصبح": 9, "الفجر": 5, "الظهر": 13, "بعد الضهر": 14, "العصر": 16,
                "المغرب": 18, "بالليل": 21, "الليل": 21, "المسا": 19, "المساء": 19}

TITLE_FILLERS = ["فكرني", "ذكرني", "افتكرني", "لازم", "مطلوب", "من فضلك", "لو سمحت", "يا مروه", "يا فيجن", "مروه", "فيجن"]


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


# ------------------------------------------------------------------ التواريخ
def _parse_time(text: str) -> Optional[Tuple[int, int]]:
    """يُرجع (ساعة، دقيقة) من نص عربي — وNone لو مفيش وقت.

    ملاحظات دقة: علامة ص/م تُقرأ فقط لو ملاصقة للرقم (منعًا لخطأ حرف «م» داخل
    كلمة تانية مثل «العميل»). ولو مفيش علامة: الساعات 1-7 تُفهم مساءً (5 = 17:00)
    لأن دي عُرف المواعيد عندنا، وباقي الساعات صباحًا.
    """
    hour: Optional[int] = None
    minute = 0
    period: Optional[str] = None

    m = re.search(
        r"(?:الساعه|الساعة|الساعه|عند|في)\s*(\d{1,2})(?::(\d{2}))?\s*"
        r"(ص|م|صباحا|صباحًا|مساء|مساءً|بالليل|العصر|الظهر|الصبح|الفجر)?",
        text,
    )
    if m:
        hour, minute, period = int(m.group(1)), int(m.group(2) or 0), m.group(3)
    else:
        m = re.search(
            r"\b(\d{1,2})(?::(\d{2}))?\s*(ص|م|صباحا|صباحًا|مساء|مساءً|بالليل|العصر|الظهر|الصبح)\b",
            text,
        )
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
        hour += 12  # عُرف المواعيد: «الساعة 5» = 5 العصر

    return hour, max(0, min(59, minute))


def _parse_date(text: str, base: Optional[datetime] = None) -> Optional[datetime]:
    now = base or datetime.now()
    # تاريخ صريح 2026-10-20 أو 20/10/2026 أو 20-10
    m = re.search(r"\b(20\d{2})[-/](\d{1,2})[-/](\d{1,2})\b", text)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    m = re.search(r"\b(\d{1,2})[-/](\d{1,2})(?:[-/](20\d{2}))?\b", text)
    if m:
        day, month = int(m.group(1)), int(m.group(2))
        year = int(m.group(3)) if m.group(3) else now.year
        if 1 <= day <= 31 and 1 <= month <= 12:
            try:
                candidate = datetime(year, month, day)
                if candidate.date() < now.date() and not m.group(3):
                    candidate = candidate.replace(year=year + 1)
                return candidate
            except ValueError:
                return None
    # بعد النهاردة / بعد بكرة
    if "بعد بكره" in text or "بعد بكرة" in text:
        return now + timedelta(days=2)
    if any(w in text for w in ("النهارده", "النهاردة", "اليوم", "today")):
        return now
    if any(w in text for w in ("بكره", "بكرة", "بكرا", "غدا", "غدًا", "غداً", "tomorrow")):
        return now + timedelta(days=1)
    # بعد X وحدة
    m = re.search(r"بعد\s+(\d{1,3})\s*(يوم|ايام|أيام|ساعه|ساعة|ساعات|اسبوع|أسبوع|اسابيع|شهر|شهور)", text)
    if m:
        amount = int(m.group(1))
        unit = m.group(2)
        if "ساع" in unit:
            return now + timedelta(hours=amount)
        if "اسبوع" in unit or "أسبوع" in unit:
            return now + timedelta(weeks=amount)
        if "شهر" in unit:
            return now + timedelta(days=30 * amount)
        return now + timedelta(days=amount)
    m = re.search(r"بعد\s+(يوم|يومين|اسبوع|أسبوع|شهر|ساعه|ساعة)", text)
    if m:
        unit = m.group(1)
        if unit == "يومين":
            return now + timedelta(days=2)
        if "ساع" in unit:
            return now + timedelta(hours=2)
        if "اسبوع" in unit or "أسبوع" in unit:
            return now + timedelta(weeks=1)
        if "شهر" in unit:
            return now + timedelta(days=30)
        return now + timedelta(days=1)
    # يوم الأسبوع الجاي
    for name, idx in WEEKDAYS.items():
        if name in text:
            days_ahead = (idx - now.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7
            if "الجاي" in text or "القادم" in text:
                pass
            return now + timedelta(days=days_ahead)
    return None


def parse_when(text: str, base: Optional[datetime] = None) -> Dict[str, Optional[str]]:
    """يُرجع due_at/remind_at/remind_every من النص."""
    now = base or datetime.now()
    norm = normalize(text)
    result: Dict[str, Optional[str]] = {"due_at": None, "remind_at": None, "remind_every": "none", "when_text": None}

    every = "none"
    if any(w in norm for w in ("كل يوم", "يوميا", "daily")):
        every = "daily"
    elif any(w in norm for w in ("كل اسبوع", "اسبوعيا", "weekly")):
        every = "weekly"
    elif any(w in norm for w in ("كل شهر", "شهريا", "monthly")):
        every = "monthly"
    result["remind_every"] = every

    date_part = _parse_date(norm, now)
    time_part = _parse_time(norm)
    if date_part is None and time_part is None:
        if every != "none":
            due = now.replace(second=0, microsecond=0)
            result["due_at"] = due.strftime("%Y-%m-%d %H:%M")
            result["remind_at"] = result["due_at"]
            result["when_text"] = "متكرر"
        return result

    due = date_part or now
    if time_part:
        due = due.replace(hour=time_part[0], minute=time_part[1], second=0, microsecond=0)
    else:
        due = due.replace(hour=9, minute=0, second=0, microsecond=0)
    if date_part is None and time_part is not None and due < now:
        due = due + timedelta(days=1)

    result["due_at"] = due.strftime("%Y-%m-%d %H:%M")
    remind = due - timedelta(hours=1) if not (due.hour == 9 and time_part is None) else due
    if remind < now:
        remind = now + timedelta(minutes=5)
    result["remind_at"] = remind.strftime("%Y-%m-%d %H:%M")
    result["when_text"] = due.strftime("%Y-%m-%d %H:%M")

    # ---- فحص وقت الصلاة: لا مهام قبل/بعد صلاة بـ 20 دقيقة ----
    try:
        from prayer import is_prayer_window, prayer_block_end
        if is_prayer_window(due, block_min=20):
            new_due = prayer_block_end(due, block_min=20)
            result["due_at"] = new_due.strftime("%Y-%m-%d %H:%M")
            result["remind_at"] = (new_due - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M")
            result["when_text"] = new_due.strftime("%Y-%m-%d %H:%M") + " (بعد الصلاة)"
    except Exception:
        pass  # لو prayer مش متاح

    return result


# ------------------------------------------------------------------ التحليل
def classify_kind(text: str) -> Tuple[str, int]:
    n = normalize(text)
    scores = {
        "program_idea": _has(n, PROGRAM_IDEA) * 3 + _has(n, ["فكره", "فكرة"]) if ("فكره" in n or "فكرة" in n) else _has(n, PROGRAM_IDEA) * 3,
        "reminder": _has(n, REMINDER_WORDS),
        "task": _has(n, TASK_VERBS) * 2 + _has(n, TASK_HINTS),
        "idea": _has(n, IDEA_WORDS),
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
    """يُرجع (اسم التصنيف، هل اتحدد بثقة). الالتقاط الصريح من النص الخام يحفظ الـة."""
    raw = text or ""
    n = normalize(raw)
    explicit = re.search(r"(?:تصنيف|قسم|فولدر|folder)\s*[:：]\s*([\w\u0600-\u06FF ]{2,25})", raw)
    if not explicit:
        explicit = re.search(r"(?:في|من)\s+(?:تصنيف|قسم|فولدر|folder)\s+([\w\u0600-\u06FF ]{2,25})", raw)
    if explicit:
        return explicit.group(1).strip(), True
    best, best_hits = "", 0
    for name, words in CATEGORY_KEYWORDS:
        hits = _has(n, [normalize(w) for w in words])
        if hits > best_hits:
            best, best_hits = name, hits
    if best_hits:
        return best, True
    return "غير مصنف", False


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


def analyze(text: str, source: str = "ui", base: Optional[datetime] = None) -> Dict[str, Any]:
    """يحلّل النص ويُرجع قاموسًا جاهزًا لـstore.add_note + شرح للواجهة."""
    raw = (text or "").strip()
    if not raw:
        return {"ok": False, "error": "النص فاضي"}

    kind, kind_score = classify_kind(raw)
    category, cat_confident = classify_category(raw)
    priority = classify_priority(raw)
    when = parse_when(raw, base)
    tags = extract_tags(raw)

    if kind == "program_idea":
        category = "أفكار برامج"
        cat_confident = True

    question: Optional[str] = None
    needs_clarification = 0

    if kind == "note" and kind_score == 0 and len(raw) > 25:
        question = "ده نوت تحبه للذكرى، ولا مهمة عايز تتنفّذ في ميعاد؟"
        needs_clarification = 1
    elif kind == "task" and not when.get("due_at"):
        question = "المهمة دي لها ميعاد معيّن؟ اكتب مثلًا: «بكرة الساعة 5» أو «الأحد»."
        needs_clarification = 1
    elif not cat_confident:
        question = "أحطّها في أنهي تصنيف؟ (مثلًا: ليزر / حسابات / عملاء / شخصي)"
        needs_clarification = 1

    if kind == "program_idea":
        meta_questions = [
            "المشكلة اللي البرنامج بيحلها إيه بالظبط؟",
            "مين اللي هيستخدمه؟",
            "أهم 3 مزايا لازم تكون فيه؟",
            "عايز يشتغل على الموبايل ولا الكمبيوتر؟",
        ]
        question = "فكرة برنامج 💡 — نبدأ نوضّحها: " + " / ".join(meta_questions[:2])
        needs_clarification = 1
        meta = {"idea_questions": meta_questions, "stage": "مسودة"}
    else:
        meta = {}

    confidence = min(1.0, 0.45 + 0.15 * kind_score) if kind_score else 0.4
    title = _first_sentence(raw)

    return {
        "ok": True,
        "kind": kind,
        "title": title,
        "body": raw,
        "category": category,
        "priority": priority,
        "due_at": when.get("due_at"),
        "remind_at": when.get("remind_at"),
        "remind_every": when.get("remind_every") or "none",
        "tags": ", ".join(tags),
        "confidence": round(confidence, 2),
        "needs_clarification": needs_clarification,
        "question": question,
        "source": source,
        "meta": __import__("json").dumps(meta, ensure_ascii=False),
        "explain": {
            "kind": KIND_LABELS.get(kind, kind),
            "category": category,
            "priority": PRIORITY_LABELS.get(priority, priority),
            "when": when.get("when_text") or "من غير ميعاد",
            "confidence": round(confidence, 2),
        },
    }


KIND_LABELS = {
    "note": "📝 نوت",
    "task": "✅ مهمة",
    "reminder": "⏰ تذكير",
    "idea": "💡 فكرة",
    "program_idea": "🚀 فكرة برنامج",
}
PRIORITY_LABELS = {"low": "منخفضة", "normal": "عادية", "high": "مهمة", "urgent": "عاجلة"}


def confirm_message(note: Dict[str, Any], note_id: int) -> str:
    """رسالة تأكيد عربية مختصرة بعد الحفظ."""
    lines = [f"{KIND_LABELS.get(note.get('kind'), '📝 نوت')} — سجّلت (#{note_id}): {note.get('title')}"]
    lines.append(f"• التصنيف: {note.get('category')} | الأولوية: {PRIORITY_LABELS.get(note.get('priority'), 'عادية')}")
    lines.append(f"• الميعاد: {note.get('due_at') or 'من غير ميعاد'}"
                 + (f" | تذكير: {note.get('remind_at')}" if note.get('remind_at') else ""))
    if note.get("remind_every") and note.get("remind_every") != "none":
        lines.append(f"• التكرار: {note.get('remind_every')}")
    if note.get("question"):
        lines.append(f"❓ {note.get('question')}")
    return "\n".join(lines)