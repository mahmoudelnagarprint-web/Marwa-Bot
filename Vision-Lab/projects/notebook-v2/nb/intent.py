# -*- coding: utf-8 -*-
"""بوابة النوايا — «ده كلام ولا حاجة تتحفظ؟»

المشكلة اللي الملف ده بيحلها: البوت القديم كان بياخد **أي نص حر** ويرميه على
`ai_router.route` ← `db.add_capture`، فكلمة «هاي» اتحفظت كنوت (E3 في العقد).
هنا الحكم بيتاخد قبل أي حفظ، والافتراضي دايمًا **محادثة** — الحفظ محتاج دليل
صريح، مش مجرد فشل في التصنيف.

ترتيب الأدلة (من الأقوى للأضعف):
1. إشارة مرجعية («حطها…») ← نرجّعها للرسالة السابقة ونحللها مع بعض.
2. إشارة محادثة قوية (تحية/شكر/وداع قصيرة) ← محادثة، **بلا أي نداء شبكة**.
3. إشارة التقاط صريحة (فكرني/احفظ/اعمل…/موعد/تاريخ) ← التقاط.
4. النص محتاجه تفسير: نسأل الموديل عن النوع.
   - نوع من CAPTURE_KINDS ← التقاط.
   - نوع محادثة (greeting/message/chat…) ← محادثة (دي إشارة الموديل نفسه).
   - فشل أو نوع مبهم ← **محادثة** + تسجيل السبب الحقيقي (A6).

الـ`gate` **بتحلّل بس ومابتكتبش**: الحفظ والرد مسؤولية `bot.py`/`web.py`.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from nb import ai_router, config, persona

INTENT_CHAT = "chat"
INTENT_CAPTURE = "capture"

# إشارات التقاط صريحة — أفعال حفظ أو أفعال أمر، **مش أسماء فضفاضة**.
# ⚠️ «فكرة» و«مشروع» و«خامات» لوحدها كانت بتخلي «دي كانت فكرة حلوة» تتسجّل
# كنوت. الأسماء دي بقت عبارات مركبة («فكرة برنامج») أو بتسيب الحكم للموديل.
CAPTURE_WORDS = (
    "فكرني", "ذكرني", "افتكرني", "تذكير", "متنساش", "متنسانيش",
    "احفظ", "احفظلي", "سجل", "سجللي", "خزّن", "ضيف", "اضف",
    "اعمللي", "اعمل لي", "لازم", "مطلوب", "مهمه", "تاسك", "todo",
    "التزام", "فاتوره", "مصروف", "اشتري", "جهز", "سلم", "كلم", "اتصل",
    "راجع", "ابعت", "اطلب", "احجز", "تابع", "اتاكد", "اصلح", "صلح",
    # عبارات مركبة صريحة (مش كلمة واحدة)
    "فكره برنامج", "فكرة برنامج", "فكره تطبيق", "فكرة تطبيق",
    "فكره مشروع", "فكرة مشروع", "مشروع جديد", "برنامج جديد", "تطبيق جديد",
    "احتياج ورشه", "احتياج الورشه", "قائمه مشتريات", "قائمة مشتريات",
    "ملاحظه", "ملاحظة", "نوت", "مذكر", "خامات ناقصه", "خامات ناقصة",
)

# إشارات مرجعية: الكلام عن حاجة اتقالت قبله.
# ⚠️ لازم مطابقة **كلمة بكلمة** مش substring: «النهاردة» جواها «ده» و«واحده»
# جواها «ده» — بالمطابقة الفرعية كان أي سؤال فيه «النهاردة» بيتفسّر كإحالة
# للرسالة السابقة! (اتمسكت بقياس فعلي: «عامل ايه النهاردة؟» ← capture غلط)
REF_PHRASES = ("حطها في ملف", "في نفس الملف", "في ملف", "اللي فوق", "اللي فات",
               "الرساله اللي فاتت", "الرسالة اللي فاتت", "الرساله السابقه",
               "الرسالة السابقة", "اللي قلتلك عليه", "اللي كتبته")
REF_VERBS = ("حطها", "حطه", "حطهم", "سجلها", "سجله", "سجلهم", "ضيفها", "ضيفه",
             "خليها", "خليه", "اعملها", "اعمله", "نفسها", "نفسه")
REF_DEMO = ("دي", "ده", "دى", "دول")
REF_ANCHORS = ("في ملف", "فكرني", "احفظ", "سجل", "ضيف", "نوت", "ملاحظه", "ملاحظة")

# إشارات محادثة قوية (قصيرة بس)
CHAT_WORDS = (
    "مين انت", "انت مين", "اسمك ايه", "بتعملي ايه", "بتعرف تعمل ايه",
    "ايه الاخبار", "اخبار ايه", "تمام", "ماشي", "اوك", "طيب", "زي الفل",
    "الحمد لله", "ربنا يكرمك", "تعبك راحه", "صباح النور", "مساء النور",
)

_QUESTION_STARTS = ("ايه", "إيه", "ازاي", "إزاي", "ليه", "امتى", "أمتى", "فين", "هل", "مين", "كام")
_SELF_WORDS = ("انت", "أنت", "اسمك", "بتعملي", "بتعمل ايه", "نفسك")

# حشو بيتشال قبل ما نتأكد إن النص «تحية صافية»
_GREET_FILLERS = ("يا فوفا", "فوفا", "يا محمود", "محمود", "يا افكار", "افكار",
                  "لو سمحت", "من فضلك", "يا باشا", "باشا", "يا معلم", "يا نجم")

_ALL_GREET = (persona.GREETING_WORDS + persona.THANKS_WORDS + persona.FAREWELL_WORDS
              + CHAT_WORDS)


def _n(text: str) -> str:
    return ai_router.normalize(text)


def _hit(norm: str, words) -> Optional[str]:
    for word in words:
        w = _n(word)
        if w and w in norm:
            return word
    return None


def _tokens(text: str) -> List[str]:
    return re.findall(r"[a-z0-9\u0600-\u06ff]+", _n(text))


def _pure_chat(norm: str) -> bool:
    """النص **كله** تحية/شكر/كلام قصير — مش جملة فيها كلمة تحية.

    ده الفرق المهم: «هاي» تحية صافية، بينما «عامل ايه النهاردة؟» جملة حوارية
    لازم تروح للموديل يرد عليها رد حقيقي. المطابقة بالمحتوى الفرعي (substring)
    كانت بتبلع أي سؤال فيه «عامل ايه»، ففوفا كانت بترد ترحيب جاهز بدل رد.

    بنقارن **كلمة بكلمة** (مش substring): كل كلمات النص لازم تكون من مفردات
    التحية. `النهاردة` مش منها ← جملة حوارية ← تروح للموديل.
    """
    tokens = _tokens(norm)
    if not tokens or len(tokens) > 4:
        return False
    greet_tokens = set()
    for word in _ALL_GREET + _GREET_FILLERS:
        greet_tokens.update(_tokens(word))
    return all(t in greet_tokens for t in tokens)


def looks_like_greeting(text: str) -> bool:
    """تحية/شكر/وداع **صافية** — أسرع مسار (بلا شبكة). مش أي جملة فيها تحية."""
    norm = _n(text)
    if not norm or len(norm) > 40:
        return False
    # علامة استفهام = سؤال، والسؤال محتاج رد حقيقي على السؤال مش ترحيب جاهز
    if "؟" in (text or "") or "?" in (text or ""):
        return False
    if not _pure_chat(norm):
        return False
    return not _hit(norm, CAPTURE_WORDS)


def looks_like_question(text: str) -> bool:
    norm = _n(text)
    if "؟" in (text or "") or "?" in (text or ""):
        return True
    return any(norm.startswith(_n(w)) for w in _QUESTION_STARTS)


# علامات ساعة صريحة: التاريخ لوحده (بكرة/النهاردة) مش دليل التقاط
_TIME_MARKERS = ("الساعه", "الساعة", "ساعه", "ساعة", "الصبح", "بالليل", "العصر",
                 "الظهر", "المغرب", "الفجر", "الجمعه", "الجمعة", "السبت", "الاحد",
                 "الأحد", "الاتنين", "الاثنين", "الثلاثاء", "الاربعاء", "الأربعاء",
                 "الخميس", "القادم", "الجاي")


def has_capture_signal(text: str) -> bool:
    """دليل التقاط صريح: فعل حفظ/أمر، أو #وسم، أو **ميعاد بساعة محددة**.

    ⚠️ التاريخ لوحده مش دليل: `parse_when("النهاردة")` بيرجّع 9 صباحًا افتراضيًا،
    فكان أي كلام فيه «النهاردة» (زي «عامل ايه النهاردة؟») بيتفسّر كالتقاط
    ويتسجّل. دلوقتي التاريخ محتاج **ساعة صريحة** معاه عشان يبقى دليل.
    """
    norm = _n(text)
    if _hit(norm, CAPTURE_WORDS):
        return True
    if ai_router.extract_tags(text):
        return True
    when = ai_router.parse_when(text)
    if not when.get("due_at"):
        return False
    if "الساعه" in norm or "الساعة" in text:
        return True
    if re.search(r"\d{1,2}\s*[:.]\s*\d{2}", text or ""):
        return True
    return _hit(norm, _TIME_MARKERS) is not None


def is_reference(text: str) -> bool:
    """الكلام عن الحاجة اللي فاتت — بمطابقة **كلمة بكلمة** مش substring.

    شرطان: (١) إشارة صريحة (فعل زي «حطها» أو جملة زي «في ملف»)، أو ضمير
    إشارة **+** كلمة حفظ (عشان «دي» لوحدها في «دي كانت فكرة حلوة» مش إحالة).
    (٢) النص قصير — الجملة الطويلة كلام عادي مش إحالة.
    """
    norm = _n(text)
    if not norm or len(norm) > 45:
        return False
    tokens = set(_tokens(norm))
    all_tokens = _tokens(norm)
    for phrase in REF_PHRASES:
        ptoks = _tokens(phrase)
        if ptoks and all(t in all_tokens for t in ptoks):
            return True
    if tokens & {_n(w) for w in REF_VERBS}:
        return True
    if (tokens & {_n(w) for w in REF_DEMO}) and (tokens & {_n(w) for w in REF_ANCHORS}):
        return True
    return False


def resolve_reference(text: str, past: List[Dict[str, str]]) -> tuple:
    """(النص الفعلي، الرسالة المرجعية أو None).

    «حطها في ملف فكرني» لوحدها مالهاش معنى — بنلزقها بآخر رسالة من المستخدم
    عشان الحفظ يبقى واضح ومفهوم (A5).
    """
    if not is_reference(text):
        return text, None
    previous = None
    for row in reversed(past or []):
        if row.get("role") == "user" and (row.get("content") or "").strip():
            candidate = row["content"].strip()
            if _n(candidate) != _n(text):
                previous = candidate
                break
    if not previous:
        return text, None
    return f"{previous} — {text.strip()}", previous


def local_intent(text: str, past: List[Dict[str, str]]) -> tuple:
    """(intent, reason, effective_text, reference) بلا شبكة."""
    effective, reference = resolve_reference(text, past)
    if reference:
        return INTENT_CAPTURE, f"مرجع للرسالة السابقة: «{reference[:60]}»", effective, reference
    if looks_like_greeting(text):
        return INTENT_CHAT, "تحية/شكر قصيرة (قواعد محلية)", effective, None
    if has_capture_signal(text):
        return INTENT_CAPTURE, "إشارة التقاط صريحة (قواعد محلية)", effective, None
    if looks_like_question(text) and len(_n(text)) <= 60:
        return INTENT_CHAT, "سؤال قصير (قواعد محلية)", effective, None
    return None, "", effective, reference


def cloud_intent(text: str, timeout: int = 25) -> tuple:
    """(intent، السبب) من الموديل — بيرجّع None مع السبب عند الفشل."""
    kind, err = ai_router.classify_kind_cloud(text, timeout=timeout)
    if err:
        return None, err
    if not kind:
        return None, "رد بلا نوع صالح"
    if kind in ai_router.CAPTURE_KINDS:
        return INTENT_CAPTURE, f"الموديل قال kind={kind}"
    return INTENT_CHAT, f"الموديل قال kind={kind} (نوع محادثة)"


def gate(text: str, chat_id: Optional[int] = None,
         history: Optional[List[Dict[str, str]]] = None,
         source: str = "telegram", use_cloud: bool = True,
         cloud_timeout: int = 25) -> Dict[str, Any]:
    """يحكم على النص: محادثة ولا التقاط — وبيرجّع التحليل جاهز للحفظ.

    الحقول الراجعة:
      intent    : "chat" | "capture"  (الافتراضي دايمًا chat)
      reply     : رد جاهز للتحيات (أو None ← البوت ينده persona.reply)
      analysis  : تحليل ai_router.route() كامل عند التقاط، وإلا None
      routed_by : "rules" أو "llm:…" أو "rules(cloud-failed:…)"
      reason    : السبب الحقيقي للقرار — يتسجّل دايمًا
      reference : الرسالة اللي اتشير ليها، لو في
    """
    raw = (text or "").strip()
    if not raw:
        return {"intent": INTENT_CHAT, "reply": None, "analysis": None,
                "routed_by": "rules", "reason": "نص فاضي", "reference": None}

    past = history if history is not None else persona.history(chat_id, 12)
    intent, reason, effective, reference = local_intent(raw, past)
    routed_by = "rules"

    if intent is None:
        if not use_cloud:
            return {"intent": INTENT_CHAT, "reply": None, "analysis": None,
                    "routed_by": "rules", "reason": "غير حاسم وبلا سحابة — الافتراضي محادثة",
                    "reference": reference}
        cloud_result, cloud_reason = cloud_intent(effective, timeout=cloud_timeout)
        if cloud_result is None:
            # فشل السحابة = **محادثة** (مش حفظ) — الفشل مش دليل على إن فيه حاجة تتحفظ
            routed_by = f"rules(cloud-failed: {cloud_reason[:80]})"
            reason = f"غير حاسم وفشل الفحص السحابي — الافتراضي محادثة ({cloud_reason[:120]})"
            config.log(f"intent: {reason}")
            return {"intent": INTENT_CHAT, "reply": None, "analysis": None,
                    "routed_by": routed_by, "reason": reason, "reference": reference}
        intent, reason = cloud_result, cloud_reason
        routed_by = "llm"

    if intent == INTENT_CHAT:
        fast = persona.local_reply(raw) if looks_like_greeting(raw) else None
        return {"intent": INTENT_CHAT, "reply": fast, "analysis": None,
                "routed_by": routed_by, "reason": reason, "reference": reference}

    # التقاط: نحلّل النص الفعلي (بعد فك المرجع) تحليل كامل
    analysis = ai_router.route(effective, source=source)
    if not analysis.get("ok"):
        return {"intent": INTENT_CHAT, "reply": None, "analysis": None,
                "routed_by": "rules", "reason": f"التحليل رفض النص: {analysis.get('error')}",
                "reference": reference}
    if reference:
        analysis.setdefault("meta", {})["reference_of"] = reference[:200]
        analysis["body"] = effective
    routed_by = analysis.get("routed_by") or "rules"
    if analysis.get("cloud_error") and routed_by == "rules":
        routed_by = f"rules(cloud-failed: {str(analysis['cloud_error'])[:80]})"
    return {"intent": INTENT_CAPTURE, "reply": None, "analysis": analysis,
            "routed_by": routed_by, "reason": reason, "reference": reference}
