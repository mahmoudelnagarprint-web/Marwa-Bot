# -*- coding: utf-8 -*-
"""محوّال منظومة المحل (Retail) — R1.

مبدأ v1 المقدس: قاعدة POS **قراءة فقط** — لا كتابة أبدًا.

- لقطة دورية/يدوية من قاعدة POS (SQLite mode=ro) على الجهاز اللي عنده القاعدة
  (غالبًا جهاز الورشة) → تُخزن في Supabase (retail_snapshots + retail_inventory).
- البوت والواجهة يقرأوا آخر لقطة فقط — لا استعلام حي على قاعدة المحل.
- أسماء الأعمدة مستمدة من pos-reader MCP؛ لو اختلفت النسخة، القسم الفاشل
  يُسجّل بصدق في sync_log بدون كسر بقية اللقطة.
"""
from __future__ import annotations

import json
import sqlite3
from typing import Any, Dict, List, Optional

import psycopg2.extras

from nb import config, db


def _log(ok: bool, kind: str, detail: str) -> None:
    try:
        db.x("""INSERT INTO sync_log(kind, ok, node_id, detail) VALUES (%s,%s,%s,%s)""",
             (kind, ok, config.NODE_ID, detail[:400]))
    except Exception:
        pass


# ------------------------------------------------------------------ POS pull
def _ro_connect():
    path = config.POS_DB_PATH
    if not path:
        raise FileNotFoundError("NB2_POS_DB_PATH غير مضبوط في .env")
    uri = f"file:{path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def _safe_one(conn: sqlite3.Connection, sql: str, default=None):
    try:
        row = conn.execute(sql).fetchone()
        return dict(row) if row else default
    except Exception as exc:
        return {"__error__": f"{type(exc).__name__}: {exc}"}


def _safe_all(conn: sqlite3.Connection, sql: str, limit: int = 500):
    try:
        return [dict(r) for r in conn.execute(sql).fetchall()][:limit]
    except Exception as exc:
        return [{"__error__": f"{type(exc).__name__}: {exc}"}]


