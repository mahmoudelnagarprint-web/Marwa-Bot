# -*- coding: utf-8 -*-
"""طبقة الاتصال المركزية الوحيدة (Single Source of Truth) — منظومة النجار برنت.

task-2: قطع قراءة الوكلاء من `pos_data.db` القديم وربطهم بالمصدر الحي.

القاعدة الحاكمة (مُثبتة بالقياس 2026-10-18):
  • المصدر الرسمي الحي = ``G:\\ai\\Elnagar POS\\pos_data.db`` — قاعدة التطبيق الشغّال
    فعلاً الآن (Flask على 8888 + Mobile API على 7777، بدأ 2026-10-17 23:57:09).
    56 عميلاً/58 طلباً، أقصى طلب #334، إجمالي المديونيات 1040.0 جنيه.
  • أي نسخة `pos_data.db` أخرى (مساحة العمل، الساندبوكس، النسخ الاحتياطية، الأرشيف)
    = مصدر قديم/ميت → **رفض صريح + تحذير**، ولا تُستخدم في أي استعلام حي.
  • كل قراءة تمر من هنا. لا يوجد مسار SQLite آخر مسموح به للاستعلام الحي.

التجاوز بمنفذ واحد: ``POS_LIVE_DB`` (للاختبار على نسخة) — لكنه يظل محكوماً:
أي مسار يُصنَّف «قديم» يُرفض حتى لو جاء من المتغير.

الكتابة على القاعدة الحية ممنوعة من هذه الطبقة افتراضياً:
يلزم ``POS_LIVE_WRITE=1`` **و** ``approved=True`` صراحة.

لا تُطبع أي أسرار (كلمات مرور/مفاتيح) من هذا الملف — هو لا يقرأ أسراراً أصلاً.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ─────────────────────────────────────────────────────────── المواقع والثوابت
CONFIG_DIR = Path(__file__).resolve().parent
VISION_LAB = CONFIG_DIR.parent                      # G:\ai\Naggar Print POS Agent\Vision-Lab
AGENT_ROOT = VISION_LAB.parent                      # G:\ai\Naggar Print POS Agent
CONFIG_FILE = CONFIG_DIR / "data_source.json"

ENV_LIVE_DB = "POS_LIVE_DB"          # منفذ التجاوز الوحيد للمسار
ENV_ALLOW_WRITE = "POS_LIVE_WRITE"   # 1 = السماح بالكتابة (مع approved=True)
ENV_STRICT = "POS_LIVE_STRICT"       # 1 = ارفع الاستثناء عند التحميل أيضاً

DEFAULT_LIVE_DB = r"G:\ai\Elnagar POS\pos_data.db"

# ── التعريف الرسمي للمديونية (من كود التطبيق الحي app.py 1655/1712) ──
OFFICIAL_DEBT_SQL = (
    "SELECT COUNT(*) AS debt_clients_count, "
    "IFNULL(SUM(balance), 0) AS total_receivables "
    "FROM clients WHERE balance > 0"
)

# ── مصادر قديمة معروفة بالاسم + سبب مُقنَّص بالقياس ──
KNOWN_LEGACY: Tuple[Tuple[str, str], ...] = (
    (
        r"G:\ai\Naggar Print POS Agent\pos_data.db",
        "نسخة مساحة العمل المتجمدة: 52 عميلاً/50 طلباً، أقصى طلب #323، أقصى تاريخ 2026-08-31، مجموع الأرصدة = 0.0 (صفر كاذب)",
    ),
    (
        r"G:\ai\Naggar Print POS Agent\_sandbox_pos_writer\pos_data.db",
        "نسخة الساندبوكس (اختبار كتابة) — ليست بيانات حية",
    ),
    (
        r"G:\ai\Elnagar POS\pos_data_merge_backup.db",
        "نسخة احتياطية قديمة قبل دمج المنتجات المكرّرة",
    ),
)

# علامات مجلدات أرشيف/نسخ احتياطي (مقارنة على المسار الصغير)
LEGACY_DIR_MARKERS: Tuple[str, ...] = (
    "\\backup\\",
    "\\backups\\",
    r"\_quarantine_unused",
    r"\_archive_scripts",
    r"\backup_code_before_fix",
)

# علامات أسماء ملفات نسخ قديمة
LEGACY_NAME_MARKERS: Tuple[str, ...] = (
    "pos_data.db.",
    "pos_data_backup",
    "pos_data_merge_backup",
    "pos_data_20",
    ".bak-",
)


class LegacySourceRefused(RuntimeError):
    """يُرفع عند أي محاولة قراءة من مصدر SQLite قديم/غير معتمد."""


class LiveWriteRefused(RuntimeError):
    """يُرفع عند أي محاولة كتابة على القاعدة الحية بدون تصريح صريح."""


_LAST_VIOLATION: Optional[Dict[str, str]] = None


def _setup_utf8() -> None:
    """يجعل أي طباعة عربية على stdout/stderr آمنة (كونسول ويندوز cp1252 افتراضياً)."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except Exception:
            pass


