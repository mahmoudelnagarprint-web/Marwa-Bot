# -*- coding: utf-8 -*-
"""الجسر الموحد — نفس جداول المنظومة، نفس منطق النوايا، صفر منطق جديد.

ليه `bridge` أصلًا: «أفكاري» ليها تلات أبواب (تليجرام، واجهة الويب، وسطر
الأوامر). لو كل باب كتب منطق الالتقاط بتاعه، هيحصل تباعد: **نفس الجملة
تتحفظ من التليجرام وما تتحفظش من الويب**. عشان كده الملف ده **غلاف رقيق**:
`add`/`chat` بينادوا `bot.process_text` — المصدر الوحيد للمنطق — و`done`
وإخواتها بينادوا دوال `nb.db` المجمّدة. مفيش هنا أي تفنيد نوايا ولا SQL
جديد بيتكتب من دماغنا.

قاعدتان في الملف ده:

1. **مفيش أي إرسال لتليجرام.** `bridge` مابيستوردش `bot` غير للقراءة
   (`process_text` **مابتبعتش حاجة** لأي حد). لو حد احتاج `send` صريح،
   لازم يمر من `TelegramClient` مباشرة **وبتأكيد** — وده مش وظيفة الجسر.
2. **كل حاجة بترجع JSON-قابل للتحويل** (`_jsonable`) عشان سطر الأوامر
   يطبع JSON نضيف بلا `TypeError` على `datetime`/`Decimal`.

استيراد `bot` **جوّه الدوال** مقصود: `bot` بيستورد شبكة كاملة (polling،
squad، workshop، intent) و`intent` بيعمل `from nb import ai_router, config,
persona` — فاستيراده من فوق في ملف بيتستورد بدرّي (زي `acceptance.py`)
بيزود فرصة دورة استيراد بلا داعي. الجوّه بيقطعها تمامًا.
"""
from __future__ import annotations

import datetime as _dt
from decimal import Decimal
from typing import Any, Dict, List, Optional

from nb import config, db

__all__ = [
    "list_captures", "add", "chat", "today", "search", "stats", "status",
    "done", "reopen", "snooze", "category", "delete",
]


# ------------------------------------------------------------------ helpers
def _jsonable(value: Any) -> Any:
    """يحوّل نتيجة القاعدة لشكل JSON يقدر يتطبع ويتقرا من سطر الأوامر."""
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, (_dt.datetime, _dt.date)):
        return value.isoformat(sep=" ") if isinstance(value, _dt.datetime) else value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (int, float, bool, str)) or value is None:
        return value
    return str(value)


def _rows(sql: str, params: Optional[list] = None, **kw: Any) -> List[Dict[str, Any]]:
    return _jsonable(db.q(sql, params, **kw)) or []


def _bust() -> int:
    """يلغي كاش اللوحة بعد الكتابة — نفس منطق `web._bust` بالحرف."""
    try:
        from nb import cache
        return cache.invalidate("dash:")
    except Exception:                                     # noqa: BLE001
        return 0


def _owner_chat(chat_id: Optional[int]) -> int:
    return int(chat_id or config.OWNER_TELEGRAM_ID or 0)


def _exists(cid: int) -> bool:
    """هل الصف موجود فعلًا قبل أي فعل؟

    ليه: `db.set_capture_status` و`snooze_capture` بيسجّلوا حدث في
    `capture_events` بعد التحديث — فلو المعرف مش موجود، الـFK بيرمي
    `ForeignKeyViolation` بدل ما يرجّعوا «مفيش حاجة اتغيرت». الفحص
    (قراءة بس) بيخلّي الجسر يرد بصدق وأدب بدل traceback على معرف غلط.
    """
    try:
        return bool(db.scalar("SELECT 1 FROM captures WHERE id=%s", (int(cid),)))
    except Exception:                                     # noqa: BLE001
        return True                                       # مانمنعش المحاولة لو الفحص نفسه وقع


