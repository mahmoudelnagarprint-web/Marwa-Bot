import sqlite3
import os
import shutil
import time
import gc

DB_NAME = "pos_data.db"


def _log_best_effort_sheet_sync(message):
    try:
        from google_sheet_realtime_sync import log_local
        log_local("error", message)
    except Exception:
        try:
            with open("google_sheets_sync.log", "a", encoding="utf-8") as fh:
                fh.write(message + "\n")
        except Exception:
            pass


def _schedule_best_effort_sheet_sync(order_id):
    try:
        from google_sheet_realtime_sync import schedule_order_sync
        schedule_order_sync(order_id)
    except Exception as exc:
        _log_best_effort_sheet_sync(f"Failed to schedule Google Sheet sync for order #{order_id}: {exc}")

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    
    # 1. Settings Table
    c.execute('''CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )''')
    
    # 2. Clients Table
    c.execute('''CREATE TABLE IF NOT EXISTS clients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phone TEXT,
        type TEXT DEFAULT 'Retail',
        balance REAL DEFAULT 0,
        notes TEXT
    )''')
    
    # 3. Products Table
    c.execute('''CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        category TEXT,
        price_wholesale REAL DEFAULT 0,
        price_retail REAL DEFAULT 0,
        stock_qty INTEGER DEFAULT 0,
        sort_order INTEGER DEFAULT 0
    )''')
    
    # 4. Orders Table
    c.execute('''CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id INTEGER,
        total_amount REAL,
        status TEXT,
        date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        delivery_date TEXT,
        local_image_path TEXT,
        FOREIGN KEY (client_id) REFERENCES clients (id)
    )''')
    
    # Migrations
    try: c.execute("ALTER TABLE products ADD COLUMN sort_order INTEGER DEFAULT 0")
    except: pass
    try: c.execute("ALTER TABLE orders ADD COLUMN status TEXT DEFAULT 'Under Preparation'")
    except: pass
    try: c.execute("ALTER TABLE orders ADD COLUMN delivery_date TEXT")
    except: pass
    try: c.execute("ALTER TABLE orders ADD COLUMN local_image_path TEXT")
    except: pass
    try: c.execute("ALTER TABLE orders ADD COLUMN notes TEXT")
    except: pass
    try: c.execute("ALTER TABLE products ADD COLUMN last_cost_price REAL DEFAULT 0")
    except: pass
    
    # Migrations for Financial Module
    try: c.execute("ALTER TABLE transactions ADD COLUMN category TEXT")
    except: pass
    try: c.execute("ALTER TABLE transactions ADD COLUMN user TEXT")
    except: pass
    try: c.execute("ALTER TABLE transactions ADD COLUMN related_ref TEXT")
    except: pass
    try: c.execute("ALTER TABLE transactions ADD COLUMN is_verified INTEGER DEFAULT 0")
    except: pass
    try: c.execute("ALTER TABLE transactions ADD COLUMN is_savings INTEGER DEFAULT 0")
    except: pass

    # Migrations for Staff Module
    try: c.execute('''CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        description TEXT,
        assigned_to TEXT,
        product_id INTEGER,
        image_path TEXT,
        status TEXT DEFAULT 'pending', 
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        completed_at TIMESTAMP
    )''')
    except: pass

    try: c.execute('''CREATE TABLE IF NOT EXISTS chat_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender TEXT,
        message TEXT,
        image_path TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    except: pass

    try: c.execute('''CREATE TABLE IF NOT EXISTS staff_calls (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        caller TEXT,
        target TEXT,
        type TEXT DEFAULT 'summon',
        status TEXT DEFAULT 'active',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    except: pass

    # 17. Obligations Table (New)
    c.execute('''CREATE TABLE IF NOT EXISTS obligations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        expected_amount REAL,
        due_day INTEGER, -- 1 to 31
        last_paid_date TEXT, -- YYYY-MM-DD
        active INTEGER DEFAULT 1
    )''')
    
    # 5. Transactions Table
    c.execute('''CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id INTEGER,
        type TEXT, -- 'payment', 'debt', 'order'
        amount REAL,
        notes TEXT,
        date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        category TEXT,
        user TEXT,
        related_ref TEXT,
        is_verified INTEGER DEFAULT 0,
        is_savings INTEGER DEFAULT 0,
        FOREIGN KEY (client_id) REFERENCES clients (id)
    )''')

    # 6. Tasks Table (New)
    c.execute('''CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        description TEXT,
        assigned_to TEXT,
        product_id INTEGER,
        image_path TEXT,
        status TEXT DEFAULT 'pending', -- pending, done
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        completed_at TIMESTAMP
    )''')

    # 7. Chat Messages Table (New)
    c.execute('''CREATE TABLE IF NOT EXISTS chat_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender TEXT,
        message TEXT,
        image_path TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # 8. Staff Calls Table (New)
    c.execute('''CREATE TABLE IF NOT EXISTS staff_calls (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        caller TEXT,
        target TEXT,
        type TEXT DEFAULT 'summon',
        status TEXT DEFAULT 'active', -- active, resolved
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # 6. Order Items Table
    c.execute('''CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER,
        product_id INTEGER,
        product_name TEXT,
        qty INTEGER,
        price REAL,
        total REAL,
        FOREIGN KEY (order_id) REFERENCES orders (id)
    )''')
    
    # 7. Purchase Invoices Table
    c.execute('''CREATE TABLE IF NOT EXISTS purchase_invoices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        supplier_id INTEGER,
        supplier_name TEXT,
        total_cost REAL DEFAULT 0,
        status TEXT DEFAULT 'Pending',
        date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        notes TEXT
    )''')

    # 8. Purchase Items Table
    c.execute('''CREATE TABLE IF NOT EXISTS purchase_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        invoice_id INTEGER,
        product_id INTEGER,
        product_name TEXT,
        qty INTEGER,
        cost_price REAL,
        total REAL,
        FOREIGN KEY (invoice_id) REFERENCES purchase_invoices (id)
    )''')
    
    # 9. File Movement Logs (Undo Engine)
    c.execute('''CREATE TABLE IF NOT EXISTS file_movement_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER,
        previous_path TEXT,
        new_stage TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (order_id) REFERENCES orders (id)
    )''')
    
    # 10. Categories Table (New)
    c.execute('''CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL
    )''')

    # 11. Staff Table
    c.execute('''CREATE TABLE IF NOT EXISTS staff (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        role TEXT DEFAULT 'Employee', -- 'Admin', 'Employee', 'Manager'
        photo_path TEXT,
        pin_hash TEXT,
        base_salary REAL DEFAULT 0,
        commission_rate REAL DEFAULT 0,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # 12. Attendance Table
    c.execute('''CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        staff_id INTEGER,
        date TEXT, -- YYYY-MM-DD
        check_in TEXT, -- ISO Timestamp
        check_out TEXT, -- ISO Timestamp
        status TEXT DEFAULT 'Absent', -- 'Present', 'Late', 'Absent', 'Leave'
        FOREIGN KEY (staff_id) REFERENCES staff (id)
    )''')
    
    # 13. Payroll Transactions (Ledger for Staff)
    c.execute('''CREATE TABLE IF NOT EXISTS payroll_transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        staff_id INTEGER,
        type TEXT, -- 'Bonus', 'Deduction', 'Payout', 'Commission'
        amount REAL,
        reason TEXT,
        date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        created_by TEXT,
        FOREIGN KEY (staff_id) REFERENCES staff (id)
    )''')

    # 14. Requests Table
    c.execute('''CREATE TABLE IF NOT EXISTS requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        staff_id INTEGER,
        type TEXT, -- 'Loan', 'Leave', 'Complaint'
        details TEXT,
        status TEXT DEFAULT 'Pending', -- 'Pending', 'Approved', 'Rejected'
        date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (staff_id) REFERENCES staff (id)
    )''')

    # 15. Chat Messages
    c.execute('''CREATE TABLE IF NOT EXISTS chat_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender_id INTEGER, -- NULL for System/Admin broadcast
        recipient_id INTEGER, -- NULL for Broadcast
        message TEXT,
        image_path TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_read INTEGER DEFAULT 0
    )''')

    # 16. Security Tokens (For QR)
    c.execute('''CREATE TABLE IF NOT EXISTS security_tokens (
        token TEXT PRIMARY KEY,
        expires_at TIMESTAMP
    )''')

    # 17. SPECIAL LOG FOR OPERATIONS (User Request for Undo Compatibility)
    c.execute('''CREATE TABLE IF NOT EXISTS operation_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER,
        old_status TEXT,
        new_status TEXT,
        user TEXT, -- (Optional) if we track who did it
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (order_id) REFERENCES orders (id)
    )''')

    # 18. Production Tasks Table (Laser Ops Center)
    c.execute('''CREATE TABLE IF NOT EXISTS production_tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT DEFAULT 'manual',
        reference_image TEXT,
        quantity INTEGER DEFAULT 1,
        status TEXT DEFAULT 'pending',
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        completed_at TIMESTAMP
    )''')

    # 20. Daily Financial Archive (New ERP)
    c.execute('''CREATE TABLE IF NOT EXISTS daily_financial_archive (
        date TEXT PRIMARY KEY,
        total_cash REAL,
        total_profit REAL,
        total_expenses REAL
    )''')

    # 21. Scheduled Obligations (Smart Obligations)
    c.execute('''CREATE TABLE IF NOT EXISTS scheduled_obligations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        total_monthly_amount REAL,
        weekly_deduction_target REAL,
        accumulated_amount REAL DEFAULT 0,
        next_due_date TEXT,
        is_recurring INTEGER DEFAULT 1,
        daily_target_amount REAL DEFAULT 0,
        weekly_target_amount REAL DEFAULT 0,
        paid_days INTEGER DEFAULT 0,
        paid_weeks INTEGER DEFAULT 0
    )''')

    # 22. Shortages (Low Stock & Materials Needed)
    c.execute('''CREATE TABLE IF NOT EXISTS shortages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        estimated_cost REAL,
        qty INTEGER DEFAULT 1,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # 23. Daily Shifts (Evolved POS)
    c.execute('''CREATE TABLE IF NOT EXISTS daily_shifts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        opened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        closed_at TIMESTAMP,
        total_revenue REAL DEFAULT 0,
        total_cost REAL DEFAULT 0,
        net_profit REAL DEFAULT 0,
        status TEXT DEFAULT 'open'
    )''')

    # Column upgrades with safety checks
    try: c.execute("ALTER TABLE transactions ADD COLUMN material_cost_recovery REAL DEFAULT 0")
    except: pass
    try: c.execute("ALTER TABLE transactions ADD COLUMN net_profit_portion REAL DEFAULT 0")
    except: pass

    try: c.execute("ALTER TABLE scheduled_obligations ADD COLUMN is_recurring INTEGER DEFAULT 1")
    except: pass
    try: c.execute("ALTER TABLE scheduled_obligations ADD COLUMN daily_target_amount REAL DEFAULT 0")
    except: pass
    try: c.execute("ALTER TABLE scheduled_obligations ADD COLUMN weekly_target_amount REAL DEFAULT 0")
    except: pass
    try: c.execute("ALTER TABLE scheduled_obligations ADD COLUMN paid_days INTEGER DEFAULT 0")
    except: pass
    try: c.execute("ALTER TABLE scheduled_obligations ADD COLUMN paid_weeks INTEGER DEFAULT 0")
    except: pass

    # 24. Obligation Payments History
    c.execute('''CREATE TABLE IF NOT EXISTS obligation_payments_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ob_id INTEGER,
        amount_paid REAL,
        payment_type TEXT, -- 'daily', 'weekly'
        date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (ob_id) REFERENCES scheduled_obligations (id) ON DELETE CASCADE
    )''')

    try: c.execute("ALTER TABLE transactions ADD COLUMN expense_type TEXT DEFAULT 'Business'")
    except: pass

    # Auto-Open Shift Hook
    try:
        active_shift = c.execute("SELECT id FROM daily_shifts WHERE status = 'open'").fetchone()
        if not active_shift:
            c.execute("INSERT INTO daily_shifts (status) VALUES ('open')")
    except:
        pass
    
    conn.commit()

    # --- Migration: Populate Categories from Products ---
    # Check if categories table is empty
    cat_count = conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
    if cat_count == 0:
        print("🔄 Migrating Categories from Products...")
        # Get distinct categories from products
        existing_cats = conn.execute("SELECT DISTINCT category FROM products WHERE category IS NOT NULL AND category != ''").fetchall()
        for row in existing_cats:
            cat_name = row['category']
            try:
                conn.execute("INSERT OR IGNORE INTO categories (name) VALUES (?)", (cat_name,))
            except:
                pass
        conn.commit()
    
    # --- End Migration ---
    
    # Seeding
    cur = conn.execute("SELECT COUNT(*) FROM products")
    if cur.fetchone()[0] == 0:
        print("🌱 Seeding Initial Products...")
        initial_products = [
            ('بصمة قلب أكريليك كاملة', 'أكريليك/هدايا', 250, 300, 0),
            ('طقم سبوع', 'هدايا مناسبات', 260, 300, 0),
            ('بوكس حرف', 'بوكسات/خشب', 160, 170, 0),
            ('مبخرة أكريليك', 'أكريليك/ديكور', 200, 250, 0),
            ('مبخرة استاند', 'أكريليك/ديكور', 170, 200, 0),
            ('طارة خشب', 'خشب/ديكور', 100, 130, 0),
            ('ساعة ديكور حائط', 'ديكور', 200, 259, 0),
            ('مرايا سحرية', 'ديكور/مرايا', 160, 0, 0),
            ('مج عادي', 'مجات', 60, 100, 0),
            ('مج ديجيتال', 'مجات', 140, 0, 0),
            ('مج سحري', 'مجات', 120, 0, 0),
            ('سلسلة ذهبي', 'اكسسوارات', 60, 90, 0),
            ('محفظة', 'اكسسوارات/جلد', 130, 0, 0),
            ('محفظة سبشيال', 'اكسسوارات/جلد', 150, 190, 0),
            ('نوتبوك', 'قرطاسية', 65, 85, 0),
            ('قلم مضيء', 'قرطاسية', 40, 50, 0),
            ('ديكور مطبخ', 'ديكور', 120, 150, 0),
            ('علاقة مفاتيح دائرية', 'اكسسوارات', 85, 100, 0),
            ('طباعة استيكر', 'طباعة', 200, 270, 0),
            ('تاج نيم مكتب خشب ذهبي', 'خشب/ديكور', 270, 0, 0),
            ('بوكس خشب', 'بوكسات/خشب', 180, 0, 0),
            ('بوكس أكريليك', 'بوكسات/أكريليك', 0, 100, 0),
            ('قطعة أكريليك', 'خامات', 0, 60, 0),
            ('دلاية سبحة', 'اكسسوارات', 2, 2, 0),
            ('طباعة 30×40 (طباعة فقط)', 'طباعة', 45, 0, 0),
            ('أسماء خشب (للقطعة)', 'خشب/أسماء', 10, 10, 0),
            ('يد هواية فضي', 'اكسسوارات', 60, 0, 0),
            ('بروش', 'اكسسوارات', 45, 50, 0),
            ('صينية سحابة', 'ديكور/صواني', 207, 370, 0),
            ('تابلو 30×40', 'تابلوهات', 95, 120, 0),
            ('برواز 20×30', 'تابلوهات', 85, 110, 0),
            ('برواز 30×40', 'تابلوهات', 95, 120, 0),
            ('أكريليك أبيض', 'خامات', 100, 0, 0),
            ('تابلو 10x15', 'تابلوهات', 30, 40, 0),
            ('تابلو 15x21', 'تابلوهات', 40, 50, 0),
            ('تابلو 20x30', 'تابلوهات', 65, 70, 0),
            ('تابلو 30x40', 'تابلوهات', 100, 130, 0),
            ('تابلو 40x50', 'تابلوهات', 160, 230, 0),
            ('تابلو 60x50', 'تابلوهات', 230, 270, 0),
            ('تابلو 60x70', 'تابلوهات', 300, 360, 0)
        ]
        c.executemany("INSERT INTO products (name, category, price_wholesale, price_retail, stock_qty) VALUES (?, ?, ?, ?, ?)", initial_products)
        conn.commit()
    
    conn.close()
    print("[OK] Database Initialized Successfully.")

