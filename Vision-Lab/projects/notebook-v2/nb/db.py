# -*- coding: utf-8 -*-
"""طبقة PostgreSQL الموحدة (Supabase + pgvector).

- كل الاستعلامات parameterized (%s) — لا تركيب نصوص أبدًا.
- **إعادة استخدام الاتصال لكل خيط** (`threading.local`): الـFlask شغّال
  `threaded=True`، وفتح اتصال لكل استعلام كان بيكلّف **~0.66 ثانية**
  (TLS + مصافحة المصادقة مع الـpooler). القياس بيقول `stats()` = 10
  استعلامات × 0.66s = 6.6s، والمصافحة هي التكلفة مش الاستعلام.
  بنعيد الاستخدام داخل نفس الخيط، وبنفحص الاتصال قبل التسليم فلو مات
  (Supabase بيقطع الخاملة) بنفتح غيره ونعيد المحاولة مرة.
- **أمان الخيوط إلزامي:** `threading.local()` — اتصال واحد مشترك بين
  خيوط متوازية = استعلامات متشابكة = كارثة.
- timestamptz في كل الأوقات — مقارنات الـHA بوقت السيرفر.
- أي كتابة بتلغي كاش اللوحة — قراءة قديمة بعد كتابة = بيانات غلط.
"""
from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

import psycopg2
import psycopg2.extras

from nb import cache, config

# اتصال لكل خيط (Flask threaded=True) — إلزامي للسلامة
_local = threading.local()


class DBError(RuntimeError):
    pass


def connect():
    """اتصال **جديد** دائمًا (توقيع مجمّد — استخدمه في التشخيص/المُهاجرة).

    الكود العادي بيستخدم `conn()` اللي بتعيد استخدام اتصال الخيط.
    """
    if not config.DB_DSN:
        raise DBError("لا يوجد DSN — اضبط NB2_DB_URL أو POOLER_URL في .env الجذر")
    kw: Dict[str, Any] = {"connect_timeout": 15, "application_name": f"nb2-{config.NODE_ID}"}
    host = config.DB_DSN_HOST
    if host and "localhost" not in host and "127.0.0.1" not in host:
        kw["sslmode"] = "require"
    return psycopg2.connect(config.DB_DSN, **kw)


def conn():
    """اتصال الخيط الحالي — يعيد استخدامه، ويفتح غيره لو مات/اتقفل."""
    c = getattr(_local, "conn", None)
    if c is not None:
        try:
            # closed == 0 يعني مفتوح؛ وأي حالة معاملة غير سليمة = نتخلص منه
            if getattr(c, "closed", 1) == 0 and \
               c.info.transaction_status != psycopg2.extensions.TRANSACTION_STATUS_UNKNOWN:
                return c
        except Exception:
            pass
        close_conn()
    _local.conn = connect()
    return _local.conn


def close_conn() -> None:
    """إغلاق اتصال الخيط الحالي (للاختبارات والإيقاف المرتّب)."""
    c = getattr(_local, "conn", None)
    _local.conn = None
    if c is not None:
        try:
            c.close()
        except Exception:
            pass


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _is_dead(exc: BaseException) -> bool:
    """هل الاستثناء معناه «الاتصال مات» (نعيد المحاولة) ولا «استعلام غلط»؟"""
    if isinstance(exc, (psycopg2.InterfaceError, psycopg2.OperationalError)):
        return True
    if isinstance(exc, psycopg2.DatabaseError):
        msg = str(exc).lower()
        return any(k in msg for k in ("closed", "terminat", "ssl", "broken pipe",
                                     "connection reset", "server closed",
                                     "no connection", "connection already"))
    return False


def _run(sql: str, params: Optional[Sequence[Any]], *, fetch: str, commit: bool):
    """ينفّذ جملة على اتصال الخيط، ويعيد المحاولة مرة لو الاتصال مات.

    إعادة المحاولة آمنة: الفشل اللي بيستدعيها (اتصال مقطوع) مابيسيبش أثر.
    """
    attempts = max(0, int(config.RECONNECT_RETRIES)) + 1
    last: Optional[BaseException] = None
    for attempt in range(attempts):
        c = conn()
        try:
            cur = c.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            try:
                cur.execute(sql, params or ())
                if fetch == "all":
                    out: Any = [dict(r) for r in cur.fetchall()]
                elif fetch == "one":
                    row = cur.fetchone()
                    out = dict(row) if row else None
                else:
                    out = cur.rowcount
                if commit:
                    c.commit()
                return out
            finally:
                cur.close()
        except Exception as exc:
            try:
                c.rollback()
            except Exception:
                pass
            if _is_dead(exc):
                close_conn()                    # نرمي الميت ونحاول باتصال جديد
                last = exc
                if attempt + 1 < attempts:
                    continue
            raise
    if last:
        raise last
    raise DBError("استعلام غير متوقع")


