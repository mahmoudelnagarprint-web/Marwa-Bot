import sqlite3
import shutil
import os

DB_NAME = "pos_data.db"
BACKUP_NAME = "pos_data_backup_before_reset.db"

def reset():
    if not os.path.exists(DB_NAME):
        print(f"Error: {DB_NAME} not found.")
        return

    # 1. Backup
    print(f"Creating backup: {BACKUP_NAME}...")
    shutil.copy2(DB_NAME, BACKUP_NAME)

    # 2. Connect
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    try:
        print("Resetting order_items...")
        c.execute("DELETE FROM order_items")
        
        print("Resetting orders...")
        c.execute("DELETE FROM orders")
        
        print("Resetting transactions...")
        c.execute("DELETE FROM transactions")
        
        print("Resetting client balances to 0...")
        c.execute("UPDATE clients SET balance = 0")
        
        print("Resetting production_tasks...")
        c.execute("DELETE FROM production_tasks")

        print("Resetting payroll_transactions (if exists)...")
        try:
            c.execute("DELETE FROM payroll_transactions")
        except:
            pass

        conn.commit()
        print("\n✅ Reset completed successfully!")
        
        # Verification counts
        clients_count = c.execute("SELECT COUNT(*) FROM clients").fetchone()[0]
        products_count = c.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        orders_count = c.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
        
        print(f"Clients preserved: {clients_count}")
        print(f"Products preserved: {products_count}")
        print(f"Orders remaining: {orders_count}")

    except Exception as e:
        conn.rollback()
        print(f"Error during reset: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    reset()