_setup_utf8()


# ─────────────────────────────────────────────────────────────── أدوات داخلية
def warn(msg: str) -> None:
    """تحذير بصوت عالٍ على stderr — لا يُسكَت أبداً."""
    print(msg, file=sys.stderr, flush=True)


def load_config() -> Dict[str, Any]:
    """الإعداد المركزي من config/data_source.json (فارغ عند الفشل — بلا سقوط)."""
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _norm(p: Any) -> str:
    """تطبيع المسار للمقارنة (مطلق، بلا شرطة أخيرة، بحروف صغيرة)."""
    try:
        return str(Path(p).resolve()).lower().rstrip("\\/")
    except Exception:
        return str(p).lower().rstrip("\\/")


def official_path() -> Path:
    """المسار الرسمي الحي بحسب الإعداد المركزي، ثم متغير التجاوز `POS_LIVE_DB`."""
    cfg = load_config()
    raw = os.environ.get(ENV_LIVE_DB) or cfg.get("live_db") or DEFAULT_LIVE_DB
    return Path(str(raw))


def classify(path: Any) -> Tuple[str, str]:
    """تصنيف أي مسار: ('official' | 'legacy' | 'other', السبب)."""
    if path is None:
        path = official_path()
    p = _norm(path)
    off = _norm(official_path())

    for known, reason in KNOWN_LEGACY:
        if p == _norm(known):
            return "legacy", reason

    low = p
    for marker in LEGACY_DIR_MARKERS:
        if marker in low:
            return "legacy", f"مجلد أرشيف/نسخ احتياطي ({marker.strip(chr(92))})"

    name = Path(str(path)).name.lower()
    for marker in LEGACY_NAME_MARKERS:
        if marker in name:
            return "legacy", f"اسم ملف نسخة قديمة ({marker})"

    if p == off:
        return "official", "المصدر الرسمي الحي (قاعدة تطبيق Elnagar POS الشغّال)"

    if name == "pos_data.db":
        return "legacy", "نسخة pos_data.db غير المسار الرسمي — مصدر قديم مرفوض"

    suffix = Path(str(path)).suffix.lower()
    if suffix in (".db", ".sqlite", ".sqlite3"):
        return "other", "قاعدة أخرى غير قاعدة النظام الحي"
    return "other", "ليس مصدر النظام الحي"


def official_reference() -> Path:
    """المسار الرسمي المرجعي **للعرض في رسائل الرفض/التوجيه** — لا يُعرض أبداً مسار قديم.

    ليه مش `official_path()`؟ لأن `official_path()` تحترم متغير التجاوز `POS_LIVE_DB`،
    فلو أشار المتجاوز لمسار قديم (سيناريو الاختبار القسري) كان الرفض يطبع المسار المرفوض
    نفسه في سطر «المصدر الرسمي» — لخبطة عكسية مقصودة إصلاحها. هنا نُسقط أي إشارة قديمة
    ونرجع للمصدر الرسمي الافتراضي الحي.
    """
    p = official_path()
    verdict, _ = classify(p)
    return Path(DEFAULT_LIVE_DB) if verdict == "legacy" else p