def q(sql: str, params: Optional[Sequence[Any]] = None, one: bool = False):
    """تنفيذ ويعيد الصفوف: SELECT ← قائمة dicts (أو dict واحد مع one=True).

    مهم: `q()` كمان بتنفّذ جمل `INSERT/UPDATE ... RETURNING` (زي إيجار القيادة
    وحجز `cron_runs` وحفظ التقارير)، فبتعمل **commit** قبل الإرجاع. من غيرها
    كان psycopg2 يتراجع عند الإغلاق (autocommit=False) فيضيع الأثر صامتًا
    — وهو ما كان بيخلي جدول `leader_lease` فاضي والعقدتين تظن نفسها قائدة.
    """
    return _run(sql, params, fetch=("one" if one else "all"), commit=True)


def x(sql: str, params: Optional[Sequence[Any]] = None) -> int:
    """INSERT/UPDATE/DELETE ← rowcount."""
    return _run(sql, params, fetch="none", commit=True)


def scalar(sql: str, params: Optional[Sequence[Any]] = None) -> Any:
    row = q(sql, params, one=True)
    if not row:
        return None
    return next(iter(row.values()))


def _invalidate_dashboard() -> int:
    """أي كتابة بتلغي كاش اللوحة — قراءة قديمة بعد كتابة = بيانات غلط."""
    return cache.invalidate("dash:")


# ------------------------------------------------------------------ settings
def get_setting(key: str, default: Any = None) -> Any:
    row = q("SELECT value FROM settings WHERE key = %s", (key,), one=True)
    return row["value"] if row else default


def set_setting(key: str, value: Any) -> None:
    x("""INSERT INTO settings(key, value, updated_at) VALUES (%s, %s::jsonb, now())
         ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = now()""",
      (key, psycopg2.extras.Json(value)))
    _invalidate_dashboard()


# ------------------------------------------------------------------ captures
def add_capture(a: Dict[str, Any]) -> int:
    """إدراج تحليل الـAI Router كصف captures — ويرجع المعرف."""
    sql = """INSERT INTO captures
             (kind, title, body, category, priority, status, due_at, remind_at,
              remind_every, source, tags, confidence, routed_by, needs_clarification, question, meta)
             VALUES (%s,%s,%s,%s,%s,'open',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
             RETURNING id"""
    row = q(sql, (
        a.get("kind"), a.get("title") or "", a.get("body") or "",
        a.get("category"), a.get("priority") or "normal",
        a.get("due_at"), a.get("remind_at"), a.get("remind_every") or "none",
        a.get("source") or "api", a.get("tags") or [], float(a.get("confidence") or 0),
        a.get("routed_by") or "rules", bool(a.get("needs_clarification")),
        a.get("question"), psycopg2.extras.Json(a.get("meta") or {}),
    ), one=True)
    cid = row["id"]
    x("""INSERT INTO capture_events(capture_id, type, detail)
         VALUES (%s, 'created', %s)""",
      (cid, f"kind={a.get('kind')} source={a.get('source')} routed_by={a.get('routed_by')}"))
    _invalidate_dashboard()
    return cid


def list_captures(status: Optional[str] = "open", kind: Optional[str] = None,
                  search: Optional[str] = None, limit: int = 200) -> List[Dict[str, Any]]:
    sql = "SELECT * FROM captures WHERE 1=1"
    params: List[Any] = []
    if status:
        sql += " AND status = %s"
        params.append(status)
    if kind:
        sql += " AND kind = %s"
        params.append(kind)
    if search:
        sql += " AND (title ILIKE %s OR body ILIKE %s)"
        params += [f"%{search}%", f"%{search}%"]
    sql += " ORDER BY COALESCE(due_at, created_at) ASC, id DESC LIMIT %s"
    params.append(int(limit))
    return q(sql, params)


def due_reminders() -> List[Dict[str, Any]]:
    return q("""SELECT * FROM captures
                WHERE status='open' AND remind_at IS NOT NULL AND remind_at <= now()
                ORDER BY remind_at ASC LIMIT 20""")


def overdue_captures() -> List[Dict[str, Any]]:
    return q("""SELECT * FROM captures
                WHERE status='open' AND due_at IS NOT NULL AND due_at < now()
                ORDER BY due_at ASC LIMIT 20""")


