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
# كل أعمدة التاريخ/الوقت في المخطط العام (28 عمودًا) — بتستخدمها `_rehydrate`
# عشان ترجّع `datetime` مكان النص بعد دمج اللوحة في JSONB واحد.
_TS_FIELDS = frozenset({
    "acked_at", "acquired_at", "added_at", "applied_at", "at", "captured_at",
    "closed_at", "created_at", "date", "delivered_at", "discovered_at",
    "done_at", "due_at", "due_date", "ends_at", "expires_at", "last_activity_at",
    "last_check_at", "last_seen", "last_sync", "last_used_at", "received_at",
    "remind_at", "run_date", "sent_at", "started_at", "updated_at", "used_at",
})
# أعمدة من نوع `date` (مش timestamptz) — ترجع `date` مش `datetime`
_DATE_FIELDS = frozenset({"due_date", "run_date", "date"})


def _rehydrate(obj: Any) -> Any:
    """يرجّع `datetime` مكان النص للتواريخ المعروفة — في أي شكل متداخل.

    ليه ده إلزامي: استعلام اللوحة المدموج بيرجّع `timestamptz` جوّه JSONB
    **كنص ISO**. من غير الخطوة دي، شكل الإرجاع يتغيّر من `datetime` لـ`str`
    والقوالب (`{{ n.due_at }}`) تعرض صيغة مختلفة — يعني «مقايضة» مش تحسين.
    بعد `_rehydrate` الأنواع **مطابقة للأصل بالحرف**: `datetime` زي الأول،
    فمفيش قالب يتكسر ومفيش مقايضة أصلًا.

    ملاحظة أنواع: عمودان في المخطط من نوع `date` مش `timestamptz`
    (`due_date`, `run_date`) — بنرجّعهم `date` مش `datetime` عشان النوع ما
    يتغيّرش لو ظهروا في أي استعلام مستقبلي. (مفيش تقاطع أسماء: التحقق
    طلع `ambiguous_name_columns = []`، فمحكومين بجدولهم.)

    كمان بنشيل أي مفتاح مبدوء بـ`__` (زي `__o` اللي بيحكم ترتيب `jsonb_agg`).
    """
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if isinstance(k, str) and k.startswith("__"):
                continue
            if k in _TS_FIELDS and isinstance(v, str):
                out[k] = date.fromisoformat(v) if k in _DATE_FIELDS \
                    else datetime.fromisoformat(v)
            else:
                out[k] = _rehydrate(v)
        return out
    if isinstance(obj, list):
        return [_rehydrate(v) for v in obj]
    return obj


# استعلام اللوحة المدموج: **رحلة شبكة واحدة** بدل 9.
# كل جزء محافظ على نفس ترتيب الاستعلام الأصلي بالحرف، والترتيب مضمون صراحة
# بـ`jsonb_agg(... ORDER BY t.__o)` — مش معتمد على «الترتيب بيحصل بالغلط».
_DASH_AGG = """COALESCE(jsonb_agg(to_jsonb(t) - '__o' ORDER BY t.__o), '[]'::jsonb)"""