def _refusal_message(path: Any, reason: str) -> str:
    return (
        "⛔ مرفوض: محاولة قراءة من مصدر SQLite قديم/ميت\n"
        f"   المسار المطلوب : {path}\n"
        f"   السبب          : {reason}\n"
        f"   المصدر الرسمي  : {official_reference()}\n"
        "   لا تُستخدم النسخ القديمة في أي استعلام حي "
        "(التفاصيل: Vision-Lab/config/data_binding_report.md)"
    )


def _record_violation(path: Any, reason: str) -> None:
    global _LAST_VIOLATION
    _LAST_VIOLATION = {"path": str(path), "reason": reason}


def last_violation() -> Optional[Dict[str, str]]:
    """آخر مخالفة مسجَّلة (للتقارير/الاختبارات)."""
    return dict(_LAST_VIOLATION) if _LAST_VIOLATION else None


# ─────────────────────────────────────────────────────────────────── المسار
def db_path(strict: bool = False) -> Path:
    """المسار الرسمي المُعتمد للقراءة الحية.

    لا يرفع استثناءً افتراضياً (كي لا يسقط الوكيل لحظة التحميل)، لكنه يسجّل
    المخالفة ويحذّر بصوت عالٍ — والرفض الفعلي يقع لحظة الاتصال.
    ``strict=True`` (أو POS_LIVE_STRICT=1) يرفع فوراً.
    """
    p = official_path()
    verdict, reason = classify(p)
    if verdict == "legacy":
        _record_violation(p, reason)
        warn(
            f"⛔ تحذير: المصدر المطلوب مصنَّف «قديم/ميت»: {p}\n"
            f"   السبب: {reason}\n"
            f"   المصدر الرسمي الحي هو: {DEFAULT_LIVE_DB}\n"
            "   سيُرفض أي اتصال قراءة بهذا المسار."
        )
        if strict or os.environ.get(ENV_STRICT) == "1":
            raise LegacySourceRefused(_refusal_message(p, reason))
    return p


def assert_official(path: Any = None) -> Path:
    """يرفع LegacySourceRefused إلا إذا كان المسار هو الرسمي الحي."""
    target = Path(path) if path is not None else db_path()
    verdict, reason = classify(target)
    if verdict == "legacy":
        _record_violation(target, reason)
        raise LegacySourceRefused(_refusal_message(target, reason))
    if _norm(target) != _norm(official_path()):
        _record_violation(target, "مسار غير معتمد للقراءة الحية")
        raise LegacySourceRefused(
            f"⛔ مرفوض: مسار غير معتمد للقراءة الحية\n"
            f"   المطلوب : {target}\n"
            f"   المعتمد : {official_reference()}"
        )
    return target


def refuse_if_legacy(path: Any) -> None:
    """رفض صريح لأي مسار مصنَّف قديم (يُستخدم كحاجز قبل أي اتصال)."""
    verdict, reason = classify(path)
    if verdict == "legacy":
        _record_violation(path, reason)
        raise LegacySourceRefused(_refusal_message(path, reason))