# --- Settings ---
def save_setting(key, value):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

def get_setting(key):
    conn = get_db_connection()
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row['value'] if row else ""

# --- Clients Logic ---
def get_all_clients():
    conn = get_db_connection()
    clients = conn.execute("SELECT * FROM clients ORDER BY name ASC").fetchall()
    
    clients_list = []
    for c in clients:
        c_dict = dict(c)
        # Add Under Prep Value to Balance for Display
        c_dict['balance'] = (c_dict['balance'] or 0)
        clients_list.append(c_dict)
        
    conn.close()
    return clients_list



def update_client_balance(client_id, amount, note="Payment"):
    """Update client balance and log transaction."""
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("UPDATE clients SET balance = balance - ? WHERE id=?", (amount, client_id))
        c.execute("INSERT INTO transactions (client_id, type, amount, notes) VALUES (?, 'Payment', ?, ?)", 
                  (client_id, amount, note))
        conn.commit()
        return True
    except:
        conn.rollback()
        return False
    finally:
        conn.close()

def get_all_products(category=None):
    conn = get_db_connection()
    query = "SELECT * FROM products"
    params = []
    if category and category != "All":
        query += " WHERE category = ?"
        params.append(category)
    query += " ORDER BY sort_order ASC, name ASC"
    
    products = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(p) for p in products]

# --- Kanban Board Functions ---
def get_kanban_orders():
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute("""
        SELECT o.id, o.client_id, c.name as client_name, c.phone as client_phone, 
               o.total_amount, o.status, o.date, o.delivery_date, o.local_image_path, o.notes
        FROM orders o
        LEFT JOIN clients c ON o.client_id = c.id
        WHERE o.status IN ('Under Preparation', 'Ready', 'Delivered') 
        ORDER BY o.date DESC LIMIT 100
    """)
    orders = [dict(row) for row in c.fetchall()]
    
    for o in orders:
        items = c.execute("""
            SELECT oi.product_name, oi.qty, p.category 
            FROM order_items oi
            LEFT JOIN products p ON oi.product_id = p.id
            WHERE oi.order_id = ?
        """, (o['id'],)).fetchall()
        o['items'] = [dict(i) for i in items]
        
        client = c.execute("SELECT balance FROM clients WHERE id = ?", (o['client_id'],)).fetchone()
        o['client_balance'] = client['balance'] if client else 0

    conn.close()
    return orders

def update_order_status(order_id, new_status, payment=0, method=None):
    conn = get_db_connection()
    c = conn.cursor()
    try:
        # Get Old Status for Logging
        prev = c.execute("SELECT status FROM orders WHERE id=?", (order_id,)).fetchone()
        old_status = prev['status'] if prev else "Unknown"

        # Update Status
        c.execute("UPDATE orders SET status = ? WHERE id = ?", (new_status, order_id))
        
        # Log to Operation Logs
        c.execute("INSERT INTO operation_logs (order_id, old_status, new_status, user) VALUES (?, ?, ?, 'System')", (order_id, old_status, new_status))
        
        # --- File System Management ---
        try:
            manage_file_system(order_id, 'move', new_status)
        except Exception as file_err:
            print(f"FileSystem Warning: {file_err}")
        
        # If Delivering and Payment is involved
        if new_status == 'Delivered' and payment > 0:
            oid = c.execute("SELECT client_id FROM orders WHERE id = ?", (order_id,)).fetchone()
            if oid:
                client_id = oid['client_id']
                client_id = oid['client_id']
                # UPDATED: Auto-Sync for Delivery Payment
                c.execute("""
                    INSERT INTO transactions (client_id, type, category, amount, notes, user, related_ref) 
                    VALUES (?, 'Income', 'Sales', ?, ?, 'System', ?)
                """, (client_id, payment, f"Delivery Order #{order_id} - {method}", f"Order #{order_id}"))
                
                c.execute("UPDATE clients SET balance = balance - ? WHERE id = ?", (payment, client_id))
        
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        return str(e)
    finally:
        conn.close()

def get_order_images(order_id):
    conn = get_db_connection()
    row = conn.execute("SELECT local_image_path FROM orders WHERE id = ?", (order_id,)).fetchone()
    conn.close()
    
    paths = []
    if row and row['local_image_path'] and os.path.exists(row['local_image_path']):
        folder = row['local_image_path']
        if os.path.isdir(folder):
            for f in os.listdir(folder):
                if f.lower().endswith(('.png', '.jpg', '.jpeg')):
                    paths.append(os.path.join(folder, f))
        elif os.path.isfile(folder): 
             # If path points to file (should be folder in new logic, but robust fallback)
             pass
    
    return paths  

def add_new_client(name, phone, c_type, notes):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO clients (name, phone, type, notes) VALUES (?, ?, ?, ?)", 
              (name, phone, c_type, notes))
    new_id = c.lastrowid
    conn.commit()
    conn.close()
    return new_id

def update_client_transaction(client_id, amount, t_type, notes, material_cost_recovery=0.0, net_profit_portion=0.0):
    conn = get_db_connection()
    c = conn.cursor()
    
    # Financial Logic:
    # Payment -> 'Income' (Debt Collection)
    # Debt/Order -> just affects balance, not a cash transaction unless paid.
    
    cat = 'Debt Collection' if t_type == 'payment' else 'General'
    fin_type = 'Income' if t_type == 'payment' else 'Log' 
    
    # If it's a 'debt' transaction (adding debt), it's not cash flow. It's just balance update.
    # The 'transactions' table is now being used for BOTH Client Balance Log AND Cash Treasury.
    # This might be mixed. Let's respect the user's "Strict" request.
    # We should distinguish: 
    # - Cash Flow (Income/Expense) -> affects Treasury
    # - Non-Cash Flow (Credit) -> affects Client Balance but NOT Treasury
    
    # Current design: transactions table IS the ledger.
    # So we must be careful.
    # t_type: 'payment', 'debt', 'order'
    
    real_type = 'Income' if t_type == 'payment' else t_type
    
    c.execute("""
        INSERT INTO transactions (client_id, type, category, amount, notes, user, related_ref, material_cost_recovery, net_profit_portion) 
        VALUES (?, ?, ?, ?, ?, 'System', 'Client Balance', ?, ?)
    """, (client_id, real_type, cat, amount, notes, material_cost_recovery, net_profit_portion))
    
    if t_type == 'payment':
        c.execute("UPDATE clients SET balance = balance - ? WHERE id = ?", (amount, client_id))
    elif t_type in ['debt', 'order']:
        c.execute("UPDATE clients SET balance = balance + ? WHERE id = ?", (amount, client_id))
        
    conn.commit()
    conn.close()

# 2026-10-12 fix (owner order): payments are stored as type='Income' (see
# update_client_transaction); 'payment' kept for legacy rows only.
def get_last_client_payments(client_id):
    conn = get_db_connection()
    c = conn.cursor()
    payments = c.execute("""
        SELECT * FROM transactions 
        WHERE client_id = ? AND type IN ('payment', 'Income') 
        ORDER BY date DESC LIMIT 5
    """, (client_id,)).fetchall()
    conn.close()
    return [dict(p) for p in payments]

def get_client_statement_data(client_id):
    conn = get_db_connection()
    c = conn.cursor()
    
    # 1. Client Info
    client = dict(conn.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone())
    
    # 2. Transactions (Payments & Manual Debts)
    trans = conn.execute("SELECT * FROM transactions WHERE client_id = ? ORDER BY date DESC", (client_id,)).fetchall()
    
    # 3. Orders (Detailed)
    orders = []
    # Fetch orders for this client
    client_orders = conn.execute("SELECT * FROM orders WHERE client_id = ? ORDER BY date DESC", (client_id,)).fetchall()
    
    for o in client_orders:
        o_dict = dict(o)
        # Fetch Items for this order
        items = conn.execute("SELECT * FROM order_items WHERE order_id = ?", (o['id'],)).fetchall()
        o_dict['items'] = [dict(i) for i in items]
        orders.append(o_dict)

    # 4. Summaries
    # Last Payment Info
    last_pay_row = conn.execute("SELECT amount, date FROM transactions WHERE client_id = ? AND type IN ('payment', 'Income') ORDER BY date DESC LIMIT 1", (client_id,)).fetchone()
    last_payment = {
        'amount': last_pay_row['amount'] if last_pay_row else 0,
        'date': last_pay_row['date'] if last_pay_row else None
    }
    
    # Total Lifetime Paid (Sum)
    total_lifetime_paid = conn.execute("SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE client_id = ? AND type IN ('payment', 'Income')", (client_id,)).fetchone()[0]

    # Total Sales (Lifetime Value)
    sum_orders = conn.execute("SELECT SUM(total_amount) FROM orders WHERE client_id = ?", (client_id,)).fetchone()[0] or 0
    # Under Preparation & Ready Values (Breakdown)
    prep_val = conn.execute("SELECT SUM(total_amount) FROM orders WHERE client_id = ? AND status = 'Under Preparation'", (client_id,)).fetchone()[0] or 0
    ready_val = conn.execute("SELECT SUM(total_amount) FROM orders WHERE client_id = ? AND status = 'Ready'", (client_id,)).fetchone()[0] or 0
    
    manual_debt_val = conn.execute("""
        SELECT SUM(amount) FROM transactions 
        WHERE client_id = ? AND type = 'debt'
        AND (notes IS NULL OR notes NOT LIKE '%Order #%')
        AND (related_ref IS NULL OR related_ref NOT LIKE '%Order #%')
    """, (client_id,)).fetchone()[0] or 0

    
    # Calculate total_sales
    total_sales = sum_orders + manual_debt_val
    
    # Calculate "other debt"
    balance = client['balance'] or 0
    other_debt = balance - prep_val - ready_val
    
    # --- 5. Strict Grouping Logic (User Request) ---
    # Fetch all items with their order status
    raw_mixed_items = conn.execute("""
        SELECT i.product_name, i.qty, i.total, o.status, o.id as order_id, o.date
        FROM order_items i
        JOIN orders o ON i.order_id = o.id
        WHERE o.client_id = ?
        ORDER BY o.date DESC
    """, (client_id,)).fetchall()
    
    grouped_map = {}
    for r in raw_mixed_items:
        # Calculate unit price safely
        qty = r['qty'] or 1
        total = r['total'] or 0
        unit_price = round(total / qty, 2)
        
        # Key: Name + Price + Status
        key = (r['product_name'], unit_price, r['status'])
        
        if key not in grouped_map:
            grouped_map[key] = {
                'product_name': r['product_name'],
                'unit_price': unit_price,
                'qty': 0,
                'total': 0,
                'status': r['status'],
                'ids': [],
                'last_date': r['date']
            }
            
        g = grouped_map[key]
        g['qty'] += qty
        g['total'] += total
        g['ids'].append(str(r['order_id']))
        # Keep the most recent date
        if r['date'] > g['last_date']: g['last_date'] = r['date']

    # Organize into categories
    structured_groups = {
        'under_prep': [],
        'ready': [],
        'delivered': []
    }
    
    for item in grouped_map.values():
        if item['status'] == 'Under Preparation':
            structured_groups['under_prep'].append(item)
        elif item['status'] == 'Ready':
            structured_groups['ready'].append(item)
        else:
            structured_groups['delivered'].append(item)
            
    # Sort each list by date descending
    for key in structured_groups:
        structured_groups[key].sort(key=lambda x: x['last_date'], reverse=True)

    conn.close()
    
    return {
        "client": client,
        "transactions": [dict(t) for t in trans],
        "orders": orders,
        "summary": {
            "total_debt": balance,
            "total_paid": total_lifetime_paid,
            "last_payment_date": last_payment['date'],
            "last_payment_amount": last_payment['amount'],
            "processing_debt": prep_val,
            "executed_debt": ready_val,
            "other_debt": other_debt,
            "total_sales": total_sales
        },
        "grouped_items": structured_groups
    }

# --- STAFF MODULE FUNCTIONS ---

