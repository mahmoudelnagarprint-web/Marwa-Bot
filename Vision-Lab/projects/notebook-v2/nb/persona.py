# -*- coding: utf-8 -*-
"""شخصية «فوفا» — صوت «أفكاري».

القاعدة الحاكمة: فوفا **بتتكلم**، ومش بتخترع. لو مفيش مزود سحابي، بترد رد محلي
قصير وصادق (مش رسالة خطأ تقنية)، ولو الرد السحابي رجع تفكير خام بيتشال في
`providers.strip_reasoning` قبل ما يوصل للمستخدم.

كمان الملف ده فيه ذاكرة المحادثة (تسجيل/قراءة) — بتنادي دوال `nb.db` المتفق
عليها في العقد، ولو لسه ما نزلتش على القرص بتشتغل احتياطيًا على نفس الجدول
`conversations` بالحقول المتفق عليها (chat_id, role, content, meta, created_at).
الاحتياطي مؤقت ومقصود: البوت يفضل شغال قبل ما طبقة قاعدة البيانات تكتمل.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

from nb import config, db, providers

PERSONA_NAME = "فوفا"
APP_NAME = "أفكاري"
BOT_USERNAME = config.TELEGRAM_AFKARY_USERNAME
OWNER_ADDRESS = "يا أفكار"

SYSTEM_PROMPT = """أنت «فوفا» — المساعدة الشخصية لتطبيق «أفكاري»، وبتتكلمي مع محمود النجار
(صاحب ورشة النجار برنت للطباعة والقص بالليزر) بالعامية المصرية.

قواعدك الثابتة:
1. ردودك قصيرة جدًا: سطر لسطرين، بلا مقدمات طويلة وبلا شرح.
2. نادِيه بـ«يا أفكار» أو «يا محمود» أحيانًا، وبودّ ودفء بسيط بلا مبالغة.
3. **ممنوع** تخترعي أي رقم أو موعد أو حالة من عندك. اللي مش عندك تقولي إنه مش عندك.
4. لو الرسالة مجرد تحية أو سؤال أو كلام عادي: ردي كلام وخلاص.
   **ومتتكلميش عن الحفظ خالص** — لا تقولي «هحفظ» ولا «مش هحفظ» ولا تعلّقي على
   نيتك. الحفظ موضوع داخلي مش جزء من الكلام مع محمود.
5. ممنوع تمامًا أي كلام بين قوسين عن نفسك أو عن قواعدك أو عن «ملحوظة» داخلية.
   اللي بيتكلم معاك محمود مش بيقرأ تعليماتك — مايتعرضش لها.
6. متكرريش نفس الجملة مرتين، ومتكرريش سؤالك. جملة واحدة واضحة كفاية.
6. ممنوع markdown معقد أو جداول أو إنجليزي. عربي بسيط بس.
7. لو سأل عن مهامه أو مواعيده وانت مش شايفة بيانات، قولي له يبعت «مهام اليوم»
   أو «المستحق» بدل ما تخترعي إجابة.