def _dashboard_db_bundle(status: Optional[str], kind: Optional[str],
                         search: Optional[str], limit: int) -> Dict[str, Any]:
    """مفاتيح اللوحة الجاية من القاعدة — في **جملة واحدة**.

    6 أجزاء (stats/captures/due/late/need_help/projects/events) في رحلة
    واحدة. كل جملة كانت ~220ms شبكة، فدمجهم بينزّل البارد من ~3.2s
    لـ~0.5s. وفي حالة أي استثناء بنرجع للمسار القديم (استدعاءات منفصلة)
    عشان اللوحة ما تقعش — الأرقام الصح أهم من السرعة.
    """
    where, cparams = "WHERE 1=1", []
    if status:
        where += " AND status = %s"
        cparams.append(status)
    if kind:
        where += " AND kind = %s"
        cparams.append(kind)
    if search:
        where += " AND (title ILIKE %s OR body ILIKE %s)"
        cparams += [f"%{search}%", f"%{search}%"]
    cparams.append(int(limit))

    sql = f"""
    SELECT jsonb_build_object(
      'stats', (SELECT jsonb_build_object(
          'open',           (SELECT COUNT(*) FROM captures WHERE status='open'),
          'done',           (SELECT COUNT(*) FROM captures WHERE status='done'),
          'tasks',          (SELECT COUNT(*) FROM captures WHERE status='open' AND kind='task'),
          'ideas',          (SELECT COUNT(*) FROM captures WHERE kind IN ('idea','program_idea')
                                                              AND status!='archived'),
          'overdue',        (SELECT COUNT(*) FROM captures WHERE status='open' AND due_at < now()),
          'due_today',      (SELECT COUNT(*) FROM captures WHERE status='open' AND due_at::date = %s),
          'need_help',      (SELECT COUNT(*) FROM captures WHERE status='open' AND needs_clarification),
          'projects_active',(SELECT COUNT(*) FROM projects WHERE status='active'),
          'ws_open_jobs',   (SELECT COUNT(*) FROM ws_jobs WHERE status NOT IN ('delivered','cancelled')),
          'vault_prompts',  (SELECT COUNT(*) FROM vault_prompts))),
      'captures', (SELECT {_DASH_AGG} FROM (
          SELECT c.*, row_number() OVER (ORDER BY COALESCE(c.due_at, c.created_at) ASC, c.id DESC) AS __o
          FROM captures c {where} LIMIT %s) t),
      'due', (SELECT {_DASH_AGG} FROM (
          SELECT c.*, row_number() OVER (ORDER BY c.remind_at ASC) AS __o
          FROM captures c WHERE c.status='open' AND c.remind_at IS NOT NULL
            AND c.remind_at <= now() LIMIT 20) t),
      'late', (SELECT {_DASH_AGG} FROM (
          SELECT c.*, row_number() OVER (ORDER BY c.due_at ASC) AS __o
          FROM captures c WHERE c.status='open' AND c.due_at IS NOT NULL
            AND c.due_at < now() LIMIT 20) t),
      'need_help', (SELECT {_DASH_AGG} FROM (
          SELECT c.*, row_number() OVER (ORDER BY COALESCE(c.due_at, c.created_at) ASC, c.id DESC) AS __o
          FROM captures c WHERE c.status='open' AND c.needs_clarification LIMIT 15) t),
      'projects', (SELECT {_DASH_AGG} FROM (
          SELECT p.*, (p.last_activity_at < now() - make_interval(days => p.stagnant_after_days)) AS stagnant,
                 row_number() OVER (ORDER BY (p.last_activity_at < now() - make_interval(days => p.stagnant_after_days)) DESC NULLS LAST, p.id DESC) AS __o
          FROM projects p WHERE p.status='active' LIMIT 10) t),
      'events', (SELECT {_DASH_AGG} FROM (
          SELECT e.capture_id, e.at, e.type, e.detail,
                 row_number() OVER (ORDER BY e.id DESC) AS __o
          FROM capture_events e LIMIT 15) t)
    ) AS payload"""
    row = q(sql, [now_local_date()] + cparams, one=True)
    return _rehydrate(row["payload"]) if row and row.get("payload") else {}


def _dashboard_db_bundle_slow(status: Optional[str], kind: Optional[str],
                              search: Optional[str], limit: int) -> Dict[str, Any]:
    """المسار القديم (استدعاءات منفصلة) — احتياطي لو الدمج فشل."""
    return {
        "stats": stats(),
        "captures": list_captures(status=status if status != "all" else None,
                                  kind=kind, search=search, limit=limit),
        "due": due_reminders(),
        "late": overdue_captures(),
        "need_help": q("""SELECT * FROM captures
                          WHERE status='open' AND needs_clarification
                          ORDER BY COALESCE(due_at, created_at) ASC, id DESC LIMIT 15"""),
        "projects": q("""SELECT *, (last_activity_at < now() - make_interval(days => stagnant_after_days)) AS stagnant
                         FROM projects WHERE status='active' ORDER BY stagnant DESC, id DESC LIMIT 10"""),
        "events": q("SELECT capture_id, at, type, detail FROM capture_events ORDER BY id DESC LIMIT 15"),
    }


def _dashboard_build(status: Optional[str] = None, kind: Optional[str] = None,
                     search: Optional[str] = None, limit: int = 150) -> Dict[str, Any]:
    """يبني كل مفاتيح اللوحة — `web.py` بينده ده مباشرة عبر `dashboard()`.

    مفاتيح الخدمات الاختيارية (`retail_digest`, `agent_reports`, `ws_stats`)
    مش في قايمة الـ9 المضمونة، فبتتحمّل هنا بتسامح: لو خدمة وقعت اللوحة
    تفضل قايمة ببياناتها الناقصة بدل ما الصفحة كلها ترجع 500.
    """
    from nb import retail, workshop          # استيراد داخلي: يمنع دورة استيراد

    try:
        bundle = _dashboard_db_bundle(status, kind, search, limit)
        if not bundle or "stats" not in bundle:
            raise DBError("دفعة اللوحة رجعت فاضية")
    except Exception:
        bundle = _dashboard_db_bundle_slow(status, kind, search, limit)

    stats_v = bundle.get("stats") or {}
    captures = bundle.get("captures") or []
    due = bundle.get("due") or []
    late = bundle.get("late") or []
    need_help = bundle.get("need_help") or []
    projects = bundle.get("projects") or []
    radar = [p for p in projects if p.get("stagnant")]
    events = bundle.get("events") or []

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
