# -*- coding: utf-8 -*-
"""كاش داخلي بذاكرة العملية (TTL) — R5.

ليه؟ لوحة القيادة بتعمل ~10 استعلامات، وكل استعلام على الـpooler بيكلّف
~0.6 ثانية اتصال. بدل ما نكرّرهم مع كل ضغطة/تحديث، بنحسبهم مرة وبنخزّن
النتيجة لعمر قصير (45 ثانية افتراضيًا).

قواعد السلامة:
- **آمن للخيوط**: Flask شغّال بـ`threaded=True` — كل وصول للقاموس تحت قفل.
- **الخيط الواحد ينفّذ مرة**: `get_or_set` بيمسك القفل وقت الحساب (single-flight)
  فـ10 طلبات متزامنة على مفتاح بائت = استعلام واحد، مش 10. ده اللي بيحمي
  الـpooler من عاصفة إعادة الحساب.
- **بلا تخزين للفشل**: لو الـ`producer` رمى استثناء، مفيش حاجة تتخزن
  والاستثناء يطلع للمتصل زي ما هو (مش بنخزّن خطأ كأنه بيانات).
- **بلا تسريب مراجع**: اللي بيخرج نسخة عميقة، فأي متصل يعدّل النتيجة
  بتاعته مش بيفسد الكاش لباقي الخيوط.
- **بلا تبعية**: مش بيعتمد على أي موديل تاني، فمفيش دورة استيراد.
"""
from __future__ import annotations

import copy
import threading
import time
from typing import Any, Callable, Dict, Tuple, TypeVar

T = TypeVar("T")

# key -> (expires_at_monotonic, value)
_store: Dict[str, Tuple[float, Any]] = {}
_lock = threading.RLock()

# عدّادات للرصد (تحت نفس القفل)
_hits = 0
_misses = 0
_stale = 0          # مفاتيح بائتة اتشالت
_started_at = time.monotonic()


def get_or_set(key: str, ttl: int, producer: Callable[[], Any]) -> Any:
    """يرجّع قيمة `key` من الكاش، أو بينفّذ `producer` ويخزّن نتيجته `ttl` ثانية.

    `ttl <= 0` = بلا تخزين (تنفيذ مباشر ومرور). ده مفيد لو حبينا نعطّل
    الكاش لمفتاح معيّن بدون تغيير الكود.
    """
    global _hits, _misses, _stale

    if ttl is None or int(ttl) <= 0:
        return producer()

    ttl = float(int(ttl))
    now = time.monotonic()

    # ملاحظة: القفل RLock وبنمسكه طول الحساب (single-flight).
    # لو الـproducer ندّه نفسه على نفس المفتاح هيرجع لنفس الخيط (RLock) —
    # ساعتها مفيش قفل تاني فمفيش جمود.
    with _lock:
        hit = _store.get(key)
        if hit is not None:
            expires_at, value = hit
            if expires_at > now:
                _hits += 1
                return copy.deepcopy(value)
            # بائت — نشيله ونحسب من جديد
            del _store[key]
            _stale += 1

        _misses += 1
        value = producer()          # تحت القفل عن قصد (single-flight)
        _store[key] = (now + ttl, value)
        return copy.deepcopy(value)


def invalidate(prefix: str = "") -> int:
    """يشيل المفاتيح اللي بتبدأ بـ`prefix` — أو **كل** المفاتيح لو فاضي.

    يرجع عدد المفاتيح اللي اتشالت. النداء الفاضي مقصود: أي كتابة لازم
    تقدر تلغي كل حاجة من غير ما تعرف أسماء المفاتيح.
    """
    with _lock:
        if not prefix:
            n = len(_store)
            _store.clear()
            return n
        doomed = [k for k in _store if k.startswith(prefix)]
        for k in doomed:
            del _store[k]
        return len(doomed)


def get(key: str, default: Any = None) -> Any:
    """قراءة صريحة بلا حساب — بترجّع `default` لو المفتاح غايب أو بائت."""
    with _lock:
        hit = _store.get(key)
        if hit is None:
            return default
        expires_at, value = hit
        if expires_at <= time.monotonic():
            del _store[key]
            return default
        return copy.deepcopy(value)


def set(key: str, value: Any, ttl: int) -> None:
    """تخزين قيمة جاهزة بعمر محدّد (بديل `get_or_set` لو القيمة عندنا)."""
    if ttl is None or int(ttl) <= 0:
        return
    with _lock:
        _store[key] = (time.monotonic() + float(int(ttl)), value)


def clear() -> int:
    """تفريغ كامل — نفس `invalidate("")` بس باسم صريح للاختبارات."""
    return invalidate("")


def stats() -> Dict[str, Any]:
    """إحصاءات الكاش — للوحة القيادة والفحص الصحي."""
    global _stale
    now = time.monotonic()
    with _lock:
        keys = list(_store.keys())
        live = sum(1 for k in keys if _store[k][0] > now)
        expires_in = min((_store[k][0] - now for k in keys), default=0.0)
        # بائتة لسه في القاموس (محدش قراها من بعد ما انتهت)
        dead = len(keys) - live
        _stale += dead
        hits, misses = _hits, _misses
    total = hits + misses
    return {
        "keys": live,
        "expired_pending": dead,
        "hits": hits,
        "misses": misses,
        "hit_rate": round(hits / total, 3) if total else 0.0,
        "invalidations": _stale,
        "oldest_expires_in_secs": round(expires_in, 1) if live else 0.0,
        "uptime_secs": round(now - _started_at, 1),
    }


def reset_stats() -> None:
    """تصفير العدّادات فقط (بيسيب المفاتيح مكانها) — للقياس قبل/بعد."""
    global _hits, _misses, _stale, _started_at
    with _lock:
        _hits = _misses = _stale = 0
        _started_at = time.monotonic()