def add_task(title, desc, assigned_to, product_id=None, image_path=None):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''INSERT INTO tasks (title, description, assigned_to, product_id, image_path, status) 
                 VALUES (?, ?, ?, ?, ?, 'pending')''', 
                 (title, desc, assigned_to, product_id, image_path))
    conn.commit()
    conn.close()
    return True

def get_tasks(staff_name=None):
    conn = get_db_connection()
    c = conn.cursor()
    if staff_name:
        tasks = c.execute("SELECT * FROM tasks WHERE assigned_to = ? OR assigned_to = 'All' ORDER BY created_at DESC", (staff_name,)).fetchall()
    else:
        tasks = c.execute("SELECT * FROM tasks ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(t) for t in tasks]

def update_task_status(task_id, status):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE tasks SET status = ?, completed_at = CURRENT_TIMESTAMP WHERE id = ?", (status, task_id))
    conn.commit()
    conn.close()
    return True

def update_batch_order_status(order_ids_str, new_status, payment=0, method=None):
    """
    Updates status for multiple order IDs (comma separated string).
    Leverages existing update_order_status for each ID to ensure consistency.
    """
    if not order_ids_str: return False
    
    ids = [x.strip() for x in order_ids_str.split(',') if x.strip()]
    errors = []
    
    for oid in ids:
        res = update_order_status(oid, new_status, payment, method)
        if res is not True:
            errors.append(f"Order {oid}: {res}")
            
    if errors:
        return {"success": False, "error": ", ".join(errors)}
    return {"success": True}


def add_chat_message(sender, message, image_path=None):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO chat_messages (sender, message, image_path) VALUES (?, ?, ?)", (sender, message, image_path))
    conn.commit()
    conn.close()
    return True

def get_chat_messages(limit=50):
    conn = get_db_connection()
    c = conn.cursor()
    msgs = c.execute("SELECT * FROM chat_messages ORDER BY timestamp DESC LIMIT ?", (limit,)).fetchall()
    conn.close()
    return [dict(m) for m in msgs][::-1] 

def add_staff_call(caller, target, call_type='summon'):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO staff_calls (caller, target, type) VALUES (?, ?, ?)", (caller, target, call_type))
    conn.commit()
    conn.close()
    return True

def get_active_staff_calls(target_user=None):
    conn = get_db_connection()
    c = conn.cursor()
    calls = c.execute("SELECT * FROM staff_calls WHERE status = 'active' AND (target = ? OR target = 'all') ORDER BY created_at ASC", (target_user,)).fetchall()
    conn.close()
    return [dict(c) for c in calls]

def resolve_staff_call(call_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE staff_calls SET status = 'resolved' WHERE id = ?", (call_id,))
    conn.commit()
    conn.close()
    return True

# --- LASER OPS CENTER FUNCTIONS ---

def get_laser_queue_summary():
    """
    Returns a summary of products in 'Under Preparation' orders.
    Aggregates by product name.
    """
    conn = get_db_connection()
    c = conn.cursor()
    
    # We join order_items with orders to filter by status
    # We group by product_name to get total quantity needed
    query = """
        SELECT 
            oi.product_name,
            SUM(oi.qty) as total_qty,
            COUNT(DISTINCT o.id) as order_count
        FROM order_items oi
        JOIN orders o ON oi.order_id = o.id
        WHERE o.status = 'Under Preparation'
        GROUP BY oi.product_name
        ORDER BY total_qty DESC
    """
    
    rows = c.execute(query).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_active_laser_tasks():
    """
    Returns all pending manual tasks/images.
    """
    conn = get_db_connection()
    c = conn.cursor()
    tasks = c.execute("SELECT * FROM production_tasks WHERE status = 'pending' ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(t) for t in tasks]

def add_production_task(notes, image_filename=None, quantity=1, task_type='manual'):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO production_tasks (type, reference_image, quantity, status, notes)
        VALUES (?, ?, ?, 'pending', ?)
    """, (task_type, image_filename, quantity, notes))
    conn.commit()
    conn.close()
    return True

def complete_production_task(task_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE production_tasks SET status = 'completed', completed_at = CURRENT_TIMESTAMP WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()
    return True

def get_production_summary():
    conn = get_db_connection()
    c = conn.cursor()
    query = '''
        SELECT 
            p.name as product_name,
            p.id as product_id,
            SUM(oi.qty) as total_qty
        FROM order_items oi
        JOIN orders o ON oi.order_id = o.id
        JOIN products p ON oi.product_id = p.id
        WHERE o.status = 'Under Preparation'
        GROUP BY p.id
        HAVING total_qty > 0
    '''
    rows = c.execute(query).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def decrement_production_item(product_id, qty_to_remove=1):
    conn = get_db_connection()
    c = conn.cursor()
    items_query = '''
        SELECT oi.id, oi.qty, oi.order_id 
        FROM order_items oi
        JOIN orders o ON oi.order_id = o.id
        WHERE o.status = 'Under Preparation' AND oi.product_id = ?
        ORDER BY o.date ASC
    '''
    items = c.execute(items_query, (product_id,)).fetchall()
    
    remaining_to_remove = int(qty_to_remove)
    
    for item in items:
        if remaining_to_remove <= 0: break
        
        item_id = item['id']
        current_qty = item['qty']
        
        if current_qty > remaining_to_remove:
            new_qty = current_qty - remaining_to_remove
            c.execute("UPDATE order_items SET qty = ? WHERE id = ?", (new_qty, item_id))
            remaining_to_remove = 0
        else:
            c.execute("DELETE FROM order_items WHERE id = ?", (item_id,))
            remaining_to_remove -= current_qty
            
    conn.commit()
    conn.close()
    return True

def clear_old_debt(client_id):
    """
    Clear old/delivered debt by setting balance = (Under Preparation + Ready) orders only.
    This removes 'مسلم/قديم' debt completely.
    """
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        # Get current balance
        current = c.execute("SELECT balance FROM clients WHERE id = ?", (client_id,)).fetchone()
        old_balance = current['balance'] if current else 0
        
        # Calculate active orders only (Prep + Ready)
        prep_val = c.execute("SELECT SUM(total_amount) FROM orders WHERE client_id = ? AND status = 'Under Preparation'", (client_id,)).fetchone()[0] or 0
        ready_val = c.execute("SELECT SUM(total_amount) FROM orders WHERE client_id = ? AND status = 'Ready'", (client_id,)).fetchone()[0] or 0
        
        new_balance = prep_val + ready_val
        difference = old_balance - new_balance  # Amount being cleared
        
        # Update balance
        c.execute("UPDATE clients SET balance = ? WHERE id = ?", (new_balance, client_id))
        
        # Record the adjustment
        c.execute("""
            INSERT INTO transactions (client_id, type, category, amount, notes, user, related_ref)
            VALUES (?, 'adjustment', 'Balance Reset', ?, ?, 'System', 'Clear Old Debt')
        """, (client_id, difference, f"مسح الديون القديمة/المسلمة. الفرق={difference}"))
        
        conn.commit()
        return {
            'success': True, 
            'old_balance': old_balance, 
            'new_balance': new_balance,
            'cleared': difference
        }
    except Exception as e:
        conn.rollback()
        return {'success': False, 'error': str(e)}
    finally:
        conn.close()

def get_client_financial_breakdown(client_id):
    # Delegate to get_client_statement_data
    return get_client_statement_data(client_id)

def adjust_balance(client_id, new_amount):
    """
    Set a client's balance to an exact value from the manual balance modal.
    The delta is logged in transactions so statements and recalculation logic
    stay compatible with the existing debt/payment model.
    """
    conn = get_db_connection()
    c = conn.cursor()

    try:
        client = c.execute("SELECT balance FROM clients WHERE id = ?", (client_id,)).fetchone()
        if not client:
            return {"success": False, "error": "Client not found"}

        current_balance = float(client["balance"] or 0)
        target_balance = float(new_amount or 0)
        delta = round(target_balance - current_balance, 2)

        if abs(delta) < 0.0001:
            return {
                "success": True,
                "old_balance": current_balance,
                "new_balance": target_balance,
                "changed": 0
            }

        txn_type = 'debt' if delta > 0 else 'payment'
        note = f"Manual balance adjustment: {current_balance} -> {target_balance}"

        c.execute("""
            INSERT INTO transactions (client_id, type, category, amount, notes, user, related_ref)
            VALUES (?, ?, 'Manual Balance Adjustment', ?, ?, 'System', 'Balance Modal')
        """, (client_id, txn_type, abs(delta), note))

        c.execute("UPDATE clients SET balance = ? WHERE id = ?", (target_balance, client_id))

        conn.commit()
        return {
            "success": True,
            "old_balance": current_balance,
            "new_balance": target_balance,
            "changed": delta
        }
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()

def recalculate_client_balance(client_id):
    """
    Audit Function: Re-sums all financial history to fix any balance drift.
    Formula: Balance = (Sum(Orders.net_total) + Sum(ManualDebt)) - Sum(Payments)
    ManualDebt should EXCLUDE system-generated debts linked to Orders to avoid double counting.
    """
    conn = get_db_connection()
    c = conn.cursor()
    try:
        # 1. Sum of Orders (Net Total) - INCLUDE ALL VALID STATUSES
        orders_sum = c.execute("SELECT COALESCE(SUM(total_amount), 0) FROM orders WHERE client_id = ? AND status != 'Cancelled'", (client_id,)).fetchone()[0]
        
        # 2. Sum of Manual Debts (Transactions type='debt')
        # EXCLUDE transactions derived from Orders (notes contain 'Order #' or related_ref contains 'Order #')
        # SQL Filtering (Proven working in force_fix.py step 104)
        debt_sum = c.execute("""
            SELECT COALESCE(SUM(amount), 0) FROM transactions 
            WHERE client_id = ? 
            AND type = 'debt'
            AND (notes IS NULL OR notes NOT LIKE '%Order #%')
            AND (related_ref IS NULL OR related_ref NOT LIKE '%Order #%')
        """, (client_id,)).fetchone()[0]
        
        # 3. Sum of Payments (Transactions type='payment' or 'Income')
        payment_sum = c.execute("SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE client_id = ? AND type IN ('payment', 'Income')", (client_id,)).fetchone()[0]
        
        # 4. Calculate Theoretical Balance
        theo_balance = (orders_sum + debt_sum) - payment_sum
        
        # 5. Update Client
        c.execute("UPDATE clients SET balance = ? WHERE id = ?", (theo_balance, client_id))
        conn.commit()
        
        return {
            'success': True, 
            'new_balance': theo_balance,
            'details': {
                'orders': orders_sum,
                'manual_debt': debt_sum,
                'payments': payment_sum
            }
        }
        
    except Exception as e:
        conn.rollback()
        return {'success': False, 'error': str(e)}
    finally:
        conn.close()

def update_product_details(p_id, name, cat, price_w, price_r, sort_order):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
        UPDATE products 
        SET name=?, category=?, price_wholesale=?, price_retail=?, sort_order=?
        WHERE id=?
    """, (name, cat, price_w, price_r, sort_order, p_id))
    conn.commit()
    conn.commit()
    conn.close()

def update_product_prices(p_id, price_r, price_w):
    """Updates only the pricing of a product."""
    conn = get_db_connection()
    c = conn.cursor()
    # Check if we should update one or both
    if price_r is not None and price_w is not None:
         c.execute("UPDATE products SET price_retail=?, price_wholesale=? WHERE id=?", (price_r, price_w, p_id))
    elif price_r is not None:
         c.execute("UPDATE products SET price_retail=? WHERE id=?", (price_r, p_id))
    elif price_w is not None:
         c.execute("UPDATE products SET price_wholesale=? WHERE id=?", (price_w, p_id))
         
    conn.commit()
    conn.close()

def delete_product(p_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM products WHERE id = ?", (p_id,))
    conn.commit()
    conn.close()

def update_product_stock_db(p_id, qty_change):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE products SET stock_qty = stock_qty + ? WHERE id = ?", (qty_change, p_id))
    conn.commit()
    conn.close()

def update_order_item_from_statement(order_ids, product_name, new_qty, new_price):
    """
    Update Qty/Price for a specific product across one or multiple orders (Batch Update).
    If multiple orders, Price is updated for all.
    Qty is tricky: We will Only update Qty if it's a SINGLE order to avoid ambiguity.
    """
    conn = get_db_connection()
    c = conn.cursor()
    try:
        # Convert IDs list
        if isinstance(order_ids, str):
            order_ids = [int(x) for x in order_ids.split(',') if x]
        
        if not order_ids:
            return {'success': False, 'error': "No orders specified"}

        # 1. Update Price (Apply to ALL)
        for oid in order_ids:
            # Get current item to calc delta for Total
            row = c.execute("SELECT qty FROM order_items WHERE order_id=? AND product_name=?", (oid, product_name)).fetchone()
            if row:
                current_qty = row['qty']
                
                # If Single Order, we might update Qty too
                final_qty = current_qty
                if len(order_ids) == 1 and new_qty is not None:
                     final_qty = float(new_qty)
                
                # Calc new Total
                new_total = final_qty * float(new_price)
                
                # Update Item
                c.execute("""
                    UPDATE order_items 
                    SET price=?, qty=?, total=? 
                    WHERE order_id=? AND product_name=?
                """, (new_price, final_qty, new_total, oid, product_name))
                
                # Update Order Grand Total
                # Recalculate order total from items
                c.execute("""
                    UPDATE orders 
                    SET total_amount = (SELECT SUM(total) FROM order_items WHERE order_id=?)
                    WHERE id=?
                """, (oid, oid))
        
        conn.commit()
        return {'success': True}
        
    except Exception as e:
        conn.rollback()
        return {'success': False, 'error': str(e)}
    finally:
        conn.close()

# --- Category Management ---
def get_all_categories_db():
    conn = get_db_connection()
    cats = conn.execute("SELECT * FROM categories ORDER BY name ASC").fetchall()
    conn.close()
    return [dict(c) for c in cats]

def add_category_db(name):
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO categories (name) VALUES (?)", (name,))
        conn.commit()
        return {"success": True, "id": c.lastrowid}
    except sqlite3.IntegrityError:
        return {"success": False, "error": "Category already exists"}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        conn.close()

def update_category_db(cat_id, new_name):
    conn = get_db_connection()
    c = conn.cursor()
    try:
        # Get old name first
        old_cat = c.execute("SELECT name FROM categories WHERE id=?", (cat_id,)).fetchone()
        if not old_cat: return {"success": False, "error": "Category not found"}
        old_name = old_cat['name']
        
        # Update category table
        c.execute("UPDATE categories SET name=? WHERE id=?", (new_name, cat_id))
        
        # Update associated products
        c.execute("UPDATE products SET category=? WHERE category=?", (new_name, old_name))
        
        conn.commit()
        return {"success": True}
    except sqlite3.IntegrityError:
        return {"success": False, "error": "Name already taken"}
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()

def delete_category_db(cat_id):
    conn = get_db_connection()
    c = conn.cursor()
    try:
        # Get category name
        cat = c.execute("SELECT name FROM categories WHERE id=?", (cat_id,)).fetchone()
        if not cat: return {"success": False, "error": "Category not found"}
        cat_name = cat['name']
        
        # Move products to 'Uncategorized'
        c.execute("UPDATE products SET category='Uncategorized' WHERE category=?", (cat_name,))
        
        # Delete category
        c.execute("DELETE FROM categories WHERE id=?", (cat_id,))
        
        conn.commit()
        return {"success": True}
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()

def infer_category(name):
    name = name.lower()
    if 'فانوس' in name or 'مصحف' in name or 'رمضان' in name:
        return 'رمضان'
    if 'بوكس' in name or 'هدية' in name or 'هدايا' in name:
        return 'هدايا'
    if 'تابلوه' in name or 'برواز' in name:
        return 'تابلوهات'
    if 'ميدال' in name or 'مديلي' in name or 'سلسلة' in name:
        return 'اكسسوارات'
    if 'مج' in name or 'كوب' in name:
        return 'طباعة'
    if 'نوت' in name or 'أجندة' in name:
        return 'طباعة'
    return 'غير مصنف'

def add_quick_product(name, cat, price_r, price_w):
    if not cat or cat.strip() == "":
        cat = infer_category(name)
        
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO products (name, category, price_retail, price_wholesale, stock_qty) VALUES (?, ?, ?, ?, 0)",
              (name, cat, price_r, price_w))
    new_id = c.lastrowid
    conn.commit()
    conn.close()
    return new_id


def resolve_or_create_product_for_external_order(
    product_id=None,
    product_name=None,
    client_type="Retail",
    category=None,
    retail_price=None,
    wholesale_price=None,
    external_price=None,
):
    """
    Future-safe helper for external order importers.
    It resolves by product_id, then exact name, then creates via add_quick_product.
    It never raises for unknown pricing; instead it returns needs_review=True.
    """

    def _to_float(value):
        if value in (None, "", "null"):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    conn = get_db_connection()
    try:
        product = None
        created = False

        if product_id not in (None, "", 0, "0"):
            product = conn.execute(
                """
                SELECT id, name, category, price_wholesale, price_retail,
                       stock_qty, sort_order, stock, last_cost_price
                FROM products
                WHERE id = ?
                """,
                (product_id,),
            ).fetchone()

        if not product and product_name:
            product = conn.execute(
                """
                SELECT id, name, category, price_wholesale, price_retail,
                       stock_qty, sort_order, stock, last_cost_price
                FROM products
                WHERE name = ?
                ORDER BY id ASC
                LIMIT 1
                """,
                (product_name,),
            ).fetchone()

        resolved_retail = _to_float(retail_price)
        resolved_wholesale = _to_float(wholesale_price)
        resolved_external = _to_float(external_price)

        if not product:
            safe_name = (product_name or "").strip()
            if not safe_name:
                return {
                    "success": False,
                    "error": "product_name is required when product_id cannot be resolved",
                    "needs_review": True,
                }

            inferred_category = category or infer_category(safe_name)

            if resolved_external is not None:
                if client_type == "Wholesale" and resolved_wholesale is None:
                    resolved_wholesale = resolved_external
                elif client_type != "Wholesale" and resolved_retail is None:
                    resolved_retail = resolved_external

            new_id = add_quick_product(
                safe_name,
                inferred_category,
                resolved_retail if resolved_retail is not None else 0,
                resolved_wholesale if resolved_wholesale is not None else 0,
            )
            created = True
            product = conn.execute(
                """
                SELECT id, name, category, price_wholesale, price_retail,
                       stock_qty, sort_order, stock, last_cost_price
                FROM products
                WHERE id = ?
                """,
                (new_id,),
            ).fetchone()

        price_field = "price_wholesale" if client_type == "Wholesale" else "price_retail"
        selected_price = product["price_wholesale"] if client_type == "Wholesale" else product["price_retail"]
        needs_review = False
        price_source = "database"

        if selected_price in (None, "", 0, 0.0):
            if resolved_external is not None:
                selected_price = resolved_external
                price_source = "external_price"
            elif client_type == "Wholesale" and resolved_wholesale is not None:
                selected_price = resolved_wholesale
                price_source = "wholesale_price"
            elif client_type != "Wholesale" and resolved_retail is not None:
                selected_price = resolved_retail
                price_source = "retail_price"
            else:
                selected_price = 0
            needs_review = True

        return {
            "success": True,
            "created": created,
            "needs_review": needs_review,
            "selected_price": selected_price,
            "selected_price_field": price_field,
            "price_source": price_source,
            "product": {
                "id": product["id"],
                "name": product["name"],
                "category": product["category"],
                "price_wholesale": product["price_wholesale"],
                "price_retail": product["price_retail"],
                "stock_qty": product["stock_qty"],
                "sort_order": product["sort_order"],
                "stock": product["stock"],
                "last_cost_price": product["last_cost_price"],
            },
        }
    finally:
        conn.close()

def save_order_transaction(client_id, total_amount, discount, net_total, paid_amount, remaining, items, payment_method, notes="", delivery_date=None):
    conn = get_db_connection()
    c = conn.cursor()
    sync_order_id = None
    try:
        c.execute("""
            INSERT INTO orders (client_id, total_amount, status, date, delivery_date, notes) 
            VALUES (?, ?, 'Under Preparation', CURRENT_TIMESTAMP, ?, ?)
        """, (client_id, net_total, delivery_date, notes))
        order_id = c.lastrowid
        
        for item in items:
            c.execute("""
                INSERT INTO order_items (order_id, product_id, product_name, qty, price, total) 
                VALUES (?, ?, ?, ?, ?, ?)
            """, (order_id, item['id'], item['name'], item['qty'], item['price'], item['total']))
            c.execute("UPDATE products SET stock_qty = stock_qty - ? WHERE id = ?", (item['qty'], item['id']))
            
        if remaining > 0:
            c.execute("UPDATE clients SET balance = balance + ? WHERE id = ?", (remaining, client_id))
            c.execute("INSERT INTO transactions (client_id, type, amount, notes) VALUES (?, 'debt', ?, ?)",
                      (client_id, remaining, f"Order #{order_id} - Remaining"))
                      
        if paid_amount > 0:
            c.execute("""
                INSERT INTO transactions (client_id, type, category, amount, notes, user, related_ref) 
                VALUES (?, 'Income', 'Sales', ?, ?, 'System', ?)
            """, (client_id, paid_amount, f"Order #{order_id} - Payment ({payment_method})", f"Order #{order_id}"))

        conn.commit()
        sync_order_id = order_id
        return {"success": True, "order_id": order_id}
        
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()
        if sync_order_id is not None:
            _schedule_best_effort_sheet_sync(sync_order_id)

def update_order_total_db(order_id, new_total):
    conn = get_db_connection()
    c = conn.cursor()
    try:
        # Update Order
        c.execute("UPDATE orders SET total_amount = ? WHERE id = ?", (new_total, order_id))
        # Note: This desyncs items sum from total. Accepted for "Manual Override".
        conn.commit()
        return {"success": True}
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()

def delete_transaction(txn_id):
    conn = get_db_connection()
    c = conn.cursor()
    try:
        # Get transaction details first to reverse effect
        txn = c.execute("SELECT * FROM transactions WHERE id=?", (txn_id,)).fetchone()
        if not txn: return {"success": False, "error": "Not found"}
        
        client_id = txn['client_id']
        amount = txn['amount']
        t_type = txn['type']
        
        # Reverse Balance Effect
        # If 'payment' or 'Income', it REDUCED balance. So adding it back INCREASES balance.
        # If 'debt', it INCREASED balance. So removing it DECREASES balance.
        
        if t_type in ['payment', 'Income']:
            c.execute("UPDATE clients SET balance = balance + ? WHERE id=?", (amount, client_id))
        elif t_type == 'debt':
            c.execute("UPDATE clients SET balance = balance - ? WHERE id=?", (amount, client_id))
            
        # Delete record
        c.execute("DELETE FROM transactions WHERE id=?", (txn_id,)).fetchone() # fetchone needed? No, delete returns cursor
        c.execute("DELETE FROM transactions WHERE id=?", (txn_id,))
        
        conn.commit()
        return {"success": True}
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()



def get_dashboard_stats():
    conn = get_db_connection()
    c = conn.cursor()
    stats = {}
    
    # 1. Total Sales (Revenue - Delivered Only)
    # User feedback indicates "Total Sales" (All) was wrong, implying they want Revenue.
    stats['total_sales'] = c.execute("SELECT COALESCE(SUM(total_amount), 0) FROM orders WHERE status = 'Delivered'").fetchone()[0]
    
    # 2. Total Debt (Sum of all Client Balances + Under Prep)
    # Correct Formula Logic
    sum_balance = c.execute("SELECT COALESCE(SUM(balance), 0) FROM clients").fetchone()[0]
    sum_under_prep = c.execute("SELECT COALESCE(SUM(total_amount), 0) FROM orders WHERE status = 'Under Preparation'").fetchone()[0]
    stats['total_debt'] = sum_balance + sum_under_prep

    # 3. Counts
    stats['total_orders'] = c.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    stats['active'] = c.execute("SELECT COUNT(*) FROM orders WHERE status = 'Under Preparation'").fetchone()[0]
    stats['completed'] = c.execute("SELECT COUNT(*) FROM orders WHERE status = 'Delivered'").fetchone()[0]
    
    # NEW: Daily Cash (Resets every 24h)
    # Use SQLite 'localtime' to match Python's perspective if DB is UTC
    import datetime
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    
    # Robust Query: Try to match the date part of the timestamp
    # We check against both 'now' locally and the python passed date
    stats['daily_cash'] = c.execute("""
        SELECT COALESCE(SUM(amount), 0) 
        FROM transactions 
        WHERE type='Income' 
        AND (date(date) = ? OR date(date, 'localtime') = ?)
    """, (today, today)).fetchone()[0]

    recent = c.execute("""
        SELECT o.id, c.name, o.total_amount, o.status, o.date 
        FROM orders o 
        LEFT JOIN clients c ON o.client_id = c.id 
        ORDER BY o.date DESC LIMIT 5
    """).fetchall()
    stats['recent_orders'] = [{'id': r['id'], 'name': r['name'], 'total_amount': r['total_amount'], 'status': r['status'], 'date_str': r['date']} for r in recent]
    
    low = c.execute("SELECT name, stock_qty FROM products WHERE stock_qty <= 5 ORDER BY stock_qty ASC LIMIT 10").fetchall()
    stats['low_stock'] = [{'name': r['name'], 'stock': r['stock_qty']} for r in low]
    
    sales = c.execute("""
        SELECT strftime('%Y-%m-%d', date) as day, SUM(total_amount) as total 
        FROM orders WHERE status = 'Delivered' GROUP BY day ORDER BY day DESC LIMIT 7
    """).fetchall()
    stats['daily_sales'] = [{'day': r['day'], 'total': r['total']} for r in sales][::-1]
    
    mix = c.execute("""
        SELECT product_name, SUM(qty) as total_qty FROM order_items GROUP BY product_name ORDER BY total_qty DESC LIMIT 5
    """).fetchall()
    stats['product_mix'] = [{'product_name': r['product_name'], 'total_qty': r['total_qty']} for r in mix]
    
    conn.close()
    return stats

def get_customers_stats():
    conn = get_db_connection()
    stats = {}
    stats['wholesale'] = conn.execute("SELECT COUNT(*) FROM clients WHERE type = 'Wholesale'").fetchone()[0]
    stats['retail'] = conn.execute("SELECT COUNT(*) FROM clients WHERE type = 'Retail'").fetchone()[0]
    stats['total_debt'] = conn.execute("SELECT COALESCE(SUM(balance), 0) FROM clients").fetchone()[0]
    conn.close()
    return stats

def get_products_stats():
    conn = get_db_connection()
    stats = {}
    stats['total_items'] = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    stats['inventory_value'] = conn.execute("SELECT COALESCE(SUM(price_wholesale * stock_qty), 0) FROM products").fetchone()[0]
    stats['low_stock_count'] = conn.execute("SELECT COUNT(*) FROM products WHERE stock_qty <= 5").fetchone()[0]
    conn.close()
    return stats

def get_orders_stats():
    conn = get_db_connection()
    stats = {'under_prep': {'count': 0, 'value': 0}, 'ready': {'count': 0, 'value': 0}, 'delivered': {'count': 0, 'value': 0}, 'completion_rate': 0}
    rows = conn.execute("SELECT status, COUNT(*), SUM(total_amount) FROM orders GROUP BY status").fetchall()
    total = 0; delivered = 0
    for r in rows:
        st, cnt, val = r[0], r[1], r[2] or 0
        total += cnt
        if st == 'Under Preparation': stats['under_prep'] = {'count': cnt, 'value': val}
        elif st == 'Ready': stats['ready'] = {'count': cnt, 'value': val}
        elif st == 'Delivered': 
            stats['delivered'] = {'count': cnt, 'value': val}
            delivered = cnt
    if total > 0: stats['completion_rate'] = int((delivered / total) * 100)
    conn.close()
    conn.close()
    return stats

def update_order_image_path(order_id, path):
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("UPDATE orders SET local_image_path = ? WHERE id = ?", (path, order_id))
        conn.commit()
        return True
    except Exception as e:
        return str(e)
    finally:
        conn.close()

def delete_client(client_id):
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("DELETE FROM transactions WHERE client_id = ?", (client_id,))
        orders = c.execute("SELECT id FROM orders WHERE client_id = ?", (client_id,)).fetchall()
        for o in orders:
            c.execute("DELETE FROM order_items WHERE order_id = ?", (o['id'],))
        c.execute("DELETE FROM orders WHERE client_id = ?", (client_id,))
        c.execute("DELETE FROM clients WHERE id = ?", (client_id,))
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def delete_order(order_id):
    """FIXED (pos-writer 2026-10-11): reverts product stock, cancels the order's debt
    transaction and delivery-payment income rows (reverting client balance) before
    deleting items, files and the order. Old behaviour deleted rows only."""
    conn = get_db_connection()
    c = conn.cursor()
    try:
        order = c.execute("SELECT client_id, status FROM orders WHERE id = ?", (order_id,)).fetchone()
        if not order:
            return False
        client_id = order['client_id']

        # 1) Revert stock (mirror of save_order_transaction deduction)
        old_items = c.execute("SELECT product_id, qty FROM order_items WHERE order_id = ?", (order_id,)).fetchall()
        for item in old_items:
            if item['product_id'] is not None:
                c.execute("UPDATE products SET stock_qty = stock_qty + ? WHERE id = ?",
                          (item['qty'], item['product_id']))

        # 2) Cancel the order's debt transaction and revert the balance it added
        debt_txn = c.execute(
            "SELECT id, amount FROM transactions WHERE type='debt' AND notes = ?",
            (f"Order #{order_id} - Remaining",)
        ).fetchone()
        if debt_txn:
            c.execute("UPDATE clients SET balance = balance - ? WHERE id = ?",
                      (debt_txn['amount'], client_id))
            c.execute("DELETE FROM transactions WHERE id = ?", (debt_txn['id'],))

        # 3) Cancel payment/Income rows tied to this order
        pay_rows = c.execute(
            "SELECT id, amount, notes FROM transactions "
            "WHERE type IN ('payment','Income') AND (related_ref = ? OR notes LIKE ?)",
            (f"Order #{order_id}", f"%Order #{order_id}%")).fetchall()
        for t in pay_rows:
            if t['notes'] and str(t['notes']).startswith('Delivery Order #'):
                # recorded by update_order_status Delivered: it reduced the balance -> revert it
                c.execute("UPDATE clients SET balance = balance + ? WHERE id = ?",
                          (t['amount'], client_id))
            c.execute("DELETE FROM transactions WHERE id = ?", (t['id'],))

        try:
            manage_file_system(order_id, 'delete')
        except Exception:
            pass

        c.execute("DELETE FROM order_items WHERE order_id = ?", (order_id,))
        c.execute("DELETE FROM orders WHERE id = ?", (order_id,))
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def save_purchase_invoice(data):
    conn = get_db_connection()
    c = conn.cursor()
    try:
        total_cost = sum(item['qty'] * item['cost'] for item in data['items'])
        if data.get('id'):
            inv_id = data['id']
            curr = c.execute("SELECT status FROM purchase_invoices WHERE id=?", (inv_id,)).fetchone()
            if curr and curr['status'] == 'Received':
                return {"success": False, "error": "Cannot edit a Received invoice. Revert to Draft first."}
            c.execute("""UPDATE purchase_invoices SET supplier_id=?, supplier_name=?, total_cost=?, date=?, notes=? WHERE id=?""", 
                (data.get('supplier_id'), data.get('supplier_name'), total_cost, data.get('date'), data.get('notes'), inv_id))
            c.execute("DELETE FROM purchase_items WHERE invoice_id=?", (inv_id,))
        else:
            c.execute("""INSERT INTO purchase_invoices (supplier_id, supplier_name, total_cost, status, date, notes) VALUES (?, ?, ?, 'Pending', ?, ?)""",
                (data.get('supplier_id'), data.get('supplier_name'), total_cost, data.get('date'), data.get('notes')))
            inv_id = c.lastrowid
            
        for item in data['items']:
            c.execute("""INSERT INTO purchase_items (invoice_id, product_id, product_name, qty, cost_price, total) VALUES (?, ?, ?, ?, ?, ?)""",
                (inv_id, item['product_id'], item['product_name'], item['qty'], item['cost'], item['qty'] * item['cost']))
        conn.commit()
        return {"success": True, "invoice_id": inv_id}
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()

def toggle_purchase_status(invoice_id, new_status):
    conn = get_db_connection()
    c = conn.cursor()
    try:
        inv = c.execute("SELECT * FROM purchase_invoices WHERE id=?", (invoice_id,)).fetchone()
        if not inv: return {"success": False, "error": "Invoice not found"}
        if inv['status'] == new_status: return {"success": True, "message": "No change needed"}
        items = c.execute("SELECT * FROM purchase_items WHERE invoice_id=?", (invoice_id,)).fetchall()
        
        if new_status == 'Received':
            for item in items:
                c.execute("UPDATE products SET stock_qty = stock_qty + ? WHERE id=?", (item['qty'], item['product_id']))
                c.execute("UPDATE products SET last_cost_price = ? WHERE id=?", (item['cost_price'], item['product_id']))
                
            # Trigger 'Expense' with a per-invoice related_ref so Pending-revert and delete_purchase
            # can target exactly this invoice's expense (never a supplier's other invoices).
            inv_total = c.execute("SELECT total_cost FROM purchase_invoices WHERE id=?", (invoice_id,)).fetchone()[0]
            c.execute("""
                INSERT INTO transactions (type, category, amount, notes, user, related_ref) 
                VALUES ('Expense', 'Raw Materials', ?, ?, 'System', ?)
            """, (inv_total, f"Purchase Invoice #{invoice_id}", f"Purchase Invoice #{invoice_id}"))
            
        elif new_status == 'Pending':
            for item in items:
                c.execute("UPDATE products SET stock_qty = stock_qty - ? WHERE id=?", (item['qty'], item['product_id']))
            # Revert ONLY this invoice's Expense (per-invoice related_ref), never other invoices of same supplier.
            c.execute("DELETE FROM transactions WHERE related_ref = ? AND type='Expense'", (f"Purchase Invoice #{invoice_id}",))
        
        c.execute("UPDATE purchase_invoices SET status=? WHERE id=?", (new_status, invoice_id))
        conn.commit()
        return {"success": True, "new_status": new_status}
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()

def get_all_purchases():
    conn = get_db_connection()
    purchases = conn.execute("SELECT * FROM purchase_invoices ORDER BY date DESC, id DESC").fetchall()
    conn.close()
    return [dict(row) for row in purchases]

def get_purchase_details(invoice_id):
    conn = get_db_connection()
    inv = conn.execute("SELECT * FROM purchase_invoices WHERE id=?", (invoice_id,)).fetchone()
    items = conn.execute("SELECT * FROM purchase_items WHERE invoice_id=?", (invoice_id,)).fetchall()
    conn.close()
    return {"invoice": dict(inv), "items": [dict(i) for i in items]} if inv else None

def delete_purchase(invoice_id):
    conn = get_db_connection()
    c = conn.cursor()
    try:
        inv = c.execute("SELECT status FROM purchase_invoices WHERE id=?", (invoice_id,)).fetchone()
        if not inv: return {"success": False, "error": "Not found"}
        if inv['status'] == 'Received':
            items = c.execute("SELECT * FROM purchase_items WHERE invoice_id=?", (invoice_id,)).fetchall()
            for item in items:
                 c.execute("UPDATE products SET stock_qty = stock_qty - ? WHERE id=?", (item['qty'], item['product_id']))
            # Delete this invoice's own Expense row (per-invoice related_ref) so no orphan expense remains.
            c.execute("DELETE FROM transactions WHERE related_ref = ? AND type='Expense'", (f"Purchase Invoice #{invoice_id}",))
        c.execute("DELETE FROM purchase_items WHERE invoice_id=?", (invoice_id,))
        c.execute("DELETE FROM purchase_invoices WHERE id=?", (invoice_id,))
        conn.commit()
        return {"success": True}
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()




# --- Advanced Financial Module Functions ---

def add_general_transaction(t_type, category, amount, description, user, ref="Manual"):
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("""
            INSERT INTO transactions (type, category, amount, notes, user, related_ref) 
            VALUES (?, ?, ?, ?, ?, ?)
        """, (t_type, category, amount, description, user, ref))
        conn.commit()
        return {"success": True}
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()

def get_financial_ledger(start_date=None, end_date=None):
    conn = get_db_connection()
    query = "SELECT * FROM transactions WHERE type IN ('Income', 'Expense')"
    params = []
    
    if start_date:
        query += " AND date >= ?"
        params.append(start_date + " 00:00:00")
    if end_date:
        query += " AND date <= ?"
        params.append(end_date + " 23:59:59")
        
    query += " ORDER BY date DESC"
    
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_financial_stats():
    conn = get_db_connection()
    
    # Cash on Hand (All time)
    income = conn.execute("SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE type='Income'").fetchone()[0]
    expenses = conn.execute("SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE type='Expense'").fetchone()[0]
    cash_on_hand = income - expenses
    
    # Monthly Stats (Current Month)
    import datetime
    now = datetime.datetime.now()
    month_str = now.strftime("%Y-%m")
    
    monthly_sales = conn.execute("SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE type='Income' AND category='Sales' AND strftime('%Y-%m', date) = ?", (month_str,)).fetchone()[0]
    monthly_expenses = conn.execute("SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE type='Expense' AND strftime('%Y-%m', date) = ?", (month_str,)).fetchone()[0]
    
    net_profit = monthly_sales - monthly_expenses # Simplified: Cash Flow Profit
    
    conn.close()
    return {
        "cash_on_hand": cash_on_hand,
        "monthly_income": monthly_sales, # Showing Sales as Income to be specific to 'Sales', or should we show ALL monthly income? User said "Total Sales (Income)". I'll assume Sales.
        "monthly_expenses": monthly_expenses,
        "net_profit": net_profit
    }

def get_unique_categories():
    conn = get_db_connection()
    rows = conn.execute("SELECT DISTINCT category FROM transactions WHERE category IS NOT NULL ORDER BY category").fetchall()
    conn.close()
    return [r['category'] for r in rows] # Fixed: return list of strings

# --- Staff Management Module ---

def get_all_staff(include_inactive=False):
    conn = get_db_connection()
    query = "SELECT * FROM staff"
    if not include_inactive:
        query += " WHERE is_active = 1"
    query += " ORDER BY name ASC"
    staff = conn.execute(query).fetchall()
    
    staff_list = []
    for s in staff:
        s_dict = dict(s)
        # Calculate current month stats
        import datetime
        today = datetime.datetime.now().strftime("%Y-%m")
        
        # Sales Count for Leaderboard
        # Using 'transactions' table where user=staff_name or similar? 
        # Actually, simpler: For now, we manually assign sales to staff or track orders?
        # The prompt says implementation plan: "Staff Grid: ... Stats: Items Sold"
        # We need a way to link Order -> Staff. 
        # Adding 'staff_id' to orders is a migration we might need, OR just use 'user' column in transactions?
        # Let's use a dummy calc or query 'transactions' where user=s['name'] if we implemented that.
        # For now, return placeholders or 0.
        s_dict['sales_count'] = 0 
        s_dict['commission_earned'] = 0 
        
        staff_list.append(s_dict)
        
    conn.close()
    return staff_list

def save_staff(data):
    conn = get_db_connection()
    c = conn.cursor()
    try:
        import hashlib
        pin_hash = None
        if data.get('pin'):
            pin_hash = hashlib.sha256(data['pin'].encode()).hexdigest()
            
        if data.get('id'):
            # Update
            query = "UPDATE staff SET name=?, role=?, base_salary=?, commission_rate=?"
            params = [data['name'], data['role'], data['base_salary'], data['commission_rate']]
            
            if pin_hash:
                query += ", pin_hash=?"
                params.append(pin_hash)
            
            if data.get('photo_path'):
                query += ", photo_path=?"
                params.append(data['photo_path'])
                
            query += " WHERE id=?"
            params.append(data['id'])
            
            c.execute(query, params)
        else:
            # Create
            c.execute("""INSERT INTO staff (name, role, photo_path, pin_hash, base_salary, commission_rate) 
                         VALUES (?, ?, ?, ?, ?, ?)""",
                      (data['name'], data['role'], data.get('photo_path'), pin_hash, data.get('base_salary', 0), data.get('commission_rate', 0)))
        
        conn.commit()
        return {"success": True}
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()

def delete_staff(staff_id):
    # Soft Delete
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("UPDATE staff SET is_active = 0 WHERE id = ?", (staff_id,))
        conn.commit()
        return {"success": True}
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()

# --- Attendance ---

def log_attendance_action(staff_id, action, timestamp=None):
    # action: 'check_in' or 'check_out'
    conn = get_db_connection()
    c = conn.cursor()
    try:
        import datetime
        now = datetime.datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = (timestamp or now).isoformat()
        
        # Check if record exists for today
        record = c.execute("SELECT * FROM attendance WHERE staff_id=? AND date=?", (staff_id, date_str)).fetchone()
        
        if action == 'check_in':
            if record: return {"success": False, "error": "Already checked in today"}
            
            # Determine status (Late?)
            # Hardcoded 9:00 AM logic for now, or fetch settings
            status = 'Present'
            if now.hour > 9 or (now.hour == 9 and now.minute > 15):
                status = 'Late'
                
            c.execute("INSERT INTO attendance (staff_id, date, check_in, status) VALUES (?, ?, ?, ?)",
                      (staff_id, date_str, time_str, status))
        
        elif action == 'check_out':
            if not record: return {"success": False, "error": "No check-in record found for today"}
            c.execute("UPDATE attendance SET check_out = ? WHERE id = ?", (time_str, record['id']))
            
        conn.commit()
        return {"success": True}
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()

def get_attendance_log(staff_id=None, date_from=None, date_to=None):
    conn = get_db_connection()
    query = """
        SELECT a.*, s.name, s.photo_path 
        FROM attendance a 
        LEFT JOIN staff s ON a.staff_id = s.id 
        WHERE 1=1
    """
    params = []
    
    if staff_id:
        query += " AND a.staff_id = ?"
        params.append(staff_id)
    if date_from:
        query += " AND a.date >= ?"
        params.append(date_from)
    if date_to:
        query += " AND a.date <= ?"
        params.append(date_to)
        
    query += " ORDER BY a.date DESC, a.check_in DESC"
    
    logs = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(l) for l in logs]

# --- Payroll ---

def get_payroll_draft(staff_id):
    conn = get_db_connection()
    try:
        # Get Staff
        staff = conn.execute("SELECT * FROM staff WHERE id=?", (staff_id,)).fetchone()
        if not staff: return None
        
        # 1. Base Salary
        base = staff['base_salary'] or 0
        
        # 2. Commissions (Need linkage to Sales)
        # Placeholder: 0 until we link Orders -> Staff
        commission = 0
        
        # 3. Deductions & Bonuses (from payroll_transactions for current month, not yet paid out?)
        # Logic: We sum up all non-Payout transactions since last Payout? 
        # Or simpler: Just sum all for this month. 
        # Let's assume Payout clears the balance or marks items as 'Paid'.
        # Better: Ledger balance approach.
        
        # Get Balance from Ledger
        # Sum(Bonus) - Sum(Deduction) - Sum(Payout)
        # Actually, Payout should reduce the Payable amount.
        
        # Let's calculate: 
        # Total Earned (Lifetime) = Sum(Bonus) + (Months * Salary) + (Commissions)
        # Total Paid (Lifetime) = Sum(Payout) + Sum(Deduction)? No Deduction reduces earning.
        
        # Simplified Model for this task:
        # We just want a "Draft" for the current month/period.
        # Let's just return the accumulated "Wallet" balance + Base Salary pro-rated?
        # User requirement: "Wallet Balance (Bonus/Deductions)"
        
        wallet_txns = conn.execute("""
            SELECT type, amount FROM payroll_transactions 
            WHERE staff_id = ? AND type IN ('Bonus', 'Deduction') 
            AND date >= date('now', 'start of month') -- Filter for this month for draft view
        """, (staff_id,)).fetchall()
        
        bonuses = sum(t['amount'] for t in wallet_txns if t['type'] == 'Bonus')
        deductions = sum(t['amount'] for t in wallet_txns if t['type'] == 'Deduction')
        
        net_salary = base + commission + bonuses - deductions
        
        return {
            "staff_name": staff['name'],
            "base_salary": base,
            "commission": commission,
            "bonuses": bonuses,
            "deductions": deductions,
            "net_salary": net_salary
        }
    finally:
        conn.close()

def add_payroll_transaction(staff_id, t_type, amount, reason, creator="System"):
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("""
            INSERT INTO payroll_transactions (staff_id, type, amount, reason, created_by)
            VALUES (?, ?, ?, ?, ?)
        """, (staff_id, t_type, amount, reason, creator))
        conn.commit()
        return {"success": True}
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()

def confirm_payout(staff_id, notes="Monthly Payout"):
    # Secure server-side calculation of net salary
    draft = get_payroll_draft(staff_id)
    if not draft: return {"success": False, "error": "Staff not found"}
    
    amount = draft['net_salary']
    if amount <= 0:
        return {"success": False, "error": "No positive balance to pay"}
        
    return add_payroll_transaction(staff_id, 'Payout', amount, notes)

# --- Requests --- 

def get_staff_requests():
    conn = get_db_connection()
    c = conn.cursor()
    reqs = c.execute("""
        SELECT r.*, s.name as staff_name, s.photo_path 
        FROM requests r 
        LEFT JOIN staff s ON r.staff_id = s.id 
        ORDER BY r.date DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in reqs]

def update_request_status(request_id, status):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE requests SET status=? WHERE id=?", (status, request_id))
    conn.commit()
    conn.close()
    return {"success": True}

# --- Chat ---

def send_chat_message(sender_id, recipient_id, message, image_path=None):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO chat_messages (sender_id, recipient_id, message, image_path)
        VALUES (?, ?, ?, ?)
    """, (sender_id, recipient_id, message, image_path))
    conn.commit()
    conn.close()
    return {"success": True}

def get_chat_messages(limit=50):
    conn = get_db_connection()
    # Fetch messages with Sender Name
    msgs = conn.execute("""
        SELECT m.*, s.name as sender_name, s.photo_path 
        FROM chat_messages m
        LEFT JOIN staff s ON m.sender_id = s.id
        ORDER BY m.timestamp ASC
    """).fetchall() # UI will likely want DESC then reverse, or ASC to append.
    conn.close()
    return [dict(m) for m in msgs]

# --- Security Gate ---

def generate_qr_token():
    conn = get_db_connection()
    import uuid
    import datetime
    token = str(uuid.uuid4())
    expires = (datetime.datetime.now() + datetime.timedelta(seconds=30)).isoformat()
    
    conn.execute("DELETE FROM security_tokens") # Clear old
    conn.execute("INSERT INTO security_tokens (token, expires_at) VALUES (?, ?)", (token, expires))
    conn.commit()
    conn.close()
    return {"token": token, "expires": expires}
    conn.close()
    cats = [row['category'] for row in rows]
    # Add defaults if empty
    defaults = ['Sales', 'Raw Materials', 'Rent', 'Salaries', 'Utilities', 'Maintenance', 'Withdrawals', 'Debt Collection', 'Other']
    for d in defaults:
        if d not in cats:
            cats.append(d)
    return sorted(list(set(cats)))

# --- End File System Management ---
def log_debug(msg):
    try:
        with open("fs_debug.log", "a", encoding="utf-8") as f:
            f.write(f"{time.ctime()}: {msg}\n")
    except: pass

from file_ops_engine import FileOpsEngine

# --- File Movement Logs (Undo Engine) ---
def log_movement(order_id, previous_path, new_stage):
    conn = get_db_connection()
    try:
        conn.execute("INSERT INTO file_movement_logs (order_id, previous_path, new_stage) VALUES (?, ?, ?)",
                     (order_id, previous_path, new_stage))
        conn.commit()
    except Exception as e:
        log_debug(f"Log Error: {e}")
    finally:
        conn.close()

def get_last_movement_and_pop(order_id):
    conn = get_db_connection()
    try:
        # LIFO: Get most recent
        row = conn.execute("SELECT id, previous_path FROM file_movement_logs WHERE order_id = ? ORDER BY id DESC LIMIT 1", (order_id,)).fetchone()
        if row:
            # Delete it (Pop)
            conn.execute("DELETE FROM file_movement_logs WHERE id = ?", (row['id'],))
            conn.commit()
            return row['previous_path']
        return None
    finally:
        conn.close()

def get_order_details(order_id):
    conn = get_db_connection()
    c = conn.cursor()
    try:
        order = c.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        if not order: return None
        
        items = c.execute("""
            SELECT oi.*, p.price_retail, p.price_wholesale, p.stock_qty 
            FROM order_items oi 
            LEFT JOIN products p ON oi.product_id = p.id 
            WHERE oi.order_id = ?
        """, (order_id,)).fetchall()
        
        client = c.execute("SELECT * FROM clients WHERE id = ?", (order['client_id'],)).fetchone()
        
        # Get Transactions (Debt/Payment) linked to this order to show "Paid" amount
        # Heuristic: Find payment transaction with note containing Order #{id}
        paid_trans = c.execute("SELECT amount FROM transactions WHERE client_id=? AND type='payment' AND notes LIKE ?", 
                             (order['client_id'], f"%Order #{order_id}%")).fetchone()
        paid_amount = paid_trans['amount'] if paid_trans else 0

        return {
            "order": dict(order),
            "items": [dict(i) for i in items],
            "client": dict(client) if client else {},
            "paid_amount": paid_amount
        }
    finally:
        conn.close()

def update_order_full(order_id, data):
    """
    Full Update:
    1. Revert Stock & Balance (Deletion Logic).
    2. Apply New Data (Creation Logic).
    """
    conn = get_db_connection()
    c = conn.cursor()
    try:
        # --- 0. FETCH ORIGINAL DATA (CRITICAL FIX) ---
        # We must know the OLD client to revert balance correctly
        original_order = c.execute("SELECT client_id FROM orders WHERE id = ?", (order_id,)).fetchone()
        if not original_order:
            return {"success": False, "error": "Order not found"}
            
        original_client_id = original_order['client_id']

        # --- 1. PREPARE REVERT ---
        # Get Old Items
        old_items = c.execute("SELECT product_id, qty FROM order_items WHERE order_id = ?", (order_id,)).fetchall()
        for item in old_items:
            # Revert Stock
            c.execute("UPDATE products SET stock_qty = stock_qty + ? WHERE id = ?", (item['qty'], item['product_id']))
            
        # Get Old Financials
        # Find 'debt' transaction to revert balance
        old_debt_trans = c.execute("SELECT id, amount FROM transactions WHERE notes = ? AND type='debt'", (f"Order #{order_id} - Remaining",)).fetchone()
        if old_debt_trans:
            # Revert Balance from ORIGINAL CLIENT (Fix)
            c.execute("UPDATE clients SET balance = balance - ? WHERE id = ?", (old_debt_trans['amount'], original_client_id))
            # Delete Transaction
            c.execute("DELETE FROM transactions WHERE id = ?", (old_debt_trans['id'],))
            
        # Delete Old Payment Transaction (Just to avoid duplication, we will re-insert new one)
        c.execute("DELETE FROM transactions WHERE notes LIKE ? AND type='payment'", (f"%Order #{order_id}%",))

        # Delete Old Items
        c.execute("DELETE FROM order_items WHERE order_id = ?", (order_id,))

        # --- 2. APPLY NEW DATA ---
        new_client_id = data['client_id'] # The NEW client
        total_order = 0
        notes = data.get('notes', '')
        
        final_items = []
        for item in data['items']:
            pid = item.get('id')
            qty = float(item.get('qty', 1))
            price = float(item.get('price', 0))
            
            # Fetch Name
            prod_db = c.execute("SELECT name FROM products WHERE id=?", (pid,)).fetchone()
            p_name = prod_db['name'] if prod_db else item.get('name', "Unknown")
            
            line_total = price * qty
            total_order += line_total
            
            final_items.append({
                'id': pid, 'name': p_name, 'qty': qty, 'price': price, 'total': line_total
            })
            
            # Deduct Stock
            c.execute("UPDATE products SET stock_qty = stock_qty - ? WHERE id = ?", (qty, pid))
            # Insert Item
            c.execute("INSERT INTO order_items (order_id, product_id, product_name, qty, price, total) VALUES (?, ?, ?, ?, ?, ?)",
                      (order_id, pid, p_name, qty, price, line_total))

        # Financials
        paid_amount = float(data.get('paid_amount', 0))
        net_total = total_order # Assuming no discount edits for now
        remaining = net_total - paid_amount
        
        # Update Order Record (Update Client ID here!)
        c.execute("UPDATE orders SET client_id = ?, total_amount = ?, notes = ? WHERE id = ?", (new_client_id, net_total, notes, order_id))
        
        # Update Balance (New Debt) - On NEW Client
        if remaining > 0:
            c.execute("UPDATE clients SET balance = balance + ? WHERE id = ?", (remaining, new_client_id))
            c.execute("INSERT INTO transactions (client_id, type, amount, notes) VALUES (?, 'debt', ?, ?)",
                      (new_client_id, remaining, f"Order #{order_id} - Remaining"))
                      
        # New Payment Record - On NEW Client
        if paid_amount > 0:
            c.execute("""
                INSERT INTO transactions (client_id, type, category, amount, notes, user, related_ref) 
                VALUES (?, 'Income', 'Sales', ?, ?, 'System', ?)
            """, (new_client_id, paid_amount, f"Order #{order_id} - Payment (Edit)", f"Order #{order_id}"))
                      
        # File System (Path might change if client changed? For now assume client doesn't change or we ignore path move for simplicity)
        # Ideally we should rename folder if client changed, but that's complex. Let's stick to content update.
        # But we should update the Order_Details.txt
        try:
             # Fast way: read path, overwrite txt
             current_path_row = c.execute("SELECT local_image_path FROM orders WHERE id=?", (order_id,)).fetchone()
             if current_path_row and current_path_row['local_image_path']:
                 p = current_path_row['local_image_path']
                 txt_path = os.path.join(p, "Order_Details.txt")
                 if os.path.exists(p):
                     with open(txt_path, "w", encoding="utf-8") as f:
                        f.write(f"Order #{order_id} (EDITED)\n")
                        f.write(f"Date: {time.ctime()}\n")
                        f.write(f"Total: {net_total}\n")
                        f.write("Items:\n")
                        for it in final_items:
                            f.write(f"- {it['name']} (Qty: {it['qty']})\n")
        except: pass

        conn.commit()
        return {"success": True}

    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()

def manage_file_system(order_id, action, new_status=None):
    """
    Smart Order File Management V4 (Wholesale/Retail + Undo Engine).
    """
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        log_debug(f"--- manage_file_system V4 called for Order #{order_id} Action: {action} Status: {new_status} ---")
        
        # 1. Get Settings & Initialize Engine
        root_row = c.execute("SELECT value FROM settings WHERE key='local_images_path'").fetchone()
        if not root_row or not root_row['value']:
            log_debug("File System Error: 'local_images_path' not set.")
            return
        
        root_path = root_row['value']
        engine = FileOpsEngine(root_path)

        # 2. Get Order Info
        order = c.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
        if not order: return

        # Get Client Info (Needed for Paths)
        client = c.execute("SELECT * FROM clients WHERE id=?", (order['client_id'],)).fetchone()
        client_name = client['name'] if client else "Unknown"
        client_type = client['type'] if client else "Retail"

        # Get Product Info (Use first item for naming - Atomic Rule)
        # We need product name for the folder name
        item = c.execute("SELECT product_name FROM order_items WHERE order_id=? LIMIT 1", (order_id,)).fetchone()
        product_name = item['product_name'] if item else "Product"

        notes = order['notes']
        current_path_db = order['local_image_path']
        
        # --- ACTION: DELETE ---
        if action == 'delete':
            # Hard delete
            # We try to delete from where it is known to be
            success, msg = engine.delete_order_folder(current_path_db)
            log_debug(f"Delete: {msg}")
            
            # Optional: Cleanup Client folder if empty
            # If path was inside a client folder
            if current_path_db and client_name in current_path_db:
                client_folder = os.path.dirname(current_path_db)
                engine.cleanup_empty_client_folder(client_folder)
            
            # Cleanup Logs
            c.execute("DELETE FROM file_movement_logs WHERE order_id=?", (order_id,))
            conn.commit()
            return

        # --- ACTION: MOVE ---
        elif action == 'move':
            
            # A. RESTORE / UNDO (To Preparation)
            if new_status == 'Under Preparation':
                # LOGIC: Check DB Log -> Restore to PREVIOUS PATH
                previous_path = get_last_movement_and_pop(order_id)
                
                if previous_path:
                    log_debug(f"Undo: Restoring to {previous_path}")
                    success, msg = engine.restore_to_previous_path(order_id, product_name, notes, previous_path)
                    
                    if success:
                        c.execute("UPDATE orders SET local_image_path = ? WHERE id = ?", (previous_path, order_id))
                        conn.commit()
                    else:
                        log_debug(f"Undo Failed: {msg}")
                else:
                    # Fallback: Create new path in Client Folder (Self-Healing if log missing)
                    log_debug("Undo: No log found, constructing default path.")
                    target_path = engine.get_creation_path(client_type, client_name, product_name, notes, order_id)
                    success, msg = engine.restore_to_previous_path(order_id, product_name, notes, target_path) # Utilize restore logic which calls move
                    if success:
                         c.execute("UPDATE orders SET local_image_path = ? WHERE id = ?", (target_path, order_id))
                         conn.commit()

            # B. MOVE FORWARD (To Ready or Delivered)
            elif new_status in ['Ready', 'Delivered']:
                # 1. Log CURRENT Location (Before Move)
                if current_path_db and os.path.exists(current_path_db):
                    log_movement(order_id, current_path_db, new_status)
                
                # 2. Execute Move
                success, msg = engine.move_to_stage(order_id, product_name, notes, new_status, current_known_path=current_path_db)
                
                if success:
                    # Update DB with new path
                    # We need to construct what the new path IS.
                    # Engine moves to Root/Ready_Orders/{AtomicName}
                    folder_name = engine._get_atomic_folder_name(product_name, notes, order_id)
                    new_root = "Ready_Orders" if new_status == 'Ready' else "Delivered_Orders"
                    new_full_path = os.path.join(root_path, new_root, folder_name)
                    
                    c.execute("UPDATE orders SET local_image_path = ? WHERE id = ?", (new_full_path, order_id))
                    conn.commit()
                    log_debug(f"Moved to {new_status}: {new_full_path}")
                else:
                    log_debug(f"Move Failed: {msg}")

    except Exception as e:
        log_debug(f"Critical Manage Error: {str(e)}")
    finally:
        conn.close()

# Financial Stats Functions


def get_financial_ledger(start_date=None, end_date=None):
    """
    Returns financial ledger (transaction history) with optional date filtering.
    """
    conn = get_db_connection()
    
    query = """
        SELECT id, date, type, category, amount, notes, user 
        FROM transactions 
        WHERE 1=1
    """
    
    params = []
    
    if start_date:
        query += " AND date >= ?"
        params.append(start_date)
    
    if end_date:
        query += " AND date <= ?"
        params.append(end_date + " 23:59:59")  # Include full end date
    
    query += " ORDER BY date DESC LIMIT 200"
    
    try:
        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]
    except Exception as e:
        print(f"Error in get_financial_ledger: {e}")
        return []
    finally:
        conn.close()


def get_unique_categories():
    """Returns list of unique transaction categories."""
    conn = get_db_connection()
    try:
        cats = conn.execute("""
            SELECT DISTINCT category 
            FROM transactions 
            WHERE category IS NOT NULL 
            ORDER BY category
        """).fetchall()
        return [c['category'] for c in cats]
    except:
        return []
    finally:
        conn.close()


def add_general_transaction(t_type, category, amount, description, user):
    """
    Adds a general financial transaction (Income or Expense).
    """
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        c.execute("""
            INSERT INTO transactions (client_id, type, category, amount, notes, user)
            VALUES (NULL, ?, ?, ?, ?, ?)
        """, (t_type, category, amount, description, user))
        
        conn.commit()
        return {'success': True, 'message': 'تم إضافة المعاملة بنجاح'}
    except Exception as e:
        conn.rollback()
        return {'success': False, 'message': str(e)}
    finally:
        conn.close()

# Financial Stats Functions

def get_financial_stats():
    """
    Returns financial statistics for the accounts page:
    - cash_on_hand: Current total cash (Income - Expenses)
    - income: Total Income (Sales) for current month
    - expense: Total Expenses for current month
    - profit: Net Profit (Income - Expense)
    """
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        import datetime
        # Get current month range
        now = datetime.datetime.now()
        month_start = now.replace(day=1).strftime("%Y-%m-%d")
        
        # Income this month (Payments + Sales)
        income = c.execute("""
            SELECT COALESCE(SUM(amount), 0) 
            FROM transactions 
            WHERE type IN ('Income', 'payment') 
            AND date >= ?
        """, (month_start,)).fetchone()[0]
        
        # Expenses this month
        expense = c.execute("""
            SELECT COALESCE(SUM(amount), 0) 
            FROM transactions 
            WHERE type = 'Expense' 
            AND date >= ?
        """, (month_start,)).fetchone()[0]
        
        # Cash on Hand (All-Time: Total Income - Total Expenses)
        cash_income = c.execute("""
            SELECT COALESCE(SUM(amount), 0) 
            FROM transactions 
            WHERE type IN ('Income', 'payment')
        """).fetchone()[0]
        
        cash_expense = c.execute("""
            SELECT COALESCE(SUM(amount), 0) 
            FROM transactions 
            WHERE type = 'Expense'
        """).fetchone()[0]
        
        cash_on_hand = cash_income - cash_expense
        profit = income - expense
        
        # Total Customer Debt (Balance + Under Prep for all clients)
        total_debt = 0
        clients = c.execute("SELECT id, balance FROM clients").fetchall()
        for client in clients:
            client_balance = client['balance'] or 0
            under_prep = c.execute("""
                SELECT COALESCE(SUM(total_amount), 0) 
                FROM orders 
                WHERE client_id = ? AND status = 'Under Preparation'
            """, (client['id'],)).fetchone()[0]
            total_debt += client_balance + under_prep
        
        return {
            'cash_on_hand': cash_on_hand,
            'income': income,
            'expense': expense,
            'profit': profit,
            'total_debt': total_debt
        }
        
    except Exception as e:
        print(f"Error in get_financial_stats: {e}")
        return {
            'cash_on_hand': 0,
            'income': 0,
            'expense': 0,
            'profit': 0,
            'total_debt': 0
        }
    finally:
        conn.close()


def get_financial_ledger(start_date=None, end_date=None):
    """
    Returns financial ledger (transaction history) with optional date filtering.
    """
    conn = get_db_connection()
    
    query = """
        SELECT id, date, type, category, amount, notes, user 
        FROM transactions 
        WHERE 1=1
    """
    
    params = []
    
    if start_date:
        query += " AND date >= ?"
        params.append(start_date)
    
    if end_date:
        query += " AND date <= ?"
        params.append(end_date + " 23:59:59")  # Include full end date
    
    query += " ORDER BY date DESC LIMIT 200"
    
    try:
        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]
    except Exception as e:
        print(f"Error in get_financial_ledger: {e}")
        return []
    finally:
        conn.close()


def get_unique_categories():
    """Returns list of unique transaction categories."""
    conn = get_db_connection()
    try:
        cats = conn.execute("""
            SELECT DISTINCT category 
            FROM transactions 
            WHERE category IS NOT NULL 
            ORDER BY category
        """).fetchall()
        return [c['category'] for c in cats]
    except:
        return []
    finally:
        conn.close()


def add_general_transaction(t_type, category, amount, description, user):
    """
    Adds a general financial transaction (Income or Expense).
    """
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        c.execute("""
            INSERT INTO transactions (client_id, type, category, amount, notes, user)
            VALUES (NULL, ?, ?, ?, ?, ?)
        """, (t_type, category, amount, description, user))
        
        conn.commit()
        return {'success': True, 'message': 'تم إضافة المعاملة بنجاح'}
    except Exception as e:
        conn.rollback()
        return {'success': False, 'message': str(e)}
    finally:
        conn.close()


# ============= FINANCIAL STATS FOR ACCOUNTS PAGE =============

def get_financial_stats():
    """
    Returns financial statistics relative to the currently active open daily shift.
    Except total_debt which is global outstanding customer debts.
    """
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        # Get active open shift opened_at timestamp
        shift = c.execute("SELECT opened_at FROM daily_shifts WHERE status = 'open' LIMIT 1").fetchone()
        opened_at = shift['opened_at'] if shift else '1970-01-01 00:00:00'
        
        # Shift Income (Revenue)
        income = c.execute("""
            SELECT COALESCE(SUM(amount), 0) 
            FROM transactions 
            WHERE type IN ('Income', 'payment') 
            AND date >= ?
        """, (opened_at,)).fetchone()[0]
        
        # Shift Expenses
        expense = c.execute("""
            SELECT COALESCE(SUM(amount), 0) 
            FROM transactions 
            WHERE type = 'Expense' 
            AND date >= ?
        """, (opened_at,)).fetchone()[0]
        
        # Shift Drawer Balance (Shift Income - Shift Expense)
        cash_on_hand = income - expense
        
        # Shift COGS (Cost of Goods Sold)
        shift_cogs = c.execute("""
            SELECT COALESCE(SUM(oi.qty * COALESCE(p.last_cost_price, p.price_wholesale, 0)), 0)
            FROM order_items oi
            JOIN orders o ON oi.order_id = o.id
            JOIN products p ON oi.product_id = p.id
            WHERE o.status != 'Cancelled'
            AND o.date >= ?
        """, (opened_at,)).fetchone()[0]
        
        # Shift Net Profit = Revenue - COGS
        profit = income - shift_cogs
        
        # Global Customer Debt = Sum of displayed balances
        all_clients = get_all_clients()
        total_debt = sum(client.get('balance', 0) for client in all_clients)
        
        conn.close()
        
        return {
            'cash_on_hand': cash_on_hand,
            'income': income,
            'expense': expense,
            'profit': profit,
            'total_debt': total_debt
        }
        
    except Exception as e:
        print(f"Error in get_financial_stats: {e}")
        conn.close()
        return {
            'cash_on_hand': 0,
            'income': 0,
            'expense': 0,
            'profit': 0,
            'total_debt': 0
        }


def get_financial_ledger(start_date=None, end_date=None):
    """Returns financial ledger with optional date filtering."""
    conn = get_db_connection()
    
    query = """
        SELECT id, date, type, category, amount, notes, user 
        FROM transactions 
        WHERE 1=1
    """
    
    params = []
    
    if start_date:
        query += " AND date >= ?"
        params.append(start_date)
    
    if end_date:
        query += " AND date <= ?"
        params.append(end_date + " 23:59:59")
    
    query += " ORDER BY date DESC LIMIT 200"
    
    try:
        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]
    except Exception as e:
        print(f"Error in get_financial_ledger: {e}")
        return []
    finally:
        conn.close()


def get_unique_categories():
    """Returns list of unique transaction categories."""
    conn = get_db_connection()
    try:
        cats = conn.execute("""
            SELECT DISTINCT category 
            FROM transactions 
            WHERE category IS NOT NULL 
            ORDER BY category
        """).fetchall()
        return [c['category'] for c in cats]
    except:
        return []
    finally:
        conn.close()


def add_general_transaction(t_type, category, amount, description, user, expense_type='Business'):
    """Adds a general financial transaction, supporting expense_type for Expenses."""
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        c.execute("""
            INSERT INTO transactions (client_id, type, category, amount, notes, user, expense_type)
            VALUES (NULL, ?, ?, ?, ?, ?, ?)
        """, (t_type, category, amount, description, user, expense_type))
        
        conn.commit()
        return {'success': True, 'message': 'تم إضافة المعاملة بنجاح'}
    except Exception as e:
        conn.rollback()
        return {'success': False, 'message': str(e)}
    finally:
        conn.close()

def get_customers_stats():
    """
    Returns stats for Client Page:
    - wholesale count
    - retail count
    - total_debt (Sum of all balances displayed in table)
    """
    try:
        clients = get_all_clients()
        
        wholesale = len([c for c in clients if c['type'] == 'Wholesale'])
        retail = len([c for c in clients if c['type'] == 'Retail'])
        total_debt = sum(c.get('balance', 0) for c in clients)
        
        return {
            'wholesale': wholesale,
            'retail': retail,
            'total_debt': total_debt
        }
    except Exception as e:
        print(f"Error in get_customers_stats: {e}")
        return {
            'wholesale': 0,
            'retail': 0,
            'total_debt': 0
        }

# --- Treasury Upgrade Functions ---

def toggle_transaction_verify(t_id, status):
    conn = get_db_connection()
    conn.execute("UPDATE transactions SET is_verified = ? WHERE id = ?", (status, t_id))
    conn.commit()
    conn.close()

def get_obligations():
    conn = get_db_connection()
    # Get all active obligations
    obs = conn.execute("SELECT * FROM obligations WHERE active=1").fetchall()
    
    # Check status for This Month
    today = datetime.datetime.now()
    current_month_str = today.strftime("%Y-%m")
    
    result = []
    for o in obs:
        o_dict = dict(o)
        is_paid = False
        if o['last_paid_date'] and o['last_paid_date'].startswith(current_month_str):
            is_paid = True
        
        o_dict['is_paid'] = is_paid
        result.append(o_dict)
        
    conn.close()
    return result

def add_obligation(name, amount, day):
    conn = get_db_connection()
    conn.execute("INSERT INTO obligations (name, expected_amount, due_day) VALUES (?, ?, ?)", 
                 (name, amount, day))
    conn.commit()
    conn.close()

def delete_obligation(o_id):
    conn = get_db_connection()
    conn.execute("UPDATE obligations SET active=0 WHERE id=?", (o_id,))
    conn.commit()
    conn.close()

def pay_obligation(o_id, amount, note):
    conn = get_db_connection()
    try:
        # Get Obligation Name
        o = conn.execute("SELECT name FROM obligations WHERE id=?", (o_id,)).fetchone()
        name = o['name'] if o else "Obligation"
        
        # 1. Add Expense Transaction
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        conn.execute("""
            INSERT INTO transactions (type, category, amount, notes, user, related_ref, date)
            VALUES ('Expense', 'Obligations', ?, ?, 'System', ?, ?)
        """, (amount, f"Pay: {name} - {note}", name, datetime.datetime.now()))
        
        # 2. Update Obligation Last Paid
        conn.execute("UPDATE obligations SET last_paid_date = ? WHERE id = ?", (today, o_id))
        
        conn.commit()
        return {'success': True}
    except Exception as e:
        conn.rollback()
        return {'success': False, 'message': str(e)}
    finally:
        conn.close()

def get_savings_balance():
    conn = get_db_connection()
    # Logic:
    # Deposits to Savings are Expenses from Safe (is_savings=1, type=Expense) => Safe decreases, Savings increases
    # Withdraws from Savings are Income to Safe (is_savings=1, type=Income) => Safe increases, Savings decreases
    
    deps = conn.execute("SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE is_savings=1 AND type='Expense'").fetchone()[0]
    withs = conn.execute("SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE is_savings=1 AND type='Income'").fetchone()[0]
    
    conn.close()
    return deps - withs

def process_savings_transaction(action, amount, reason):
    conn = get_db_connection()
    try:
        if action == 'deposit':
            # Money OUT of Safe -> INTO Savings
            # Type: Expense (from Safe perspective)
            conn.execute("""
                INSERT INTO transactions (type, category, amount, notes, user, is_savings, related_ref)
                VALUES ('Expense', 'Savings', ?, ?, 'System', 1, 'Savings Deposit')
            """, (amount, reason))
            
        elif action == 'withdraw':
            # Money INTO Safe <- FROM Savings
            # Type: Income (to Safe perspective)
            conn.execute("""
                INSERT INTO transactions (type, category, amount, notes, user, is_savings, related_ref)
                VALUES ('Income', 'Savings', ?, ?, 'System', 1, 'Savings Withdraw')
            """, (amount, reason))
            
        conn.commit()
        return {'success': True}
    except Exception as e:
        conn.rollback()
        return {'success': False, 'message': str(e)}
    finally:
        conn.close()

def get_last_order_by_client(client_id):
    """Fetch the most recent order for a client along with its items."""
    conn = get_db_connection()
    c = conn.cursor()
    try:
        # Get the most recent order
        order = c.execute("SELECT * FROM orders WHERE client_id = ? ORDER BY date DESC LIMIT 1", (client_id,)).fetchone()
        if not order:
            return None
        
        order_dict = dict(order)
        
        # Get Items
        items = c.execute("SELECT * FROM order_items WHERE order_id = ?", (order['id'],)).fetchall()
        order_dict['items'] = [dict(i) for i in items]
        
        return order_dict
    finally:
        conn.close()

# --- INVENTORY COUNT FUNCTIONS ---

def init_inventory_table():
    """Create inventory_counts table if not exists."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS inventory_counts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER,
        staff_id INTEGER,
        system_qty INTEGER,
        counted_qty INTEGER,
        difference INTEGER,
        notes TEXT,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        reviewed_by INTEGER,
        reviewed_at TIMESTAMP,
        FOREIGN KEY (product_id) REFERENCES products(id)
    )''')
    conn.commit()
    conn.close()