def stats() -> Dict[str, int]:
    """الأرقام العشرة للوحة القيادة — **استعلام واحد** على اتصال واحد.

    قبل: 10 نداءات `scalar()` مستقلة، كل واحد بيفتح اتصال جديد بالأصل
    (~0.66s مصافحة TLS/auth مع الـpooler) = **6.6 ثانية** مقيسة.
    بعد: جملة واحدة بترجع الـ10 أعمدة معًا → **مصافحة واحدة**.

    دقة الأرقام محفوظة بالحرف: نفس شروط كل عدّاد زي ما كانت (بما فيها
    أن `idea`/`program_idea` بتستثني `archived` فقط، و`overdue` بتقارن
    `due_at < now()` بلا شرط `IS NOT NULL` — في SQL `NULL < now()` = NULL
    أي غير محسوب، فالناتج مطابق تمامًا للسلوك السابق).

    الأعمدة العشرة **إلزامية** وبنفس الأسماء — فيجن بيقراها في الويب.
    """
    today = now_local_date()
    row = q("""
        SELECT
          (SELECT COUNT(*) FROM captures  WHERE status='open')                                  AS open,
          (SELECT COUNT(*) FROM captures  WHERE status='done')                                  AS done,
          (SELECT COUNT(*) FROM captures  WHERE status='open' AND kind='task')                  AS tasks,
          (SELECT COUNT(*) FROM captures  WHERE kind IN ('idea','program_idea')
                                             AND status!='archived')                            AS ideas,
          (SELECT COUNT(*) FROM captures  WHERE status='open' AND due_at < now())               AS overdue,
          (SELECT COUNT(*) FROM captures  WHERE status='open' AND due_at::date = %s)            AS due_today,
          (SELECT COUNT(*) FROM captures  WHERE status='open' AND needs_clarification)          AS need_help,
          (SELECT COUNT(*) FROM projects  WHERE status='active')                                AS projects_active,
          (SELECT COUNT(*) FROM ws_jobs   WHERE status NOT IN ('delivered','cancelled'))        AS ws_open_jobs,
          (SELECT COUNT(*) FROM vault_prompts)                                                  AS vault_prompts
    """, (today,), one=True) or {}
    keys = ("open", "done", "tasks", "ideas", "overdue", "due_today",
            "need_help", "projects_active", "ws_open_jobs", "vault_prompts")
    return {k: int(row.get(k) or 0) for k in keys}


def now_local_date() -> str:
    """تاريخ اليوم بتوقيت القاهرة المحلي (السيرفر UTC — نحوّل قبل المقارنة)."""
    return utcnow().astimezone().strftime("%Y-%m-%d")


def set_capture_status(cid: int, status: str) -> bool:
    done_at = "now()" if status == "done" else "NULL"
    row = x(f"UPDATE captures SET status=%s, done_at={done_at}, updated_at=now() WHERE id=%s",
            (status, cid))
    x("INSERT INTO capture_events(capture_id, type, detail) VALUES (%s,'status',%s)", (cid, status))
    _invalidate_dashboard()          # A12: اللوحة تعكس التغيير فورًا مش بعد 45ث
    return row > 0


def snooze_capture(cid: int, minutes: int) -> bool:
    ok = x("""UPDATE captures
              SET remind_at = now() + (%s || ' minutes')::interval, updated_at=now()
              WHERE id=%s""", (minutes, cid)) > 0
    _invalidate_dashboard()
    return ok


# ============================================================ ذاكرة المحادثة
# دفتر محادثة فوفا — فيجن بيستهلكها عشان البوت يفتكر السياق (A5/A10).
# التوقيعات وشكل الإرجاع مجمّدة بالعقد.
def log_message(chat_id: int, role: str, content: str,
                meta: Optional[Dict[str, Any]] = None) -> int:
    """يسجّل رسالة في `conversations` ويرجع معرفها (`id`)."""
    row = q("""INSERT INTO conversations(chat_id, role, content, meta)
               VALUES (%s, %s, %s, %s) RETURNING id""",
            (int(chat_id), role, content or "",
             psycopg2.extras.Json(meta or {})), one=True)
    return int(row["id"]) if row else 0


def recent_messages(chat_id: int, limit: int = 12) -> List[Dict[str, Any]]:
    """آخر `limit` رسالة لـ`chat_id` — **الأقدم الأول** (newest last).

    الترتيب ده مقصود: جاهز مباشرة للتحويل لـ`messages[]` في نداء الموديل.
    بناخد آخر N بـ`ORDER BY id DESC LIMIT` (بيستخدم الفهرس) وبعدين نقلبهم
    في بايثون — أسرع من إعادة ترتيب الجدول كله.
    """
    rows = q("""SELECT id, chat_id, role, content, meta, created_at
                FROM conversations WHERE chat_id = %s
                ORDER BY id DESC LIMIT %s""",
             (int(chat_id), int(limit)))
    rows.reverse()
    return rows


