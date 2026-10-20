# -*- coding: utf-8 -*-
"""Read-only follow-up: October window detail + archive/shift tables."""
import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
DB = r"G:\ai\Elnagar POS\pos_data.db"
conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=5)
cur = conn.cursor()

print("== ALL OCTOBER TRANSACTIONS ==")
for row in conn.execute(
    "SELECT id, date, type, amount, client_id, category, is_verified, is_savings, archived "
    "FROM transactions WHERE date >= '2026-10-01' ORDER BY id"
).fetchall():
    print(row)

print("== daily_shifts schema + rows ==")
cols = [r[1] for r in conn.execute("PRAGMA table_info(daily_shifts)").fetchall()]
print("cols:", cols)
for row in conn.execute("SELECT * FROM daily_shifts ORDER BY 1 DESC LIMIT 5").fetchall():
    print(row)

print("== daily_financial_archive schema + rows ==")
cols = [r[1] for r in conn.execute("PRAGMA table_info(daily_financial_archive)").fetchall()]
print("cols:", cols)
for row in conn.execute("SELECT * FROM daily_financial_archive ORDER BY 1 DESC LIMIT 5").fetchall():
    print(row)

print("== client 112 name exact ==")
print(conn.execute("SELECT id, name, phone, balance FROM clients WHERE id IN (63,107,109,112)").fetchall())

print("== orders Under Preparation detail ==")
for row in conn.execute(
    "SELECT id, client_id, total_amount, status, date, notes FROM orders WHERE status IN "
    "('Under Preparation','pending','processing','تحت التجهيز')"
).fetchall():
    print(row)

print("== expenses since 2026-10-01 (any type) ==")
print(conn.execute(
    "SELECT COUNT(*), IFNULL(SUM(amount),0) FROM transactions WHERE date >= '2026-10-01' AND type='Expense'"
).fetchone())

conn.close()
print("done.")
