import sqlite3
from datetime import datetime
import database

def reset_drawer():
    print("Initializing database schema...")
    database.init_db()
    
    db_path = "pos_data.db"
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    try:
        # Calculate global income (Revenue / payment)
        income = c.execute("""
            SELECT COALESCE(SUM(amount), 0) 
            FROM transactions 
            WHERE type IN ('Income', 'payment')
        """).fetchone()[0]
        
        # Calculate global expenses
        expense = c.execute("""
            SELECT COALESCE(SUM(amount), 0) 
            FROM transactions 
            WHERE type = 'Expense'
        """).fetchone()[0]
        
        global_balance = income - expense
        print(f"Global treasury balance (Income: {income}, Expense: {expense}): {global_balance} EGP")
        
        if global_balance <= 0:
            print("Global drawer balance is already 0.00 or negative. No reset needed.")
        else:
            # Insert a single Expense transaction to zero out the drawer globally
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            c.execute("""
                INSERT INTO transactions (client_id, type, category, amount, notes, user, related_ref, date, expense_type)
                VALUES (NULL, 'Expense', 'Adjustment', ?, 'تصفية الدرج وتهيئة النظام الجديد', 'System', 'Soft Reset', ?, 'Business')
            """, (global_balance, now_str))
            
            conn.commit()
            print(f"Successfully inserted an adjustment Expense of {global_balance} EGP to zero out the global drawer.")
            
    except Exception as e:
        conn.rollback()
        print(f"Error resetting drawer: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    reset_drawer()
