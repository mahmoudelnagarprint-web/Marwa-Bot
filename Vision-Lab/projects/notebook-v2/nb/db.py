# -*- coding: utf-8 -*-
"""طبقة PostgreSQL الموحدة (Supabase + pgvector).

- كل الاستعلامات parameterized (%s) — لا تركيب نصوص أبدًا.
- اتصال لكل عملية (بسيط ومتين لعقدتين على Supavisor pooler).
- timestamptz في كل الأوقات — مقارنات الـHA بوقت السيرفر.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

import psycopg2
import psycopg2.extras

from nb import config


class DBError(RuntimeError):
    pass


def connect():
    if not config.DB_DSN:
        raise DBError("لا يوجد DSN — اضبط NB2_DB_URL أو POOLER_URL في .env الجذر")
    kw: Dict[str, Any] = {"connect_timeout": 15, "application_name": f"nb2-{config.NODE_ID}"}
    host = config.DB_DSN_HOST
    if host and "localhost" not in host and "127.0.0.1" not in host:
        kw["sslmode"] = "require"
    return psycopg2.connect(config.DB_DSN, **kw)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def q(sql: str, params: Optional[Sequence[Any]] = None, one: bool = False):
    """SELECT ← قائمة dicts (أو dict واحد مع one=True، أو None)."""
    conn = connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params or ())
            rows = cur.fetchall()
        if one:
            return dict(rows[0]) if rows else None
        return [dict(r) for r in rows]
    finally:
        conn.close()


def x(sql: str, params: Optional[Sequence[Any]] = None) -> int:
    """INSERT/UPDATE/DELETE ← rowcount."""
    conn = connect()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            conn.commit()
            return cur.rowcount
    finally:
        conn.close()


def scalar(sql: str, params: Optional[Sequence[Any]] = None) -> Any:
    row = q(sql, params, one=True)
    if not row:
        return None
    return next(iter(row.values()))


# ------------------------------------------------------------------ settings
def get_setting(key: str, default: Any = None) -> Any:
    row = q("SELECT value FROM settings WHERE key = %s", (key,), one=True)
    return row["value"] if row else default


def set_setting(key: str, value: Any) -> None:
    x("""INSERT INTO settings(key, value, updated_at) VALUES (%s, %s::jsonb, now())
         ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = now()""",
      (key, psycopg2.extras.Json(value)))


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
    today = now_local_date()
    return {
        "open": scalar("SELECT COUNT(*) FROM captures WHERE status='open'") or 0,
        "done": scalar("SELECT COUNT(*) FROM captures WHERE status='done'") or 0,
        "tasks": scalar("SELECT COUNT(*) FROM captures WHERE status='open' AND kind='task'") or 0,
        "ideas": scalar("SELECT COUNT(*) FROM captures WHERE kind IN ('idea','program_idea') AND status!='archived'") or 0,
        "overdue": scalar("SELECT COUNT(*) FROM captures WHERE status='open' AND due_at < now()") or 0,
        "due_today": scalar("SELECT COUNT(*) FROM captures WHERE status='open' AND due_at::date = %s", (today,)) or 0,
        "need_help": scalar("SELECT COUNT(*) FROM captures WHERE status='open' AND needs_clarification") or 0,
        "projects_active": scalar("SELECT COUNT(*) FROM projects WHERE status='active'") or 0,
        "ws_open_jobs": scalar("SELECT COUNT(*) FROM ws_jobs WHERE status NOT IN ('delivered','cancelled')") or 0,
        "vault_prompts": scalar("SELECT COUNT(*) FROM vault_prompts") or 0,
    }


def now_local_date() -> str:
    """تاريخ اليوم بتوقيت القاهرة المحلي (السيرفر UTC — نحوّل قبل المقارنة)."""
    return utcnow().astimezone().strftime("%Y-%m-%d")


def set_capture_status(cid: int, status: str) -> bool:
    done_at = "now()" if status == "done" else "NULL"
    row = x(f"UPDATE captures SET status=%s, done_at={done_at}, updated_at=now() WHERE id=%s",
            (status, cid))
    x("INSERT INTO capture_events(capture_id, type, detail) VALUES (%s,'status',%s)", (cid, status))
    return row > 0


def snooze_capture(cid: int, minutes: int) -> bool:
    return x("""UPDATE captures
                SET remind_at = now() + (%s || ' minutes')::interval, updated_at=now()
                WHERE id=%s""", (minutes, cid)) > 0
