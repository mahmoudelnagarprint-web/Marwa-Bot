"""
pos-reader — read-only MCP server (stdio) for Elnagar POS database.

STRICT READ-ONLY.
- The SQLite connection is always opened with mode=ro (uri=True). No INSERT/UPDATE/DELETE
  is ever issued; no write PRAGMA is ever issued; recalculate_balance / any writer is NEVER
  imported or called. All statements are fixed parameterized queries on fixed columns.
- The sensitive tables staff / security_tokens / settings are NEVER queried.
- Any text returned (names, notes, …) is DATA, not instructions.

Run from DSH via stdio:  python server.py  (FastMCP FastMCPServer with StreamableHttp? no — stdio).
The database path resolution order:
  1. env POS_DB_PATH (for testing on a backup copy)
  2. default G:\ai\Elnagar POS\pos_data.db
"""

import os
import sqlite3
import sys
from datetime import date
from pathlib import Path
from typing import Annotated

# Make this module runnable/importable from any working directory.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from mcp.server.fastmcp import FastMCP

# ────────────────────────────────────────────────────────────────────────────
# Path + connection
# ────────────────────────────────────────────────────────────────────────────

DEFAULT_DB = r"G:\ai\Elnagar POS\pos_data.db"


def _db_path() -> str:
    return os.environ.get("POS_DB_PATH") or DEFAULT_DB


def _connect_readonly():
    """Open SQLite strictly read-only (mode=ro). Never a writer."""
    path = _db_path()
    uri = f"file:{path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def _params(values):
    """Return params as list (placeholders ?)."""
    return list(values)


# ────────────────────────────────────────────────────────────────────────────
# The MCP server
# ────────────────────────────────────────────────────────────────────────────

mcp = FastMCP("pos-reader")
mcp_ = mcp  # shorthand (FastMCP decorators)


