"""
💰 Financial Integrity Engine
Centralized, Auditable Financial Calculations for Elnagar ERP.
All balance-affecting operations MUST flow through this module.
"""

import sqlite3
from datetime import datetime
from database import get_db_connection

# ═══════════════════════════════════════════════════════════════════
# 📊 CORE CALCULATION ENGINE
# ═══════════════════════════════════════════════════════════════════

def recalculate_balance(client_id: int) -> dict:
    """
    The "Nuclear" Recalculator.
    Rebuilds a client's balance from scratch using raw transaction data.
    
    Formula: Balance = (Sum of Orders + Sum of Manual Debts) - (Sum of Payments)
    
    Returns a detailed audit object for transparency.
    """
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        # 1. Get Client Info (for logging)
        client = c.execute("SELECT name, balance FROM clients WHERE id = ?", (client_id,)).fetchone()
        if not client:
            return {"success": False, "error": "Client not found"}
        
        old_balance = client['balance'] or 0
        client_name = client['name']
        
        # 2. Sum all Orders (Debt Additions)
        orders_sum = c.execute(
            "SELECT COALESCE(SUM(total_amount), 0) FROM orders WHERE client_id = ?",
            (client_id,)
        ).fetchone()[0]
        
        # 3. Sum Manual Debts (from transactions table)
        # CRITICAL FIX: Exclude "debt" transactions that are merely logs of Orders.
        # We exclude if related_ref implies Order OR if notes implies Order (for legacy data validity).
        debts_sum = c.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE client_id = ? AND type = 'debt' AND (related_ref IS NULL OR related_ref NOT LIKE 'Order #%') AND (notes IS NULL OR notes NOT LIKE 'Order #%')",
            (client_id,)
        ).fetchone()[0]
        
        # 4. Sum All Payments (Debt Reductions)
        # Note: 'Income' type was used by older code for payments via order delivery
        payments_sum = c.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE client_id = ? AND type IN ('payment', 'Income')",
            (client_id,)
        ).fetchone()[0]
        
        # 5. Calculate True Balance
        calculated_balance = (orders_sum + debts_sum) - payments_sum
        
        # 6. Update Client Record
        c.execute("UPDATE clients SET balance = ? WHERE id = ?", (calculated_balance, client_id))
        
        # 7. Log the Audit Action
        audit_note = f"[AUDIT] Recalculated. Orders={orders_sum}, Debts={debts_sum}, Payments={payments_sum}. Old={old_balance}, New={calculated_balance}"
        c.execute("""
            INSERT INTO transactions (client_id, type, category, amount, notes, user, related_ref)
            VALUES (?, 'Audit', 'Balance Recalculation', 0, ?, 'System', 'Engine')
        """, (client_id, audit_note))
        
        conn.commit()
        
        return {
            "success": True,
            "client_name": client_name,
            "old_balance": old_balance,
            "new_balance": calculated_balance,
            "breakdown": {
                "orders_sum": orders_sum,
                "manual_debts_sum": debts_sum,
                "payments_sum": payments_sum
            }
        }
        
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


def add_debt(client_id: int, amount: float, source: str, order_id: int = None) -> dict:
    """
    Adds debt to a client's balance.
    Used when creating orders or adding manual debts.
    """
    if amount <= 0:
        return {"success": False, "error": "Amount must be positive"}
    
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        # Update Balance
        c.execute("UPDATE clients SET balance = balance + ? WHERE id = ?", (amount, client_id))
        
        # Log Transaction
        related_ref = f"Order #{order_id}" if order_id else "Manual Debt"
        c.execute("""
            INSERT INTO transactions (client_id, type, category, amount, notes, user, related_ref)
            VALUES (?, 'debt', 'Debt Addition', ?, ?, 'System', ?)
        """, (client_id, amount, source, related_ref))
        
        conn.commit()
        return {"success": True, "amount_added": amount}
        
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


def add_payment(client_id: int, amount: float, source: str, note: str = "Payment") -> dict:
    """
    Records a payment from a client, reducing their balance.
    """
    if amount <= 0:
        return {"success": False, "error": "Amount must be positive"}
    
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        # Update Balance
        c.execute("UPDATE clients SET balance = balance - ? WHERE id = ?", (amount, client_id))
        
        # Log Transaction
        c.execute("""
            INSERT INTO transactions (client_id, type, category, amount, notes, user, related_ref)
            VALUES (?, 'payment', 'Debt Collection', ?, ?, 'System', ?)
        """, (client_id, amount, note, source))
        
        conn.commit()
        return {"success": True, "amount_paid": amount}
        
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