def pull_pos_snapshot() -> Dict[str, Any]:
    """سحب لقطة كاملة من POS → PG. يرجع اللقطة (أو خطأ صادق)."""
    try:
        conn = _ro_connect()
    except Exception as exc:
        _log(False, "retail_pull", f"فشل فتح قاعدة POS: {exc}")
        raise

    payload: Dict[str, Any] = {}
    try:
        payload["clients"] = _safe_one(conn, """SELECT COUNT(*) AS count,
                       SUM(CASE WHEN balance > 0 THEN balance ELSE 0 END) AS positive_debt,
                       SUM(balance) AS total_balance FROM clients""")
        payload["low_stock"] = _safe_all(conn, """SELECT id, name, category, stock_qty
                              FROM products
                              WHERE COALESCE(stock_qty, 0) <= 5
                              ORDER BY stock_qty ASC LIMIT 30""", 30)
        payload["open_orders"] = _safe_one(conn, """SELECT COUNT(*) AS count FROM orders
                              WHERE status IN ('Under Preparation','Ready')""")
        payload["overdue_orders"] = _safe_all(conn, """SELECT o.id, o.status, o.date, o.total_amount
                                   FROM orders o
                                   WHERE o.status IN ('Under Preparation','Ready')
                                     AND o.date < date('now', '-3 days')
                                   ORDER BY o.date ASC LIMIT 15""", 15)
        products = _safe_all(conn, """SELECT id, name, category, price_retail,
                          price_wholesale, stock_qty FROM products LIMIT 500""", 500)
    finally:
        conn.close()

    sid = db.q("""INSERT INTO retail_snapshots(node_id, scope, payload)
                  VALUES (%s,'full',%s) RETURNING id, captured_at""",
               (config.NODE_ID, psycopg2.extras.Json(payload)), one=True)
    inv = [p for p in products if "__error__" not in p]
    for p in inv:
        db.x("""INSERT INTO retail_inventory(snapshot_id, product_id, name, category,
                                          stock_qty, price_retail, price_wholesale, captured_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
             (sid["id"], p.get("id"), p.get("name"), p.get("category"),
              p.get("stock_qty"), p.get("price_retail"), p.get("price_wholesale"), sid["captured_at"]))

    errors = [k for k, v in payload.items() if isinstance(v, dict) and "__error__" in v]
    _log(not errors, "retail_pull",
         f"لقطة #{sid['id']} — أقسام فاشلة: {errors or 'لا شيء'} | منتجات: {len(inv)}")
    return {"id": sid["id"], "captured_at": sid["captured_at"], "errors": errors,
            "products": len(inv), "payload": payload}


def last_snapshot() -> Optional[Dict[str, Any]]:
    return db.q("SELECT * FROM retail_snapshots ORDER BY id DESC LIMIT 1", one=True)


def digest(snapshot: Optional[Dict[str, Any]] = None, max_lines: int = 14) -> str:
    """ملخص عربي مختصر للبوت/البرييفينج من آخر لقطة."""
    snap = snapshot or last_snapshot()
    if not snap:
        return "🏪 مفيش لقطة للمحل بعد — شغّل السحب من جهاز فيه قاعدة POS."
    p = snap.get("payload") or {}
    lines = [f"🏪 المحل — آخر لقطة: {snap['captured_at'].strftime('%Y-%m-%d %H:%M') if hasattr(snap['captured_at'], 'strftime') else snap['captured_at']}"]

    cl = p.get("clients") or {}
    if cl and "__error__" not in cl:
        lines.append(f"👥 عملاء: {cl.get('count', '?')} | 💳 ديون موجبة: {cl.get('positive_debt', '?')}")
    oo = p.get("open_orders") or {}
    if oo and "__error__" not in oo:
        lines.append(f"📦 طلبات مفتوحة: {oo.get('count', '?')}")
    low = p.get("low_stock") or []
    if low and "__error__" not in (low[0] or {}):
        lines.append(f"⚠️ ناقص مخزون ({len(low)}):")
        lines += [f"   • {it.get('name')} ({it.get('stock_qty')})" for it in low[:5]]
    od = p.get("overdue_orders") or []
    if od and "__error__" not in (od[0] or {}):
        lines.append(f"🔴 طلبات متأخرة: {len(od)}")
    if len(lines) > max_lines:
        lines = lines[:max_lines] + ["   …"]
    return "\n".join(lines)


# ------------------------------------------------------------------ agents
def ingest_agent_report(agent: str, title: str, body: str = "", scope: str = "",
                        severity: str = "info", payload: Optional[Dict[str, Any]] = None,
                        source: str = "api") -> Dict[str, Any]:
    if severity not in ("info", "warn", "critical"):
        severity = "info"
    row = db.q("""INSERT INTO agent_reports(agent, scope, severity, title, body, payload, source)
                  VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id, received_at""",
               (agent.strip()[:50], scope or None, severity, title.strip()[:300], body,
                psycopg2.extras.Json(payload or {}), source), one=True)
    if severity == "critical" and config.OWNER_TELEGRAM_ID:
        db.x("""INSERT INTO outbox(chat_id, body, kind, dedupe_key)
                VALUES (%s, %s, 'agent_alert', %s) ON CONFLICT DO NOTHING""",
             (config.OWNER_TELEGRAM_ID,
              f"🚨 تقرير حرج من {agent}: {title}\n{body or ''}"[:3500],
              f"agent-crit-{row['id']}"))
    return row


def latest_agent_reports(limit: int = 10) -> List[Dict[str, Any]]:
    return db.q("""SELECT * FROM agent_reports
                   WHERE severity != 'info' OR acked_at IS NULL
                   ORDER BY id DESC LIMIT %s""", (limit,))


def ack_report(rid: int) -> bool:
    return db.x("UPDATE agent_reports SET acked_at=now() WHERE id=%s", (rid,)) > 0


def recent_sync_log(limit: int = 15) -> List[Dict[str, Any]]:
    return db.q("SELECT * FROM sync_log ORDER BY id DESC LIMIT %s", (limit,))
