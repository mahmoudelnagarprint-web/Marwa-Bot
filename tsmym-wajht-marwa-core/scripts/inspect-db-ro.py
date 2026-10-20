# -*- coding: utf-8 -*-
"""Read-only schema & data inspection of the live POS database.

RED LINE: opens the SQLite database in URI read-only mode (mode=ro).
No write, no commit, no schema change is ever possible on this handle.
"""
import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")

DB = r"G:\ai\Elnagar POS\pos_data.db"

# mode=ro -> SQLite refuses any write on this connection.
conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=5)
cur = conn.cursor()

print("== TABLES ==")
tables = [r[0] for r in cur.execute(
    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()]
print(tables)

for t in ("settings", "transactions", "clients", "orders"):
    if t not in tables:
        print(f"-- {t}: MISSING")
        continue
    cols = [r[1] for r in conn.execute(f"PRAGMA table_info({t})").fetchall()]
    print(f"-- {t}: {cols}")

print("== SETTINGS ==")
try:
    for row in conn.execute("SELECT key, value FROM settings").fetchall():
        print(row)
except Exception as e:
    print("settings read error:", e)

print("== TRANSACTIONS: last 8 ==")
try:
    for row in conn.execute(
        "SELECT id, date, type, amount, client_id, notes FROM transactions ORDER BY id DESC LIMIT 8"
    ).fetchall():
        print(row)
    print("count:", conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0])
except Exception as e:
    print("transactions read error:", e)

print("== CLIENTS: positive balances ==")
try:
    rows = conn.execute(
        "SELECT id, name, balance FROM clients WHERE balance > 0 ORDER BY balance DESC"
    ).fetchall()
    for row in rows:
        print(row)
    print("sum_positive:", conn.execute(
        "SELECT IFNULL(SUM(balance),0) FROM clients WHERE balance > 0").fetchone()[0])
except Exception as e:
    print("clients read error:", e)

print("== ORDERS: status breakdown ==")
try:
    for row in conn.execute(
        "SELECT status, COUNT(*), IFNULL(SUM(total_amount),0) FROM orders GROUP BY status"
    ).fetchall():
        print(row)
    print("last order date:", conn.execute("SELECT MAX(date) FROM orders").fetchone())
except Exception as e:
    print("orders read error:", e)

print("== OCTOBER WINDOW (income/expense) ==")
try:
    for row in conn.execute(
        "SELECT type, IFNULL(SUM(amount),0) FROM transactions WHERE date >= '2026-10-01' GROUP BY type"
    ).fetchall():
        print(row)
    print("last movement:", conn.execute(
        "SELECT id, date, type, amount FROM transactions ORDER BY id DESC LIMIT 3").fetchall())
except Exception as e:
    print("window read error:", e)

conn.close()
print("READ-ONLY inspection done.")
