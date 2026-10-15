# -*- coding: utf-8 -*-
"""فحص توازن pos_financial_summary مع الدالة الرسمية get_financial_stats (2026-10-12).

الاستخدام: python check_financial_parity.py [مجلد_البرنامج]
  الافتراضي: G:\ai\Elnagar POS (الحية). مرر مسار نسخة الاختبار لفحصها.

المبدأ: يستورد database.py من المجلد الممرر (get_financial_stats/get_financial_ledger
دوال SELECT فقط — مثبت في فحص 4.0 على الأسطر 2723-2823) ويقارن أرقامه مع نفس
عبارات SELECT المستخدمة في أداة pos-reader (mcp/pos-reader/server.py,
pos_financial_summary) على اتصال قراءة فقط (PRAGMA query_only).
PASS عند تطابق الأرقام الخمسة.
"""
import sys
import os
import sqlite3
sys.stdout.reconfigure(encoding="utf-8")

prog = sys.argv[1] if len(sys.argv) > 1 else r"G:\ai\Elnagar POS"
os.chdir(prog)
sys.path.insert(0, prog)
import database

conn = sqlite3.connect("pos_data.db")
conn.row_factory = sqlite3.Row
conn.execute("PRAGMA query_only = 1")  # قراءة فقط بلا أي كتابة

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
    "SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE type = 'Expense' AND date >= ?",
    (opened_at,),
).fetchone()[0]
cash = income - expense
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
debt = conn.execute(
    "SELECT COALESCE(SUM(COALESCE(balance, 0)), 0) FROM clients"
).fetchone()[0]
conn.close()

official = database.get_financial_stats()
tool_side = {"cash_on_hand": cash, "income": income, "expense": expense,
             "profit": profit, "total_debt": debt}
print("المجلد:", prog)
print("أداة pos_financial_summary (نفس SQL):", tool_side)
print("الدالة الرسمية get_financial_stats:", dict(official))

ok = True
for k, v in tool_side.items():
    ov = official.get(k) if hasattr(official, "get") else official[k]
    if abs(float(ov) - float(v)) > 0.005:
        print(f"  فرق في {k}: رسمي {ov} مقابل أداة {v}")
        ok = False
print("PASS توازن تام بين الأداة والدالة الرسمية" if ok else "فارق — راجع الأرقام أعلاه")