# ------------------------------------------------------------------ reads
def list_captures(status: str = "open", kind: Optional[str] = None,
                  search: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
    """نفس صفوف الويب بالحرف — التفويض لـ`db.list_captures` المجمّدة.

    `status="all"` (أو `None`) = بلا شرط حالة. `limit` رقم صحيح دايمًا.
    """
    st = None if (status in (None, "", "all")) else str(status)
    return _jsonable(db.list_captures(status=st, kind=kind or None,
                                     search=search or None, limit=int(limit))) or []


def search(q: str, limit: int = 20) -> List[Dict[str, Any]]:
    """بحث في كل الحالات — مش المفتوح بس (اللي بيدوّر بيدوّر في كل حاجة)."""
    return list_captures(status="all", search=q, limit=limit)


def today() -> Dict[str, Any]:
    """مستحق الآن + متأخر + ميعادهم النهاردة (بتوقيت القاهرة)."""
    today_date = db.now_local_date()
    return {
        "date": today_date,
        "due": _jsonable(db.due_reminders()) or [],
        "overdue": _jsonable(db.overdue_captures()) or [],
        "due_today": _rows(
            """SELECT * FROM captures
               WHERE status='open' AND due_at IS NOT NULL AND due_at::date = %s
               ORDER BY due_at ASC LIMIT 50""", (today_date,)),
    }


def stats() -> Dict[str, Any]:
    """الأرقام العشرة — نفس `db.stats()` اللي اللوحة بتقراها."""
    return _jsonable(db.stats()) or {}


def status() -> Dict[str, Any]:
    """حالة العقدة والتوفّر العالي والقاعدة — للفحص السريع بلا واجهة."""
    out: Dict[str, Any] = {"node": config.NODE_ID, "device": config.DEVICE_NAME}
    try:
        st = db.ha.status()
        out["ha"] = _jsonable(st)
        out["leader"] = bool(st.get("i_am_leader"))
    except Exception as exc:                              # noqa: BLE001
        out["ha"] = None
        out["ha_error"] = f"{type(exc).__name__}: {exc}"
    try:
        row = db.q("SELECT now() AS db_now", one=True) or {}
        out["db"] = "ok"
        out["db_now"] = _jsonable(row.get("db_now"))
    except Exception as exc:                              # noqa: BLE001
        out["db"] = "down"
        out["db_error"] = f"{type(exc).__name__}: {exc}"
    try:
        out["counts"] = _jsonable(db.stats())
    except Exception as exc:                              # noqa: BLE001
        out["counts_error"] = f"{type(exc).__name__}: {exc}"
    return out


# ------------------------------------------------------------------ the single write path
def add(text: str, chat_id: Optional[int] = None,
        source: str = "bridge") -> Dict[str, Any]:
    """يودّي النص على **بوابة النوايا الوحيدة** ويرجّع النتيجة بصدق.

    لو البوابة قرّرت إن ده كلام (`intent="chat"`) فـ**مفيش حاجة اتخزنت** —
    وبما إنها وظيفة `add`، بنبلّغ ده صريح في `saved` عشان المتصل ما يفترضش
    إن كل نداء `add` بينتج صف.
    """
    res = chat(text, chat_id=chat_id, source=source)
    res["saved"] = bool(res.get("note_id"))
    return res


def chat(text: str, chat_id: Optional[int] = None,
         source: str = "bridge") -> Dict[str, Any]:
    """`bot.process_text` — نفس مسار التليجرام والويب، و**بلا أي إرسال**."""
    from nb import bot                                        # استيراد جوّه: بلا دورة

    text = (text or "").strip()
    if not text:
        return {"ok": False, "intent": "chat", "reply": "", "kb": None, "note_id": None,
                "routed_by": "rules", "reason": "", "error": "نص فاضي", "saved": False}
    res = bot.process_text(text, chat_id=_owner_chat(chat_id), source=source)
    out = {k: res.get(k) for k in ("ok", "intent", "reply", "note_id", "routed_by",
                                   "reason", "error")}
    out["kb"] = res.get("kb")
    out["saved"] = bool(res.get("note_id"))
    out["source"] = source
    return _jsonable(out)


# ------------------------------------------------------------------ actions
def done(cid: int) -> Dict[str, Any]:
    if not _exists(cid):
        return {"ok": False, "id": int(cid), "action": "done", "changed": False,
                "error": "مفيش نوتة بالمعرف ده"}
    changed = bool(db.set_capture_status(int(cid), "done"))
    _bust()
    return {"ok": True, "id": int(cid), "action": "done", "changed": changed}


def reopen(cid: int) -> Dict[str, Any]:
    changed = db.x("UPDATE captures SET status='open', updated_at=now() WHERE id=%s",
                   (int(cid),)) > 0
    _bust()
    return {"ok": True, "id": int(cid), "action": "reopen", "changed": bool(changed)}


def snooze(cid: int, minutes: int = 60) -> Dict[str, Any]:
    if not _exists(cid):
        return {"ok": False, "id": int(cid), "action": "snooze", "value": int(minutes),
                "changed": False, "error": "مفيش نوتة بالمعرف ده"}
    changed = bool(db.snooze_capture(int(cid), int(minutes)))
    _bust()
    return {"ok": True, "id": int(cid), "action": "snooze",
            "value": int(minutes), "changed": changed}


def category(cid: int, name: str) -> Dict[str, Any]:
    name = (name or "").strip()
    if not name:
        return {"ok": False, "error": "لازم اسم تصنيف", "id": int(cid)}
    if not _exists(cid):
        return {"ok": False, "id": int(cid), "action": "category", "value": name,
                "changed": False, "error": "مفيش نوتة بالمعرف ده"}
    changed = db.x("""UPDATE captures SET category=%s, needs_clarification=FALSE,
                      question=NULL, updated_at=now() WHERE id=%s""",
                   (name, int(cid))) > 0
    _bust()
    return {"ok": True, "id": int(cid), "action": "category",
            "value": name, "changed": bool(changed)}


def delete(cid: int) -> Dict[str, Any]:
    changed = db.x("DELETE FROM captures WHERE id=%s", (int(cid),)) > 0
    _bust()
    return {"ok": True, "id": int(cid), "action": "delete", "changed": bool(changed)}