def count_messages(chat_id: int) -> int:
    """عدد رسائل المحادثة الواحدة."""
    return int(scalar("SELECT COUNT(*) FROM conversations WHERE chat_id = %s",
                      (int(chat_id),)) or 0)


def clear_messages(chat_id: int) -> int:
    """مسح محادثة (لو المالك طلب نسيان السياق) — بيرجع عدد المحذوف."""
    return x("DELETE FROM conversations WHERE chat_id = %s", (int(chat_id),))


# ============================================================ لوحة القيادة
def _dashboard_build(status: Optional[str] = None, kind: Optional[str] = None,
                     search: Optional[str] = None, limit: int = 150) -> Dict[str, Any]:
    """يبني كل مفاتيح اللوحة — `web.py` بينده ده مباشرة عبر `dashboard()`.

    مفاتيح الخدمات الاختيارية (`retail_digest`, `agent_reports`, `ws_stats`)
    مش في قايمة الـ9 المضمونة، فبتتحمّل هنا بتسامح: لو خدمة وقعت اللوحة
    تفضل قايمة ببياناتها الناقصة بدل ما الصفحة كلها ترجع 500.
    """
    from nb import retail, workshop          # استيراد داخلي: يمنع دورة استيراد

    stats_v = stats()
    captures = list_captures(status=status if status != "all" else None,
                             kind=kind, search=search, limit=limit)
    due = due_reminders()
    late = overdue_captures()
    need_help = q("""SELECT * FROM captures
                     WHERE status='open' AND needs_clarification
                     ORDER BY COALESCE(due_at, created_at) ASC, id DESC LIMIT 15""")
    projects = q("""SELECT *, (last_activity_at < now() - make_interval(days => stagnant_after_days)) AS stagnant
                    FROM projects WHERE status='active' ORDER BY stagnant DESC, id DESC LIMIT 10""")
    radar = [p for p in projects if p.get("stagnant")]
    events = q("SELECT capture_id, at, type, detail FROM capture_events ORDER BY id DESC LIMIT 15")

    out: Dict[str, Any] = {
        "stats": stats_v, "captures": captures, "due": due, "late": late,
        "need_help": need_help, "projects": projects, "radar": radar,
        "events": events, "ws_stats": {},
    }
    try:
        out["retail_digest"] = retail.digest()
    except Exception as exc:
        out["retail_digest"] = None
        out["retail_error"] = type(exc).__name__
    try:
        out["agent_reports"] = retail.latest_agent_reports(6)
    except Exception:
        out["agent_reports"] = []
    try:
        out["ws_stats"] = workshop.stats()
    except Exception as exc:
        out["ws_stats"] = {}
        out["ws_error"] = type(exc).__name__
    return out


def dashboard(ttl: int = 45) -> Dict[str, Any]:
    """لوحة القيادة كاملة كمفتاح كاش واحد — بدل ~10 استعلامات لكل زيارة.

    المفاتيح **المضمونة بالعقد**: stats, captures, due, late, need_help,
    projects, radar, events, ws_stats.

    `ttl <= 0` أو `NB2_CACHE=0` = تنفيذ مباشر بلا كاش (عشان القياس البارد).
    """
    use = int(ttl) if ttl is not None else config.DASHBOARD_TTL_SECONDS
    if not config.CACHE_ENABLED or use <= 0:
        return _dashboard_build()
    return cache.get_or_set(f"dash:{use}", use, _dashboard_build)


def dashboard_stats() -> Dict[str, Any]:
    """تشخيص: حالة الكاش + زمن بناء اللوحة بارد/دافئ."""
    import time as _t
    t0 = _t.perf_counter()
    cold = _dashboard_build()
    cold_ms = (_t.perf_counter() - t0) * 1000
    t1 = _t.perf_counter()
    warm = dashboard(ttl=config.DASHBOARD_TTL_SECONDS)
    warm_ms = (_t.perf_counter() - t1) * 1000
    return {"cache": cache.stats(), "cold_ms": round(cold_ms, 1),
            "warm_ms": round(warm_ms, 1),
            "keys": sorted(cold.keys()), "warm_keys_match": sorted(warm.keys()) == sorted(cold.keys())}