def save_inventory_count(product_id, staff_id, counted_qty, notes=''):
    """Save an inventory count from employee."""
    conn = get_db_connection()
    c = conn.cursor()
    try:
        # Get current system qty
        product = c.execute("SELECT stock_qty, name FROM products WHERE id = ?", (product_id,)).fetchone()
        if not product:
            return {'success': False, 'message': 'Product not found'}
        
        system_qty = product['stock_qty'] or 0
        difference = counted_qty - system_qty
        
        # Check if there's already a pending count for this product by this staff
        existing = c.execute("""
            SELECT id FROM inventory_counts 
            WHERE product_id = ? AND staff_id = ? AND status = 'pending'
        """, (product_id, staff_id)).fetchone()
        
        if existing:
            # Update existing count
            c.execute("""
                UPDATE inventory_counts 
                SET counted_qty = ?, difference = ?, notes = ?, created_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (counted_qty, difference, notes, existing['id']))
        else:
            # Insert new count
            c.execute("""
                INSERT INTO inventory_counts 
                (product_id, staff_id, system_qty, counted_qty, difference, notes, status)
                VALUES (?, ?, ?, ?, ?, ?, 'pending')
            """, (product_id, staff_id, system_qty, counted_qty, difference, notes))
        
        conn.commit()
        return {'success': True, 'message': 'تم حفظ الجرد بنجاح', 'difference': difference}
    except Exception as e:
        conn.rollback()
        return {'success': False, 'message': str(e)}
    finally:
        conn.close()

def get_inventory_counts(staff_id=None, status='all'):
    """Get inventory counts, optionally filtered by staff and status."""
    conn = get_db_connection()
    c = conn.cursor()
    
    query = """
        SELECT ic.*, p.name as product_name, p.category, s.name as staff_name
        FROM inventory_counts ic
        LEFT JOIN products p ON ic.product_id = p.id
        LEFT JOIN staff s ON ic.staff_id = s.id
        WHERE 1=1
    """
    params = []
    
    if staff_id:
        query += " AND ic.staff_id = ?"
        params.append(staff_id)
    
    if status != 'all':
        query += " AND ic.status = ?"
        params.append(status)
    
    query += " ORDER BY ic.created_at DESC"
    
    counts = c.execute(query, params).fetchall()
    conn.close()
    
    return [dict(row) for row in counts]

def approve_inventory_count(count_id, reviewer_id, update_stock=True):
    """Approve an inventory count and optionally update stock."""
    conn = get_db_connection()
    c = conn.cursor()
    try:
        count = c.execute("SELECT * FROM inventory_counts WHERE id = ?", (count_id,)).fetchone()
        if not count:
            return {'success': False, 'message': 'Count not found'}
        
        if count['status'] != 'pending':
            return {'success': False, 'message': 'Count already processed'}
        
        # Update count status
        c.execute("""
            UPDATE inventory_counts 
            SET status = 'approved', reviewed_by = ?, reviewed_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (reviewer_id, count_id))
        
        # Update stock if requested
        if update_stock:
            c.execute("""
                UPDATE products SET stock_qty = ? WHERE id = ?
            """, (count['counted_qty'], count['product_id']))
        
        conn.commit()
        return {'success': True, 'message': 'تم اعتماد الجرد'}
    except Exception as e:
        conn.rollback()
        return {'success': False, 'message': str(e)}
    finally:
        conn.close()