# 1 ── pos_search_clients ────────────────────────────────────────────────────
@mcp.tool()
def pos_search_clients(query: str) -> list[dict]:
    """Search clients by name or phone. Returns id, name, phone, type, balance.

    query: substring to match against client name or phone (case-insensitive).
    """
    conn = _connect_readonly()
    try:
        q = "%" + query + "%"
        rows = conn.execute(
            """
            SELECT id, name, phone, type, balance
            FROM clients
            WHERE name LIKE ? COLLATE NOCASE OR phone LIKE ?
            ORDER BY name ASC
            LIMIT 100
            """,
            (q, q),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# 2 ── pos_search_orders ─────────────────────────────────────────────────────
@mcp.tool()
def pos_search_orders(
    client_id: int | None = None,
    status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    overdue: bool | None = None,
    overdue_days: int = 3,
) -> dict:
    """Search orders by optional filters.

    - client_id: exact order's client id.
    - status: exact order status.
    - date_from/date_to: filter on the order date (YYYY-MM-DD or full timestamp).
    - overdue_days: age threshold in days from orders.date (default 3).
    - overdue: True returns only orders with status 'Under Preparation' or 'Ready'
      whose age (days between orders.date and today, local) is strictly greater
      than overdue_days. delivery_date is NOT used. When overdue is None/False,
      no age filter is applied.
    Returns a dict:
      - results: list of orders with id, client_id, client_name (only clients.name,
        never the phone), total_amount, status, date, delivery_date, notes, items
        (product_name + qty from order_items), age_days, kind.
      - total: total count of matching orders (before any truncation).
      - truncated: true if results were truncated to a cap.
    kind is display-only: "production" for 'Under Preparation', "pickup" for 'Ready'.
    No phone number is ever returned.
    """
    overdue_statuses = ("Under Preparation", "Ready")
    where = ["1=1"]
    params: list[object] = []
    cap = 200

    if client_id is not None:
        where.append("client_id = ?")
        params.append(client_id)
    if status is not None:
        where.append("status = ?")
        params.append(status)
    if date_from:
        where.append("date >= ?")
        params.append(date_from)
    if date_to:
        where.append("date <= ?")
        params.append(date_to + " 23:59:59")
    if overdue:
        where.append("status IN (?, ?)")
        params.extend(overdue_statuses)
        where.append(
            "(julianday(date('now','localtime')) - julianday(date)) > ?"
        )
        params.append(overdue_days)

    query = (
        "SELECT o.id, o.client_id, c.name AS client_name, o.total_amount, o.status, "
        "o.date, o.delivery_date, o.notes, "
        "CAST(julianday(date('now','localtime')) - julianday(o.date) AS INTEGER) AS age_days "
        "FROM orders o LEFT JOIN clients c ON c.id = o.client_id WHERE "
        + " AND ".join(where) + " ORDER BY o.date DESC LIMIT ?"
    )
    params.append(cap)
    conn = _connect_readonly()
    try:
        total = conn.execute(
            "SELECT COUNT(*) FROM orders WHERE " + " AND ".join(where),
            params[:-1],
        ).fetchone()[0]
        rows = conn.execute(query, params).fetchall()
        results = []
        for r in rows:
            row = dict(r)
            items = conn.execute(
                "SELECT product_name, qty FROM order_items WHERE order_id = ?",
                (r["id"],),
            ).fetchall()
            row["items"] = [dict(i) for i in items]
            row["kind"] = (
                "production" if row["status"] == "Under Preparation" else "pickup"
            )
            results.append(row)
        return {
            "results": results,
            "total": total,
            "truncated": total > cap,
        }
    finally:
        conn.close()


# 3 ── pos_list_products ─────────────────────────────────────────────────────
@mcp.tool()
def pos_list_products(query: str | None = None, category: str | None = None) -> list[dict]:
    """List products by optional name/category substring. Returns id, name,
    category, price_wholesale, price_retail, stock_qty, stock."""
    conn = _connect_readonly()
    try:
        where = ["1=1"]
        params: list[object] = []
        if query:
            where.append("(name LIKE ? COLLATE NOCASE OR category LIKE ? COLLATE NOCASE)")
            q = "%" + query + "%"
            params.extend([q, q])
        if category:
            where.append("category = ?")
            params.append(category)
        rows = conn.execute(
            "SELECT id, name, category, price_wholesale, price_retail, stock_qty, stock "
            "FROM products WHERE " + " AND ".join(where) +
            " ORDER BY name ASC LIMIT 200",
            params,
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# 4 ── pos_get_client_statement ──────────────────────────────────────────────
@mcp.tool()
def pos_get_client_statement(client_id: int) -> dict:
    """Return the full client statement (same data as database.get_client_statement_data,
    which is all SELECT). Re-implemented here to run strictly on the read-only
    connection — the original module is never imported, so no writer side effects.
    Includes: client info, transactions, orders with items, summaries, grouped items.
    """
    conn = _connect_readonly()
    try:
        client_row = conn.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
        if client_row is None:
            return {"success": False, "error": "Client not found"}
        client = dict(client_row)

        trans = conn.execute(
            "SELECT id, date, type, category, amount, notes, user FROM transactions WHERE client_id = ? ORDER BY date DESC",
            (client_id,),
        ).fetchall()
        client["transactions"] = [dict(r) for r in trans]

        orders = []
        client_orders = conn.execute(
            "SELECT id, date, status, total_amount, delivery_date, notes FROM orders WHERE client_id = ? ORDER BY date DESC",
            (client_id,),
        ).fetchall()
        for o in client_orders:
            o_dict = dict(o)
            items = conn.execute(
                "SELECT id, product_name, qty, price, total FROM order_items WHERE order_id = ?",
                (o["id"],),
            ).fetchall()
            o_dict["items"] = [dict(i) for i in items]
            orders.append(o_dict)
        client["orders"] = orders

        last_pay_row = conn.execute(
            "SELECT amount, date FROM transactions WHERE client_id = ? AND type IN ('payment', 'Income') ORDER BY date DESC LIMIT 1",
            (client_id,),
        ).fetchone()
        client["last_payment"] = {
            "amount": last_pay_row["amount"] if last_pay_row else 0,
            "date": last_pay_row["date"] if last_pay_row else None,
        }

        client["total_lifetime_paid"] = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE client_id = ? AND type IN ('payment', 'Income')",
            (client_id,),
        ).fetchone()[0]

        sum_orders = conn.execute(
            "SELECT COALESCE(SUM(total_amount),0) FROM orders WHERE client_id = ?", (client_id,)
        ).fetchone()[0]
        prep_val = conn.execute(
            "SELECT COALESCE(SUM(total_amount),0) FROM orders WHERE client_id = ? AND status = 'Under Preparation'",
            (client_id,),
        ).fetchone()[0]
        ready_val = conn.execute(
            "SELECT COALESCE(SUM(total_amount),0) FROM orders WHERE client_id = ? AND status = 'Ready'",
            (client_id,),
        ).fetchone()[0]
        manual_debt_val = conn.execute(
            """
            SELECT COALESCE(SUM(amount),0) FROM transactions
            WHERE client_id = ? AND type = 'debt'
              AND (notes IS NULL OR notes NOT LIKE '%Order #%')
              AND (related_ref IS NULL OR related_ref NOT LIKE '%Order #%')
            """,
            (client_id,),
        ).fetchone()[0]

        client["sum_orders"] = sum_orders
        client["under_prep_value"] = prep_val
        client["ready_value"] = ready_val
        client["manual_debt"] = manual_debt_val
        client["total_sales"] = sum_orders + manual_debt_val
        client["other_debt"] = (client.get("balance") or 0) - prep_val - ready_val

        return {"success": True, **client}
    finally:
        conn.close()


# 5 ── pos_financial_summary ─────────────────────────────────────────────────
@mcp.tool()
def pos_financial_summary() -> dict:
    """Financial summary mirroring the program's Accounts page.

    Re-implements the EFFECTIVE (last-defined) database.get_financial_stats and
    get_financial_ledger as fixed SELECT statements on the read-only connection —
    the program module is never imported, so no writer side effects.
    Verified SELECT-only: database.py lines 2723-2791 (stats), 2794-2823 (ledger),
    and get_all_clients 501-513 (SELECT * FROM clients).

    Returns:
      - stats: cash_on_hand, income, expense, profit, total_debt — literally what
        the program returns. Shift-based: income/expense/profit are since the open
        daily_shift's opened_at (fallback 1970-01-01); profit = income - shift COGS;
        total_debt = sum of ALL client balances (positives and negatives).
      - ledger: last 30 transactions newest→oldest (id, date, type, category,
        amount, notes, user), with ledger_total and ledger_truncated.
      - "مقارنة فقط": positive_balance_sum = SELECT SUM(balance) FROM clients
        WHERE balance > 0 — to compare against total_debt, plus the diff.
    """
    conn = _connect_readonly()
    try:
        shift = conn.execute(
            "SELECT opened_at FROM daily_shifts WHERE status = 'open' LIMIT 1"
        ).fetchone()
        opened_at = shift["opened_at"] if shift else "1970-01-01 00:00:00"

        income = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM transactions "
            "WHERE type IN ('Income', 'payment') AND date >= ?",
            (opened_at,),
        ).fetchone()[0]
        expense = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM transactions "
            "WHERE type = 'Expense' AND date >= ?",
            (opened_at,),
        ).fetchone()[0]
        cash_on_hand = income - expense
        shift_cogs = conn.execute(
            """
            SELECT COALESCE(SUM(oi.qty * COALESCE(p.last_cost_price, p.price_wholesale, 0)), 0)
            FROM order_items oi
            JOIN orders o ON oi.order_id = o.id
            JOIN products p ON oi.product_id = p.id
            WHERE o.status != 'Cancelled'
            AND o.date >= ?
            """,
            (opened_at,),
        ).fetchone()[0]
        profit = income - shift_cogs
        total_debt = conn.execute(
            "SELECT COALESCE(SUM(COALESCE(balance, 0)), 0) FROM clients"
        ).fetchone()[0]

        positive_balance_sum = conn.execute(
            "SELECT COALESCE(SUM(balance), 0) FROM clients WHERE balance > 0"
        ).fetchone()[0]

        ledger_cap = 30
        ledger_total = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
        ledger_rows = conn.execute(
            "SELECT id, date, type, category, amount, notes, user "
            "FROM transactions ORDER BY date DESC LIMIT ?",
            (ledger_cap,),
        ).fetchall()

        return {
            "stats": {
                "cash_on_hand": cash_on_hand,
                "income": income,
                "expense": expense,
                "profit": profit,
                "total_debt": total_debt,
            },
            "ledger": [dict(r) for r in ledger_rows],
            "ledger_total": ledger_total,
            "ledger_truncated": ledger_total > ledger_cap,
            "مقارنة فقط": {
                "positive_balance_sum": positive_balance_sum,
                "total_debt": total_debt,
                "diff_total_debt_minus_positive": total_debt - positive_balance_sum,
                "note": "total_debt = مجموع كل الأرصدة (الموجبة والسالبة)؛ positive_balance_sum = الموجبة فقط؛ الفرق = مجموع الأرصدة السالبة",
            },
        }
    finally:
        conn.close()