def reverse_order_debt(client_id: int, order_amount: float, order_id: int) -> dict:
    """
    Reverses the debt impact of a deleted order.
    Called when an order is deleted.
    """
    if order_amount <= 0:
        return {"success": True, "message": "No debt to reverse"}
    
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        # Subtract order amount from balance
        c.execute("UPDATE clients SET balance = balance - ? WHERE id = ?", (order_amount, client_id))
        
        # Log the reversal
        c.execute("""
            INSERT INTO transactions (client_id, type, category, amount, notes, user, related_ref)
            VALUES (?, 'Reversal', 'Order Deletion', ?, ?, 'System', ?)
        """, (client_id, -order_amount, f"Reversed debt for deleted Order #{order_id}", f"Order #{order_id}"))
        
        conn.commit()
        return {"success": True, "amount_reversed": order_amount}
        
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


def get_detailed_statement(client_id: int, limit: int = 50) -> dict:
    """
    Returns a detailed transaction history for auditing.
    Includes a running balance calculation.
    """
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        client = c.execute("SELECT name, balance FROM clients WHERE id = ?", (client_id,)).fetchone()
        if not client:
            return {"success": False, "error": "Client not found"}
        
        # Fetch all transactions and orders chronologically
        transactions = c.execute("""
            SELECT id, date, type, amount, notes, related_ref 
            FROM transactions 
            WHERE client_id = ? 
            ORDER BY date DESC 
            LIMIT ?
        """, (client_id, limit)).fetchall()
        
        orders = c.execute("""
            SELECT id, date, total_amount, status, notes 
            FROM orders 
            WHERE client_id = ? 
            ORDER BY date DESC 
            LIMIT ?
        """, (client_id, limit)).fetchall()
        
        return {
            "success": True,
            "client_name": client['name'],
            "current_balance": client['balance'],
            "transactions": [dict(t) for t in transactions],
            "orders": [dict(o) for o in orders]
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════════
# 📈 NEXT-GEN FINANCIAL ERP FUNCTIONS (PHASE 1)
# ═══════════════════════════════════════════════════════════════════

def run_auto_archive() -> dict:
    """
    Scans the transactions table for all historical days (excluding today) 
    that have not been archived yet, and creates snapshots in daily_financial_archive.
    """
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        # Find all unique transaction days before today
        days = c.execute("""
            SELECT DISTINCT date(date) as txn_date 
            FROM transactions 
            WHERE date(date) < date('now', 'localtime')
            ORDER BY txn_date ASC
        """).fetchall()
        
        archived_count = 0
        for row in days:
            txn_date = row['txn_date']
            
            # Check if already archived
            exists = c.execute("SELECT 1 FROM daily_financial_archive WHERE date = ?", (txn_date,)).fetchone()
            if exists:
                continue
                
            # Calculate all-time cash up to the END of this day (23:59:59)
            cash_income = c.execute("""
                SELECT COALESCE(SUM(amount), 0) 
                FROM transactions 
                WHERE type IN ('Income', 'payment') 
                AND date(date) <= ?
            """, (txn_date,)).fetchone()[0]
            
            cash_expense = c.execute("""
                SELECT COALESCE(SUM(amount), 0) 
                FROM transactions 
                WHERE type = 'Expense' 
                AND date(date) <= ?
            """, (txn_date,)).fetchone()[0]
            
            total_cash = cash_income - cash_expense
            
            # Calculate day-specific stats
            day_income = c.execute("""
                SELECT COALESCE(SUM(amount), 0) 
                FROM transactions 
                WHERE type IN ('Income', 'payment') 
                AND date(date) = ?
            """, (txn_date,)).fetchone()[0]
            
            day_expense = c.execute("""
                SELECT COALESCE(SUM(amount), 0) 
                FROM transactions 
                WHERE type = 'Expense' 
                AND date(date) = ?
            """, (txn_date,)).fetchone()[0]
            
            total_expenses = day_expense
            total_profit = day_income - day_expense
            
            # Insert into archive
            c.execute("""
                INSERT INTO daily_financial_archive (date, total_cash, total_profit, total_expenses)
                VALUES (?, ?, ?, ?)
            """, (txn_date, total_cash, total_profit, total_expenses))
            archived_count += 1
            
        conn.commit()
        return {"success": True, "archived_days": archived_count}
        
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


def check_and_reset_obligations():
    """
    Checks all obligations. If the current date has passed the next_due_date,
    resets accumulated_amount to 0 and advances next_due_date by 1 month.
    """
    conn = get_db_connection()
    c = conn.cursor()
    try:
        obs = c.execute("SELECT id, next_due_date, total_monthly_amount FROM scheduled_obligations").fetchall()
        today = datetime.now().date()
        
        for ob in obs:
            ob_id = ob['id']
            due_date_str = ob['next_due_date']
            
            if not due_date_str:
                continue
                
            try:
                due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()
            except ValueError:
                continue
                
            if today > due_date:
                # Calculate next month due date (add approx 30 days, or precisely same day of next month)
                import calendar
                year = due_date.year
                month = due_date.month + 1
                if month > 12:
                    month = 1
                    year += 1
                day = min(due_date.day, calendar.monthrange(year, month)[1])
                new_due_date = f"{year:04d}-{month:02d}-{day:02d}"
                
                # Reset accumulated_amount
                c.execute("""
                    UPDATE scheduled_obligations 
                    SET accumulated_amount = 0, next_due_date = ? 
                    WHERE id = ?
                """, (new_due_date, ob_id))
                
        conn.commit()
    except Exception as e:
        print(f"Error checking obligations: {e}")
    finally:
        conn.close()


def deduct_weekly_obligation(ob_id: int) -> dict:
    """
    Deducts the weekly target from today's cash (adds an Expense transaction)
    and increases the obligation's accumulated_amount.
    """
    check_and_reset_obligations()  # Self-heal first
    
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        ob = c.execute("SELECT title, total_monthly_amount, weekly_deduction_target, accumulated_amount FROM scheduled_obligations WHERE id = ?", (ob_id,)).fetchone()
        if not ob:
            return {"success": False, "error": "Obligation not found"}
            
        title = ob['title']
        total_monthly_amount = ob['total_monthly_amount']
        weekly_deduction_target = ob['weekly_deduction_target']
        accumulated_amount = ob['accumulated_amount'] or 0
        
        if accumulated_amount >= total_monthly_amount:
            return {"success": False, "error": "Obligation is already 100% completed for this period"}
            
        # Deduct whichever is smaller: weekly target or remaining monthly amount
        deduction = min(weekly_deduction_target, total_monthly_amount - accumulated_amount)
        if deduction <= 0:
            return {"success": False, "error": "No deduction needed"}
            
        # 1. Add Expense Transaction
        c.execute("""
            INSERT INTO transactions (client_id, type, category, amount, notes, user, related_ref)
            VALUES (NULL, 'Expense', 'Obligations', ?, ?, 'System', ?)
        """, (deduction, f"Weekly Cut: {title}", f"Obligation #{ob_id}"))
        
        # 2. Update Obligation accumulated amount
        c.execute("""
            UPDATE scheduled_obligations 
            SET accumulated_amount = accumulated_amount + ? 
            WHERE id = ?
        """, (deduction, ob_id))
        
        # 3. Log to obligation_payments_history
        c.execute("""
            INSERT INTO obligation_payments_history (ob_id, amount_paid, payment_type)
            VALUES (?, ?, 'weekly')
        """, (ob_id, deduction))
        
        conn.commit()
        return {"success": True, "deduction": deduction}
        
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


def calculate_financial_analytics() -> dict:
    """
    Calculates expected monthly profit based on current daily averages
    and identifies the top performing product in the last 7 days.
    """
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        # 1. Expected Monthly Profit (last 30 days)
        income_30 = c.execute("""
            SELECT COALESCE(SUM(amount), 0) 
            FROM transactions 
            WHERE type IN ('Income', 'payment') 
            AND date(date) >= date('now', '-30 days', 'localtime')
        """).fetchone()[0]
        
        expense_30 = c.execute("""
            SELECT COALESCE(SUM(amount), 0) 
            FROM transactions 
            WHERE type = 'Expense' 
            AND date(date) >= date('now', '-30 days', 'localtime')
        """).fetchone()[0]
        
        net_profit_30 = income_30 - expense_30
        
        active_days = c.execute("""
            SELECT COUNT(DISTINCT date(date)) 
            FROM transactions 
            WHERE date(date) >= date('now', '-30 days', 'localtime')
        """).fetchone()[0] or 1
        
        daily_avg = net_profit_30 / active_days
        expected_monthly_profit = max(0.0, round(daily_avg * 30, 2))
        
        # 2. Top Performing Product (last 7 days)
        top_prod_row = c.execute("""
            SELECT product_name, SUM(qty) as total_qty 
            FROM order_items oi
            JOIN orders o ON oi.order_id = o.id
            WHERE date(o.date) >= date('now', '-7 days', 'localtime')
            GROUP BY product_name
            ORDER BY total_qty DESC
            LIMIT 1
        """).fetchone()
        
        if top_prod_row and top_prod_row['total_qty'] > 0:
            top_product_name = top_prod_row['product_name']
            top_product_qty = top_prod_row['total_qty']
            recommendation = f"منتج [{top_product_name}] مبيعاته سريعة ({top_product_qty} قطعة في آخر 7 أيام)، ننصح بزيادة إنتاجه هذا الأسبوع لتلبية الطلب."
        else:
            top_product_name = "-"
            top_product_qty = 0
            recommendation = "لا توجد مبيعات كافية في آخر 7 أيام لترشيح إنتاج. استمر في تسجيل الطلبات لتفعيل التوصيات الذكية!"
            
        # 3. Today's vs Yesterday's cash flow comparison
        today_income = c.execute("""
            SELECT COALESCE(SUM(amount), 0) 
            FROM transactions 
            WHERE type IN ('Income', 'payment') 
            AND date(date) = date('now', 'localtime')
        """).fetchone()[0]
        
        yesterday_income = c.execute("""
            SELECT COALESCE(SUM(amount), 0) 
            FROM transactions 
            WHERE type IN ('Income', 'payment') 
            AND date(date) = date('now', '-1 day', 'localtime')
        """).fetchone()[0]
        
        comparison_percentage = 0.0
        if yesterday_income > 0:
            comparison_percentage = round(((today_income - yesterday_income) / yesterday_income) * 100, 2)
            
        weekly = get_weekly_financial_stats()
        return {
            "success": True,
            "expected_monthly_profit": expected_monthly_profit,
            "weekly_cogs": weekly.get("weekly_cogs", 0.0),
            "weekly_revenue": weekly.get("weekly_revenue", 0.0),
            "weekly_business_expenses": weekly.get("weekly_business_expenses", 0.0),
            "weekly_obligations_paid": weekly.get("weekly_obligations_paid", 0.0),
            "weekly_net_profit": weekly.get("weekly_net_profit", 0.0),
            "weekly_personal_draws": weekly.get("weekly_personal_draws", 0.0),
            "top_product": {
                "name": top_product_name,
                "qty": top_product_qty
            },
            "recommendation": recommendation,
            "comparison": {
                "today_income": today_income,
                "yesterday_income": yesterday_income,
                "percentage": comparison_percentage
            }
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


def execute_shortage_purchase(shortage_id: int) -> dict:
    """
    Executes a purchase of a shortage item. 
    Logs an Expense transaction and updates the shortage item's status to 'purchased'.
    """
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        # Fetch shortage info
        sh = c.execute("SELECT name, estimated_cost, qty FROM shortages WHERE id = ?", (shortage_id,)).fetchone()
        if not sh:
            return {"success": False, "error": "Shortage item not found"}
            
        name = sh['name']
        estimated_cost = sh['estimated_cost'] or 0
        qty = sh['qty'] or 1
        total_cost = estimated_cost * qty
        
        # 1. Log Expense Transaction
        c.execute("""
            INSERT INTO transactions (client_id, type, category, amount, notes, user, related_ref)
            VALUES (NULL, 'Expense', 'Shortages', ?, ?, 'System', ?)
        """, (total_cost, f"Purchase: {name} (Qty: {qty})", f"Shortage #{shortage_id}"))
        
        # 2. Update status in shortages table
        c.execute("UPDATE shortages SET status = 'purchased' WHERE id = ?", (shortage_id,))
        
        conn.commit()
        return {"success": True, "total_cost": total_cost}
        
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


def close_daily_shift(user='System') -> dict:
    """
    Closes the current daily shift, locks it, archives its totals,
    and opens a new active shift row in the database.
    """
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        # 1. Fetch the active open shift
        shift = c.execute("SELECT id, opened_at FROM daily_shifts WHERE status = 'open' LIMIT 1").fetchone()
        if not shift:
            # If no open shift exists, open one and return
            c.execute("INSERT INTO daily_shifts (status) VALUES ('open')")
            conn.commit()
            return {"success": True, "message": "No open shift found. Created a new shift."}
            
        shift_id = shift['id']
        opened_at = shift['opened_at']
        closed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 2. Calculate Shift Revenue (Income)
        revenue = c.execute("""
            SELECT COALESCE(SUM(amount), 0) 
            FROM transactions 
            WHERE type IN ('Income', 'payment') 
            AND date >= ?
        """, (opened_at,)).fetchone()[0]
        
        # 3. Calculate Shift Cost (COGS based on product cost prices)
        cost = c.execute("""
            SELECT COALESCE(SUM(oi.qty * COALESCE(p.last_cost_price, p.price_wholesale, 0)), 0)
            FROM order_items oi
            JOIN orders o ON oi.order_id = o.id
            JOIN products p ON oi.product_id = p.id
            WHERE o.status != 'Cancelled'
            AND o.date >= ?
        """, (opened_at,)).fetchone()[0]
        
        # 4. Net Profit = Revenue - Cost
        net_profit = revenue - cost
        
        # 5. Lock the current shift
        c.execute("""
            UPDATE daily_shifts 
            SET closed_at = ?, total_revenue = ?, total_cost = ?, net_profit = ?, status = 'closed'
            WHERE id = ?
        """, (closed_at, revenue, cost, net_profit, shift_id))
        
        # 6. Open a new active shift
        c.execute("INSERT INTO daily_shifts (status) VALUES ('open')")
        
        conn.commit()
        return {
            "success": True, 
            "shift_id": shift_id,
            "opened_at": opened_at,
            "closed_at": closed_at,
            "total_revenue": revenue,
            "total_cost": cost,
            "net_profit": net_profit
        }
        
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


def get_weekly_sold_materials_cost() -> float:
    """
    Calculates the total cost of goods (materials) sold in the last 7 days.
    """
    conn = get_db_connection()
    c = conn.cursor()
    try:
        cost = c.execute("""
            SELECT COALESCE(SUM(oi.qty * COALESCE(p.last_cost_price, p.price_wholesale, 0)), 0)
            FROM order_items oi
            JOIN orders o ON oi.order_id = o.id
            JOIN products p ON oi.product_id = p.id
            WHERE o.status != 'Cancelled'
            AND o.date >= date('now', '-7 days', 'localtime')
        """).fetchone()[0]
        return float(cost)
    except Exception as e:
        print(f"Error calculating weekly COGS: {e}")
        return 0.0
    finally:
        conn.close()


def pay_daily_obligation(ob_id: int) -> dict:
    """
    Deducts the daily target from the drawer (adds an Expense transaction)
    and increases the obligation's accumulated_amount and paid_days.
    """
    check_and_reset_obligations()  # Self-heal first
    
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        ob = c.execute("SELECT title, total_monthly_amount, daily_target_amount, accumulated_amount FROM scheduled_obligations WHERE id = ?", (ob_id,)).fetchone()
        if not ob:
            return {"success": False, "error": "Obligation not found"}
            
        title = ob['title']
        total_monthly_amount = ob['total_monthly_amount']
        daily_target_amount = ob['daily_target_amount'] or 0
        accumulated_amount = ob['accumulated_amount'] or 0
        
        if accumulated_amount >= total_monthly_amount:
            return {"success": False, "error": "Obligation is already 100% completed for this period"}
            
        # Deduct whichever is smaller: daily target or remaining monthly amount
        deduction = min(daily_target_amount, total_monthly_amount - accumulated_amount)
        if deduction <= 0:
            return {"success": False, "error": "No deduction needed"}
            
        # 1. Add Expense Transaction
        c.execute("""
            INSERT INTO transactions (client_id, type, category, amount, notes, user, related_ref)
            VALUES (NULL, 'Expense', 'Obligations', ?, ?, 'System', ?)
        """, (deduction, f"Daily Cut: {title}", f"Obligation #{ob_id}"))
        
        # 2. Update Obligation accumulated amount and paid_days
        c.execute("""
            UPDATE scheduled_obligations 
            SET accumulated_amount = accumulated_amount + ?, paid_days = paid_days + 1 
            WHERE id = ?
        """, (deduction, ob_id))
        
        # 3. Log to obligation_payments_history
        c.execute("""
            INSERT INTO obligation_payments_history (ob_id, amount_paid, payment_type)
            VALUES (?, ?, 'daily')
        """, (ob_id, deduction))
        
        conn.commit()
        return {"success": True, "deduction": deduction}
        
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


def pay_weekly_obligation(ob_id: int) -> dict:
    """
    Deducts the weekly target from the drawer (adds an Expense transaction)
    and increases the obligation's accumulated_amount and paid_weeks.
    """
    check_and_reset_obligations()  # Self-heal first
    
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        ob = c.execute("SELECT title, total_monthly_amount, weekly_target_amount, accumulated_amount FROM scheduled_obligations WHERE id = ?", (ob_id,)).fetchone()
        if not ob:
            return {"success": False, "error": "Obligation not found"}
            
        title = ob['title']
        total_monthly_amount = ob['total_monthly_amount']
        weekly_target_amount = ob['weekly_target_amount'] or 0
        accumulated_amount = ob['accumulated_amount'] or 0
        
        if accumulated_amount >= total_monthly_amount:
            return {"success": False, "error": "Obligation is already 100% completed for this period"}
            
        # Deduct whichever is smaller: weekly target or remaining monthly amount
        deduction = min(weekly_target_amount, total_monthly_amount - accumulated_amount)
        if deduction <= 0:
            return {"success": False, "error": "No deduction needed"}
            
        # 1. Add Expense Transaction
        c.execute("""
            INSERT INTO transactions (client_id, type, category, amount, notes, user, related_ref)
            VALUES (NULL, 'Expense', 'Obligations', ?, ?, 'System', ?)
        """, (deduction, f"Weekly Cut: {title}", f"Obligation #{ob_id}"))
        
        # 2. Update Obligation accumulated amount and paid_weeks
        c.execute("""
            UPDATE scheduled_obligations 
            SET accumulated_amount = accumulated_amount + ?, paid_weeks = paid_weeks + 1 
            WHERE id = ?
        """, (deduction, ob_id))
        
        # 3. Log to obligation_payments_history
        c.execute("""
            INSERT INTO obligation_payments_history (ob_id, amount_paid, payment_type)
            VALUES (?, ?, 'weekly')
        """, (ob_id, deduction))
        
        conn.commit()
        return {"success": True, "deduction": deduction}
        
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


def export_weekly_sold_to_purchases() -> dict:
    """
    Aggregates all items sold in the last 7 days, creates a 'Pending' purchase invoice
    to replenish stock, and logs the cost as an expense transaction.
    """
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        # 1. Fetch aggregated sold items in the last 7 days
        items = c.execute("""
            SELECT oi.product_id, oi.product_name, SUM(oi.qty) as total_qty,
                   COALESCE(p.last_cost_price, p.price_wholesale, 0) as cost_price
            FROM order_items oi
            JOIN orders o ON oi.order_id = o.id
            JOIN products p ON oi.product_id = p.id
            WHERE o.status != 'Cancelled'
            AND o.date >= date('now', '-7 days', 'localtime')
            GROUP BY oi.product_id, oi.product_name
            HAVING total_qty > 0
        """).fetchall()
        
        if not items:
            return {"success": False, "error": "لا توجد مبيعات في آخر 7 أيام لتصديرها"}
            
        # 2. Calculate total invoice cost
        total_cost = sum(row['total_qty'] * row['cost_price'] for row in items)
        
        # 3. Create purchase invoice
        c.execute("""
            INSERT INTO purchase_invoices (supplier_id, supplier_name, total_cost, status, notes)
            VALUES (NULL, 'تصدير تلقائي مبيعات أسبوعية', ?, 'Pending', 'تصدير تلقائي للمواد المباعة في آخر 7 أيام لتغذية المخزون')
        """, (total_cost,))
        
        invoice_id = c.lastrowid
        
        # 4. Insert purchase items
        for row in items:
            item_total = row['total_qty'] * row['cost_price']
            c.execute("""
                INSERT INTO purchase_items (invoice_id, product_id, product_name, qty, cost_price, total)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (invoice_id, row['product_id'], row['product_name'], row['total_qty'], row['cost_price'], item_total))
            
        # 5. Log Expense Transaction in transactions
        c.execute("""
            INSERT INTO transactions (client_id, type, category, amount, notes, user, related_ref)
            VALUES (NULL, 'Expense', 'Purchases', ?, ?, 'System', ?)
        """, (total_cost, f"تصدير مشتريات للمخزون - فاتورة #{invoice_id}", f"Purchase Invoice #{invoice_id}"))
        
        conn.commit()
        return {
            "success": True, 
            "invoice_id": invoice_id, 
            "total_cost": total_cost,
            "items_count": len(items)
        }
        
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


def get_weekly_financial_stats() -> dict:
    """
    Calculates key financial stats for the last 7 days (weekly):
    - weekly_revenue: Total sales/income this week.
    - weekly_cogs: Cost of Goods Sold this week.
    - weekly_business_expenses: Shop expenses + Purchase Invoices paid this week.
    - weekly_obligations_paid: Sum of obligations paid this week.
    - weekly_net_profit: weekly_revenue - (weekly_cogs + weekly_business_expenses + weekly_obligations_paid).
    - weekly_personal_draws: Total Personal expenses drawn this week.
    """
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        # 1. Weekly Revenue
        weekly_revenue = c.execute("""
            SELECT COALESCE(SUM(amount), 0) 
            FROM transactions 
            WHERE type IN ('Income', 'payment') 
            AND date >= date('now', '-7 days', 'localtime')
        """).fetchone()[0]
        
        # 2. Weekly COGS
        weekly_cogs = c.execute("""
            SELECT COALESCE(SUM(oi.qty * COALESCE(p.last_cost_price, p.price_wholesale, 0)), 0)
            FROM order_items oi
            JOIN orders o ON oi.order_id = o.id
            JOIN products p ON oi.product_id = p.id
            WHERE o.status != 'Cancelled'
            AND o.date >= date('now', '-7 days', 'localtime')
        """).fetchone()[0]
        
        # 3. Weekly Business Expenses (excluding Obligations)
        weekly_business_expenses = c.execute("""
            SELECT COALESCE(SUM(amount), 0) 
            FROM transactions 
            WHERE type = 'Expense' 
            AND expense_type = 'Business' 
            AND category != 'Obligations'
            AND date >= date('now', '-7 days', 'localtime')
        """).fetchone()[0]
        
        # 4. Weekly Obligations Paid
        weekly_obligations_paid = c.execute("""
            SELECT COALESCE(SUM(amount_paid), 0) 
            FROM obligation_payments_history 
            WHERE date >= date('now', '-7 days', 'localtime')
        """).fetchone()[0]
        
        # 5. Weekly Net Profit = Revenue - (COGS + Business Expenses + Obligations Paid)
        weekly_net_profit = weekly_revenue - (weekly_cogs + weekly_business_expenses + weekly_obligations_paid)
        
        # 6. Weekly Personal Draws
        weekly_personal_draws = c.execute("""
            SELECT COALESCE(SUM(amount), 0) 
            FROM transactions 
            WHERE type = 'Expense' 
            AND expense_type = 'Personal' 
            AND date >= date('now', '-7 days', 'localtime')
        """).fetchone()[0]
        
        return {
            "success": True,
            "weekly_revenue": float(weekly_revenue),
            "weekly_cogs": float(weekly_cogs),
            "weekly_business_expenses": float(weekly_business_expenses),
            "weekly_obligations_paid": float(weekly_obligations_paid),
            "weekly_net_profit": float(weekly_net_profit),
            "weekly_personal_draws": float(weekly_personal_draws)
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "weekly_revenue": 0.0,
            "weekly_cogs": 0.0,
            "weekly_business_expenses": 0.0,
            "weekly_obligations_paid": 0.0,
            "weekly_net_profit": 0.0,
            "weekly_personal_draws": 0.0
        }
    finally:
        conn.close()
