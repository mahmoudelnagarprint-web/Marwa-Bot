#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script to archive pre-October 2026 financial data and set accounting start date.
"""
import sys
import traceback
sys.stdout.reconfigure(encoding='utf-8')

def main():
    try:
        print("START: Archiving pre-October 2026 data")
        import sqlite3
        import pandas as pd
        import os
        from datetime import datetime

        DB_PATH = r"G:\ai\Elnagar POS\pos_data.db"
        EXPORT_DIR = r"G:\ai\Naggar Print POS Agent\جرد_وشيفت"
        os.makedirs(EXPORT_DIR, exist_ok=True)
        EXCEL_PATH = os.path.join(EXPORT_DIR, "أرشيف_الحسابات_السابقة_قبل_أكتوبر_2026.xlsx")
        SETTINGS_KEY = "accounting_start_date"
        SETTINGS_VALUE = "2026-10-01"

        def get_connection():
            return sqlite3.connect(DB_PATH)

        print("Step 1: Exporting pre-October data to Excel...")
        conn = get_connection()
        try:
            txns = pd.read_sql_query("SELECT * FROM transactions WHERE date(date) < '2026-10-01' ORDER BY date", conn)
            orders = pd.read_sql_query("SELECT * FROM orders WHERE date(date) < '2026-10-01' ORDER BY date", conn)
            clients = pd.read_sql_query("SELECT * FROM clients", conn)
            obligations = pd.read_sql_query("SELECT * FROM obligations", conn)
            archive = pd.read_sql_query("SELECT * FROM daily_financial_archive ORDER BY date", conn)
            shifts = pd.read_sql_query("SELECT * FROM daily_shifts ORDER BY opened_at", conn)
            settings = pd.read_sql_query("SELECT * FROM settings", conn)
            with pd.ExcelWriter(EXCEL_PATH, engine='openpyxl') as writer:
                txns.to_excel(writer, sheet_name='Transactions', index=False)
                orders.to_excel(writer, sheet_name='Orders', index=False)
                clients.to_excel(writer, sheet_name='Clients', index=False)
                obligations.to_excel(writer, sheet_name='Obligations', index=False)
                archive.to_excel(writer, sheet_name='Daily_Archive', index=False)
                shifts.to_excel(writer, sheet_name='Shifts', index=False)
                settings.to_excel(writer, sheet_name='Settings', index=False)
            print(f"  Excel exported to: {EXCEL_PATH}")
        finally:
            conn.close()

        print("Step 2: Adding archived column to transactions and marking pre-Oct rows...")
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("PRAGMA table_info(transactions)")
            cols = [row[1] for row in cur.fetchall()]
            if 'archived' not in cols:
                cur.execute("ALTER TABLE transactions ADD COLUMN archived INTEGER DEFAULT 0")
                conn.commit()
                print("  Added column 'archived'.")
            cur.execute("UPDATE transactions SET archived = 1 WHERE date(date) < '2026-10-01'")
            updated = cur.rowcount
            conn.commit()
            print(f"  Marked {updated} transactions as archived.")
        finally:
            conn.close()

        print("Step 3: Setting accounting_start_date...")
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (SETTINGS_KEY, SETTINGS_VALUE))
            conn.commit()
            print(f"  Setting {SETTINGS_KEY} = {SETTINGS_VALUE} saved.")
        finally:
            conn.close()

        print("Step 4: Running auto_archive (optional)...")
        try:
            # We could import financial_engine, but for simplicity we'll just note.
            print("  Skipping auto_archive; user can run via API if needed.")
        except Exception as e:
            print(f"  Error in auto_archive: {e}")

        print("SUCCESS: Archiving process completed.")
    except Exception as e:
        print(f"ERROR: {e}")
        traceback.print_exc()

if __name__ == '__main__':
    main()