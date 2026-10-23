#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sqlite3
import datetime

def main():
    conn = sqlite3.connect(r"G:\ai\Elnagar POS\pos_data.db")
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # Cash on hand (all time): Income - Expense
    c.execute("SELECT COALESCE(SUM(amount),0) FROM transactions WHERE type IN ('Income','payment')")
    income_all = c.fetchone()[0]
    c.execute("SELECT COALESCE(SUM(amount),0) FROM transactions WHERE type='Expense'")
    expense_all = c.fetchone()[0]
    cash_on_hand = income_all - expense_all
    
    # Monthly income/expense (current month)
    now = datetime.datetime.now()
    month_start = now.replace(day=1).strftime("%Y-%m-%d")
    c.execute("SELECT COALESCE(SUM(amount),0) FROM transactions WHERE type IN ('Income','payment') AND date >= ?", (month_start,))
    income_month = c.fetchone()[0]
    c.execute("SELECT COALESCE(SUM(amount),0) FROM transactions WHERE type='Expense' AND date >= ?", (month_start,))
    expense_month = c.fetchone()[0]
    profit_month = income_month - expense_month
    
    # Total Debt: Client balances + Under Preparation orders
    c.execute("SELECT COALESCE(SUM(balance),0) FROM clients")
    sum_bal = c.fetchone()[0]
    c.execute("SELECT COALESCE(SUM(total_amount),0) FROM orders WHERE status='Under Preparation'")
    sum_under = c.fetchone()[0]
    total_debt = sum_bal + sum_under
    
    # Shift status
    c.execute("SELECT opened_at, status FROM daily_shifts WHERE status='open' LIMIT 1")
    shift = c.fetchone()
    if shift:
        shift_opened = shift['opened_at']
        shift_status = shift['status']
    else:
        shift_opened = None
        shift_status = 'none'
    
    # Weekly metrics (last 7 days)
    c.execute("SELECT COALESCE(SUM(amount),0) FROM transactions WHERE type IN ('Income','payment') AND date >= date('now','-7 days','localtime')")
    weekly_income = c.fetchone()[0]
    c.execute("SELECT COALESCE(SUM(amount),0) FROM transactions WHERE type='Expense' AND date >= date('now','-7 days','localtime')")
    weekly_expense = c.fetchone()[0]
    weekly_profit = weekly_income - weekly_expense
    
    # Prepare output lines
    lines = []
    lines.append("===== الحالة المالية الحالية =====")
    lines.append(f"النقد بالدرج (الإجمالي): {cash_on_hand:,.0f} ج")
    lines.append(f"الدخل الشهري: {income_month:,.0f} ج")
    lines.append(f"المصروف الشهري: {expense_month:,.0f} ج")
    print(f"صافي الربح الشهري: {profit_month:,.0f} ج")
    lines.append(f"إجمالي ديون العملاء (الرصيد + تحت التجهيز): {total_debt:,.0f} ج")
    lines.append(f"   └─ رصيد العملاء: {sum_bal:,.0f} ج")
    lines.append(f"   └─ تحت التجهيز: {sum_under:,.0f} ج")
    lines.append(f"الحالة المالية للشيفت: {shift_status} منذ {shift_opened}")
    lines.append(f"الدخل الأسبوعي: {weekly_income:,.0f} ج")
    lines.append(f"المصروف الأسبوعي: {weekly_expense:,.0f} ج")
    lines.append(f"صافي الربح الأسبوعي: {weekly_profit:,.0f} ج")
    
    # Write to file
    output_path = r"G:\ai\Naggar Print POS Agent\financial_state_output.txt"
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    
    print(f"تم حفظ الحالة المالية في الملف: {output_path}")
    conn.close()

if __name__ == '__main__':
    main()