# ───────────────────────────────────────────────────────────────── الاتصال
def open_readonly(path: Any = None) -> sqlite3.Connection:
    """اتصال قراءة فقط (mode=ro) بالمصدر الرسمي الحي — ومع رفض صريح لأي مسار قديم."""
    target = assert_official(path)
    conn = sqlite3.connect(f"file:{Path(target).as_posix()}?mode=ro", uri=True, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def forensic_open_readonly(path: Any) -> sqlite3.Connection:
    """اتصال تشخيصي **غير محكوم** — للمقارنة الإثباتية فقط (مثال: إثبات أن القديم = صفر).

    ممنوع استخدامه في أي أداة استعلام للوكلاء. اسمه صريح كي لا يُستدعى بالخطأ.
    """
    conn = sqlite3.connect(f"file:{Path(path).as_posix()}?mode=ro", uri=True, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def open_readwrite(purpose: str = "", approved: bool = False, path: Any = None) -> sqlite3.Connection:
    """اتصال كتابة على القاعدة الحية — مرفوض افتراضياً.

    يلزم POS_LIVE_WRITE=1 في البيئة **و** approved=True، مع ذكر الغرض.
    """
    if os.environ.get(ENV_ALLOW_WRITE) != "1" or not approved:
        raise LiveWriteRefused(
            "⛔ مرفوض: الكتابة على القاعدة الحية ممنوعة من طبقة الربط المركزية افتراضياً.\n"
            f"   الغرض المذكور : {purpose or '(غير مذكور)'}\n"
            "   للتفعيل بعد اعتماد المالك الصريح: POS_LIVE_WRITE=1 مع approved=True."
        )
    target = assert_official(path)
    conn = sqlite3.connect(str(target), timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


# ─────────────────────────────────────────────────────────────── استعلامات
def query(sql: str, params: Any = (), path: Any = None) -> List[Dict[str, Any]]:
    """استعلام قراءة محكوم بالمصدر الرسمي الحي — يُعيد قائمة صفوف كقواميس."""
    conn = open_readonly(path)
    try:
        return [dict(r) for r in conn.execute(sql, tuple(params or ())).fetchall()]
    finally:
        conn.close()


def query_one(sql: str, params: Any = (), path: Any = None) -> Dict[str, Any]:
    rows = query(sql, params, path=path)
    return rows[0] if rows else {}


def debt_totals(path: Any = None) -> Dict[str, Any]:
    """إجمالي المديونيات الحية بالتعريف الرسمي (balance > 0) من المصدر الحي."""
    row = query_one(OFFICIAL_DEBT_SQL, path=path)
    return {
        "debt_clients_count": int(row.get("debt_clients_count") or 0),
        "total_receivables": float(row.get("total_receivables") or 0.0),
        "sql": OFFICIAL_DEBT_SQL,
        "source": str(path or db_path()),
        "verdict": classify(path or db_path())[0],
    }


def mask_phone_like(value: Any) -> str:
    """يحجب أي نص يشبه رقم هاتف (قاعدة المشروع: لا أرقام هواتف في أي رد).

    بعض صفوف clients.name تحتوي الرقم نفسه بدل الاسم — تُحجب بدل طباعتها.
    """
    s = str(value or "")
    digits = sum(1 for ch in s if ch.isdigit())
    if digits >= 8 and re.fullmatch(r"[\s\+\d\-\(\)\.]{8,}", s.strip() or " "):
        return "[محجوب — يشبه رقم هاتف]"
    return s


def debtors(limit: int = 10, path: Any = None) -> List[Dict[str, Any]]:
    """أعلى العملاء مديونية (بلا أرقام هواتف) من المصدر الحي."""
    rows = query(
        "SELECT id, name, type, balance FROM clients WHERE balance > 0 "
        "ORDER BY balance DESC LIMIT ?",
        (int(limit),),
        path=path,
    )
    for r in rows:
        r["name"] = mask_phone_like(r.get("name"))
    return rows


def describe() -> Dict[str, Any]:
    """وصف الحالة للتقارير والاختبارات (بلا أسرار)."""
    configured = official_path()
    verdict, reason = classify(configured)
    cfg = load_config()
    return {
        "config_file": str(CONFIG_FILE),
        "engine": cfg.get("engine", "sqlite"),
        "live_db": str(configured),
        "verdict": verdict,
        "verdict_reason": reason,
        "default_live_db": DEFAULT_LIVE_DB,
        "env_override": {ENV_LIVE_DB: os.environ.get(ENV_LIVE_DB, "")},
        "write_allowed": os.environ.get(ENV_ALLOW_WRITE) == "1",
        "known_legacy": [k for k, _ in KNOWN_LEGACY],
        "last_violation": last_violation(),
    }


# ───────────────────────────────────────── متوافقات مع الاستدعاءات القديمة
def _ro_conn() -> sqlite3.Connection:
    """اسم متوافق مع الوكلاء القدامى (كانوا يعرّفونه محلياً في كل ملف)."""
    return open_readonly()


if __name__ == "__main__":
    info = describe()
    for k, v in info.items():
        print(f"{k:>16} : {v}")
    print("\n— إجمالي المديونيات الحية —")
    try:
        totals = debt_totals()
        print(f"  المصدر                : {totals['source']}")
        print(f"  عدد العملاء المدينين  : {totals['debt_clients_count']}")
        print(f"  إجمالي المديونيات     : {totals['total_receivables']} جنيه")
        print(f"  الاستعلام             : {totals['sql']}")
    except LegacySourceRefused as exc:
        warn(str(exc))
        raise SystemExit(2)