"""

# ردود محلية — بتُستخدم لمّا المزود السحابي يكون غير متاح، وبتبان برضه
# كإشارة حاسمة في بوابة النوايا (تحية = محادثة، بلا أي نداء شبكة).
GREETING_WORDS = ("هاي", "هي", "اهلا", "أهلا", "السلام عليكم", "صباح الخير",
                  "مساء الخير", "ازيك", "إزيك", "عامل ايه", "اخبارك", "أخبارك",
                  "hello", "hi", "hey", "صباحو", "تصبح على خير")
THANKS_WORDS = ("شكرا", "شكرًا", "تسلم", "تسلمي", "thanks", "thank you", "merci")
FAREWELL_WORDS = ("سلام", "باي", "تصبح", "اشوفك", "أشوفك", "bye")


def local_reply(text: str) -> str:
    """رد محلي قصير بلا شبكة — للتحيات والشكر والوداع."""
    from nb import ai_router
    n = ai_router.normalize(text)
    # مطابقة على **الكلمات** مش على أي جزء من النص: «السلام عليكم» فيها «سلام»،
    # وكانت بتتصنّف وداع فترد «مستنياك ترجع» على تحية. وكمان الترتيب: التحية
    # الصريحة قبل الوداع، لأن «السلام عليكم [..] ازيك» تحية مركّبة.
    toks = [t for t in __import__("re").split(r"[^\w\u0600-\u06FF]+", n) if t]
    tset = set(toks)

    def _hit(words) -> bool:
        for w in words:
            wn = ai_router.normalize(w)
            if not wn:
                continue
            if " " in wn:                     # عبارة: لازم تبدأ ببها
                if n.startswith(wn):
                    return True
            elif wn in tset:                  # كلمة: مطابقة كاملة
                return True
        return False

    if _hit(THANKS_WORDS):
        return "العفو يا أفكار 💙 تحت أمرك على طول."
    # الترتيب زي الأصل: شكر ← وداع ← تحية على الساعة. «تصبح على خير» في قايمة
    # التحية و«تصبح» في قايمة الوداع، والصح إنها وداع — فلو قدّمنا التحية كانت
    # هترد «صباح الخير» على «تصبح على خير». والمطابقة بالكلمات خلاص حلّت
    # «السلام عليكم» (جواها «سلام») بلا أي حاجة لإعادة الترتيب.
    if _hit(FAREWELL_WORDS):
        return "سلام يا أفكار 👋 مستنياك ترجع."
    hour = __import__("datetime").datetime.now().hour
    if hour < 12:
        return "صباح الخير يا أفكار ☀️ إيه أخبارك النهاردة؟"
    if hour < 18:
        return "أهلاً يا أفكار 👋 أقولك إيه النهاردة؟"
    return "مساء الفل يا أفكار 🌙 إيه اللي في دماغك؟"


def unavailable_reply() -> str:
    """رد صادق لما المزود السحابي يفشل — صوت فوفا، مش رسالة خطأ تقنية."""
    return ("أنا سامعاك يا أفكار، بس دماغي السحابية مش متاحة دلوقتي 🤍\n"
            "ابعت النص تاني وأنا أحفظه، أو اكتب «حالة» تشوف الوضع.")


# كلمات بسيطة بتتخلط بالتحية وبتحافظ عليها «كلام صافي»:
# «صباح الخير يا أفكار» أو «ازيك يا محمود» تفضل تحية عادية.
_SMALL_TALK_EXTRA = ("يا", "افكار", "محمود", "فوفا", "ازيك", "عامل", "عامله",
                     "ايه", "اخبارك", "النهارده", "كويس", "كويسه", "الحمد", "لله",
                     "خير", "صباح", "مساء", "الفل", "بخير", "تمام", "زي", "العفو",
                     "شكرا", "على", "من", "في", "و", "مسائك", "صباحك")


def _is_small_talk(text: str) -> bool:
    """تحية/شكر/وداع **صافية** — بلا أي import من `intent` (حلقة دائرية).

    `intent.py` بيعمل `from nb import persona`، فاستيراد `intent` هنا هيلف
    على نفسه. عشان كده الفحص هنا بالقوائم المحلية بتاعة الملف ده (سطور 45–49)
    بدل ما نستدعي `intent.looks_like_greeting`.

    الفحص **صارم عن قصد**: كل كلمة في النص لازم تكون من مفردات التحية أو من
    الحشو المسموح. مفيش أي مطابقة جزئية (substring) بتعدّي لوحدها — لأن
    «هي» جزء من كلمات كتير في العربي، ومن غير الشرط ده «اقترح أفكار للورشة»
    كانت هتعدّي كتحية.
    """
    import re as _re
    from nb import ai_router
    raw = (text or "").strip()
    if not raw:
        return False
    # علامة استفهام = سؤال حقيقي، والسؤال محتاج إجابة مش ترحيب جاهز
    if "؟" in raw or "?" in raw:
        return False
    n = ai_router.normalize(raw)
    if not n or len(n) > 40:
        return False
    phrases = [ai_router.normalize(w) for w in
               (GREETING_WORDS + THANKS_WORDS + FAREWELL_WORDS)]
    # المفردات: العبارة كاملة + كل كلمة جوّاها («صباح الخير» = صباح + الخير)،
    # لأن التقسيم بيشتغل على الكلمات مش على العبارات.
    vocab: set = set()
    for p in phrases:
        vocab.add(p)
        vocab.update(t for t in _re.split(r"\s+", p) if t)
    vocab.update(ai_router.normalize(w) for w in _SMALL_TALK_EXTRA)
    vocab.discard("")
    tokens = [t for t in _re.split(r"[^\w\u0600-\u06FF]+", n) if t]
    if not tokens:
        return False
    # لازم **تبدأ** بعبارة تحية/شكر/وداع: كلمة «هي» موجودة في القائمة لكن
    # «هي الورشة خلصت الشغلانة» جملة عادية، والشرط ده هو اللي بيفرّق.
    if not any(n == p or n.startswith(p + " ") for p in phrases if p):
        return False
    return all(t in vocab for t in tokens)


# ------------------------------------------------------------------ ذاكرة المحادثة
def _has(name: str) -> bool:
    return callable(getattr(db, name, None))


def remember(chat_id: int, role: str, content: str,
             meta: Optional[Dict[str, Any]] = None) -> int:
    """تسجيل رسالة في ذاكرة المحادثة. بترجّع رقم الصف (0 = ما اتسجلش)."""
    text = (content or "").strip()
    if not text or chat_id is None:
        return 0
    try:
        if _has("log_message"):
            return int(db.log_message(chat_id, role, text, meta) or 0)
        return int(db.x(
            "INSERT INTO conversations (chat_id, role, content, meta) VALUES (%s,%s,%s,%s)",
            (chat_id, role, text, json.dumps(meta or {}, ensure_ascii=False))) or 0)
    except Exception as exc:
        config.log(f"persona: تسجيل المحادثة فشل ({type(exc).__name__}: {str(exc)[:160]})")
        return 0


def history(chat_id: int, limit: int = 12) -> List[Dict[str, str]]:
    """آخر رسائل المحادثة **من الأقدم للأحدث** (بترتيب الزمن الطبيعي)."""
    if chat_id is None:
        return []
    try:
        if _has("recent_messages"):
            rows = db.recent_messages(chat_id, limit) or []
        else:
            rows = db.q(
                "SELECT role, content FROM (SELECT role, content, created_at FROM conversations "
                "WHERE chat_id=%s ORDER BY created_at DESC, id DESC LIMIT %s) t "
                "ORDER BY created_at ASC", (chat_id, int(limit)))
        return [{"role": r["role"], "content": r["content"]} for r in rows
                if r.get("role") in ("user", "assistant") and r.get("content")]
    except Exception as exc:
        config.log(f"persona: قراءة المحادثة فشلت ({type(exc).__name__}: {str(exc)[:160]})")
        return []


def count(chat_id: int) -> int:
    try:
        if _has("count_messages"):
            return int(db.count_messages(chat_id) or 0)
        return int(db.scalar("SELECT count(*) FROM conversations WHERE chat_id=%s", (chat_id,)) or 0)
    except Exception:
        return 0


# ------------------------------------------------------------------ الرد
# ملاحظات داخلية ظهرت فعلًا من الموديل للمستخدم — بتتشال هي ومحتواها.
# بنمسك **القوس كامل** اللي جواه كلمة عن الحفظ/النية، لأن الموديل بيسيب
# أقواس مفتوحة أحيانًا («(ملاحظة: مش هحفظ حاجة دلوقتي) عامل إيه؟»).
_META_WORDS = ("ملحوظ", "ملاحظ", "هحفظ", "مش هحفظ", "هسجل", "مش هسجل",
               "داخلية", "دي مجرد تحية", "الحفظ بيحصل", "نيتي", "قواعدي",
               "تعليماتي", "كمساعد", "as an ai")


def _strip_meta(text: str) -> str:
    """يشيل الأقواس الداخلية وأي جملة بتتكلم عن الحفظ/النوايا/القواعد."""
    import re as _re
    # ١) أقواس متوازنة جواها كلمة داخلية
    def _drop_balanced(chunk: str) -> str:
        def repl(m):
            inner = m.group(1) or ""
            low = inner.lower()
            return " " if any(w in low for w in _META_WORDS) else m.group(0)
        return _re.sub(r"\(([^()]*)\)", repl, chunk)
    text = _drop_balanced(text)
    # ٢) قوس مفتوح ما اتقفلش وفيه كلمة داخلية → يتشال لآخر النص
    text = _re.sub(r"\(\s*(?:ملحوظ|ملاحظ|مش هحفظ|هحفظ)[^)\n]*$", " ", text,
                   flags=_re.IGNORECASE)
    # ٣) نص مكشوف بلا أقواس: «ملحوظة: ...» لآخر الجملة
    text = _re.sub(r"(?:^|[\n\.])\s*ملحوظ[ةه]\s*:[^\.\n]*", " ", text)
    return text


def _polish(answer: str) -> str:
    """تنضيف أخير قبل الإرسال: ملاحظات داخلية + جمل مكرّرة + فراغات ميتة.

    ده دفاع ثاني بعد الـprompt: الـprompt ممكن يتجاهَل، لكن المستخدم عمره ما
    يشوف تعليق عن «الحفظ» أو نفس الجملة مرتين.
    """
    import re as _re
    text = _strip_meta((answer or "").strip())
    text = _re.sub(r"[ \t]{2,}", " ", text)
    text = _re.sub(r"\n{3,}", "\n\n", text).strip(" \n-—:،")
    # شيل جمل مكرّرة (الموديل بيكرّر نفسه أحيانًا)
    parts = [p.strip() for p in _re.split(r"(?<=[.!؟?])\s+|\n+", text) if p.strip()]
    seen, uniq = set(), []
    for part in parts:
        key = _re.sub(r"[\s\W]+", "", part)  # تطبيع: نفس الجملة = نفس المفتاح
        if key and key not in seen:
            seen.add(key)
            uniq.append(part)
    if uniq:
        text = "\n".join(uniq) if len(uniq) > 1 else uniq[0]
    return text.strip()


def reply(text: str, chat_id: Optional[int] = None, history_limit: int = 12,
          timeout: int = 30, max_tokens: int = 200) -> Tuple[str, Dict[str, Any]]:
    """رد فوفا على كلام حر.

    `max_tokens` صغير عن قصد (~200): الدردشة مش محتاجة 700 توكن، والسقف
    الأصغر بيقصّر الزمن بشكل ملموس. لو الموديل صرفهم كلهم على التفكير،
    `providers.chat` بيرفع السقف ويعيد المحاولة لوحده.

    بيرجّع (نص عربي جاهز للإرسال، meta). وفي كل حالات الفشل بيرجّع جملة عربية
    معقولة — عمره ما بيرمي استثناء على البوت ولا بيعرض نص إنجليزي للمستخدم.
    """
    past = history(chat_id, history_limit) if chat_id is not None else []
    messages: List[Dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages += past
    messages.append({"role": "user", "content": (text or "").strip()})
    try:
        answer, meta = providers.chat(messages, max_tokens=max_tokens, temperature=0.6,
                                      json_mode=False, timeout=timeout,
                                      min_tokens=max_tokens, total_timeout=timeout + 10)
        raw = answer or ""
        answer = _polish(providers.strip_reasoning(raw))
        # دفاع أخير: لو أي أثر تفكير عدي، مايتعرضش للمستخدم أبدًا
        meta["raw_had_think"] = raw != providers.strip_reasoning(raw)
        meta["raw_len"] = len(raw)
        if not answer:
            raise providers.ProviderError("رد فاضي بعد تنضيف التفكير")
        meta["fallback"] = False
        return answer, meta
    except Exception as exc:
        config.log(f"persona: الرد السحابي فشل — "
                   f"[{type(exc).__name__}: {str(exc)[:220]}]")
        # `local_reply` بتختار على **الساعة بس** — تصلح للتحيات/الشكر/الوداع
        # فقط. لو المالك سأل سؤالًا حقيقيًا وقت انقطاع، «صباح الخير إيه أخبارك
        # النهاردة؟» بتبان إنه مش سامع، مش إن السحابة واقعة. فبنرد الرد الصادق.
        try:
            small_talk = _is_small_talk(text)
        except Exception:
            small_talk = True  # أسوأ حالة: رد محلي مهذّب بدل نص صريح
        body = local_reply(text) if small_talk else unavailable_reply()
        return body, {"fallback": True, "small_talk": small_talk,
                      "error": f"{type(exc).__name__}: {str(exc)[:220]}"}