def reject_inventory_count(count_id, reviewer_id):
    """Reject an inventory count."""
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("""
            UPDATE inventory_counts 
            SET status = 'rejected', reviewed_by = ?, reviewed_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (reviewer_id, count_id))
        conn.commit()
        return {'success': True, 'message': 'تم رفض الجرد'}
    except Exception as e:
        conn.rollback()
        return {'success': False, 'message': str(e)}
    finally:
        conn.close()

# Initialize inventory table on import
try:
    init_inventory_table()
except:
    pass

# ═══════════════════════════════════════════════════════════════════
# 🔴 LASER OPS CENTER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════

def get_laser_queue_summary():
    """Returns aggregated quantities for products in 'Under Preparation' orders."""
    conn = get_db_connection()
    # Filter strictly by 'Under Preparation'
    query = """
    SELECT p.name as product_name, SUM(oi.qty) as total_qty, COUNT(DISTINCT o.id) as order_count 
    FROM order_items oi 
    JOIN orders o ON oi.order_id = o.id 
    JOIN products p ON oi.product_id = p.id 
    WHERE o.status = 'Under Preparation' 
    GROUP BY p.name 
    HAVING SUM(oi.qty) > 0
    ORDER BY total_qty DESC
    """
    results = conn.execute(query).fetchall()
    conn.close()
    return [dict(row) for row in results]

def add_production_task(task_type='manual', ref_image=None, qty=1, notes=''):
    """Add a new production task (manual photo task)."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''INSERT INTO production_tasks (type, reference_image, quantity, status, notes)
                 VALUES (?, ?, ?, 'pending', ?)''',
              (task_type, ref_image, qty, notes))
    task_id = c.lastrowid
    conn.commit()
    conn.close()
    return task_id

def get_production_tasks(status='pending'):
    """Get all production tasks, optionally filtered by status."""
    conn = get_db_connection()
    c = conn.cursor()
    if status:
        rows = c.execute('SELECT * FROM production_tasks WHERE status = ? ORDER BY created_at DESC', (status,)).fetchall()
    else:
        rows = c.execute('SELECT * FROM production_tasks ORDER BY created_at DESC').fetchall()
    conn.close()
    return [dict(r) for r in rows]

def complete_production_task(task_id):
    """Mark a production task as completed."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('UPDATE production_tasks SET status = ?, completed_at = CURRENT_TIMESTAMP WHERE id = ?',
              ('completed', task_id))
    conn.commit()
    conn.close()
    return True

def delete_production_task(task_id):
    """Delete a production task."""
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('DELETE FROM production_tasks WHERE id = ?', (task_id,))
    conn.commit()
    conn.close()
    return True

def get_laser_queue_summary():
    """Aggregates products from 'Under Preparation' orders."""
    conn = get_db_connection()
    # Join order_items and orders
    # Filter by status 'Under Preparation'
    # Group by product_name
    query = """
        SELECT 
            oi.product_name, 
            SUM(oi.qty) as total_qty, 
            COUNT(DISTINCT o.id) as order_count
        FROM order_items oi
        JOIN orders o ON oi.order_id = o.id
        WHERE o.status = 'Under Preparation'
        GROUP BY oi.product_name
        ORDER BY total_qty DESC
    """
    rows = conn.execute(query).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_active_laser_tasks():
    """Alias for get_production_tasks('pending') for API compatibility."""
    return get_production_tasks('pending')


# ===================================================================
# 📈 NEXT-GEN FINANCIAL ERP FUNCTIONS (PHASE 1 & 3)
# ===================================================================

def get_daily_archive():
    """Returns all recorded daily snapshots from the archive."""
    conn = get_db_connection()
    try:
        rows = conn.execute("SELECT * FROM daily_financial_archive ORDER BY date DESC LIMIT 100").fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"Error in get_daily_archive: {e}")
        return []
    finally:
        conn.close()


def get_scheduled_obligations():
    """Returns all active scheduled obligations."""
    conn = get_db_connection()
    try:
        rows = conn.execute("SELECT * FROM scheduled_obligations ORDER BY next_due_date ASC").fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"Error in get_scheduled_obligations: {e}")
        return []
    finally:
        conn.close()


def add_scheduled_obligation(title, total_monthly_amount, weekly_deduction_target, next_due_date, is_recurring=1):
    """Inserts a new scheduled obligation with computed daily/weekly targets."""
    conn = get_db_connection()
    try:
        daily_target = total_monthly_amount / 30.0
        weekly_target = total_monthly_amount / 4.0
        conn.execute("""
            INSERT INTO scheduled_obligations (title, total_monthly_amount, weekly_deduction_target, accumulated_amount, next_due_date, is_recurring, daily_target_amount, weekly_target_amount, paid_days, paid_weeks)
            VALUES (?, ?, ?, 0, ?, ?, ?, ?, 0, 0)
        """, (title, total_monthly_amount, weekly_deduction_target, next_due_date, is_recurring, daily_target, weekly_target))
        conn.commit()
        return {"success": True}
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


def delete_scheduled_obligation(ob_id):
    """Deletes a scheduled obligation by ID."""
    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM scheduled_obligations WHERE id = ?", (ob_id,))
        conn.commit()
        return {"success": True}
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


def get_obligation_history(ob_id):
    """Returns payment history for a specific obligation."""
    conn = get_db_connection()
    try:
        rows = conn.execute("""
            SELECT id, ob_id, amount_paid, payment_type, date
            FROM obligation_payments_history
            WHERE ob_id = ?
            ORDER BY date DESC
        """, (ob_id,)).fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"Error in get_obligation_history: {e}")
        return []
    finally:
        conn.close()


def update_scheduled_obligation(ob_id, title, total_monthly_amount):
    """Updates title and total_monthly_amount of a scheduled obligation, recalculating targets."""
    conn = get_db_connection()
    try:
        daily_target = total_monthly_amount / 30.0
        weekly_target = total_monthly_amount / 4.0
        conn.execute("""
            UPDATE scheduled_obligations
            SET title = ?, total_monthly_amount = ?, daily_target_amount = ?, weekly_target_amount = ?
            WHERE id = ?
        """, (title, total_monthly_amount, daily_target, weekly_target, ob_id))
        conn.commit()
        return {"success": True}
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


def get_shortages():
    """Returns all pending shortages."""
    conn = get_db_connection()
    try:
        rows = conn.execute("SELECT * FROM shortages WHERE status = 'pending' ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"Error in get_shortages: {e}")
        return []
    finally:
        conn.close()


def add_shortage(name, estimated_cost, qty=1):
    """Adds a new manual shortage item."""
    conn = get_db_connection()
    try:
        conn.execute("""
            INSERT INTO shortages (name, estimated_cost, qty, status)
            VALUES (?, ?, ?, 'pending')
        """, (name, estimated_cost, qty))
        conn.commit()
        return {"success": True}
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


def purchase_shortage_db(shortage_id):
    """Marks a shortage item as purchased."""
    conn = get_db_connection()
    try:
        conn.execute("UPDATE shortages SET status = 'purchased' WHERE id = ?", (shortage_id,))
        conn.commit()
        return {"success": True}
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()


def get_shift_history():
    """Returns all closed daily shifts."""
    conn = get_db_connection()
    try:
        rows = conn.execute("SELECT * FROM daily_shifts WHERE status = 'closed' ORDER BY closed_at DESC").fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"Error in get_shift_history: {e}")
        return []
    finally:
        conn.close()


def update_client_details(client_id, name, phone, c_type, notes):
    """FIXED (pos-writer 2026-10-11): function was called by app.py:510 and backend.py:125
    but never defined anywhere in the active code — editing a client from the UI failed.
    Signature matches both call sites: (client_id, name, phone, c_type, notes)."""
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("UPDATE clients SET name=?, phone=?, type=?, notes=? WHERE id=?",
                  (name, phone, c_type, notes, client_id))
        conn.commit()
        return {"success": True}
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()