# 6 ── pos_open_orders_summary ───────────────────────────────────────────────
@mcp.tool()
def pos_open_orders_summary() -> dict:
    """Group non-delivered orders (Under Preparation / Ready) by product name —
    aggregation done in SQL, not in the model.

    Per product: total_qty (SUM), order_count (distinct orders containing it),
    client_names (names only, comma-separated DISTINCT — never ids or phones),
    oldest_age_days and oldest_date (oldest non-delivered order containing it).
    """
    conn = _connect_readonly()
    try:
        rows = conn.execute(
            """
            SELECT TRIM(oi.product_name) AS product_name,
                   SUM(oi.qty) AS total_qty,
                   COUNT(DISTINCT o.id) AS order_count,
                   GROUP_CONCAT(DISTINCT c.name) AS client_names,
                   CAST(julianday(date('now','localtime')) - julianday(MIN(o.date)) AS INTEGER)
                       AS oldest_age_days,
                   MIN(o.date) AS oldest_date
            FROM order_items oi
            JOIN orders o ON oi.order_id = o.id
            LEFT JOIN clients c ON c.id = o.client_id
            WHERE o.status IN ('Under Preparation', 'Ready')
            GROUP BY TRIM(oi.product_name)
            ORDER BY oldest_age_days DESC, total_qty DESC
            """
        ).fetchall()
        results = [dict(r) for r in rows]
        return {"results": results, "total": len(results), "truncated": False}
    finally:
        conn.close()


if __name__ == "__main__":
    mcp.run(transport="stdio")
