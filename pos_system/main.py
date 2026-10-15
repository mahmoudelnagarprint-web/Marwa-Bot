import flet as ft
import sqlite3
import requests
import datetime
import json
import threading
import time
import os
import subprocess
import sys

# ==========================================
# 🚀 ELNAGAR POS MOBILE - 2026 FLAGSHIP EDITION
# Architecture: Flet v0.8.0 Safe | Offline-First
# ==========================================

# --- CONFIGURATION ---
DB_NAME = "mobile.db"
SERVER_URL_DEFAULT = "http://127.0.0.1:7777"

# --- THEME CONSTANTS ---
BG_COLOR = "#0F172A"
CARD_COLOR = "#1E293B"
PRIMARY = "#3B82F6"
SUCCESS = "#10B981"
WARNING = "#F59E0B"
ERROR = "#EF4444"
TEXT_MAIN = "#F8FAFC"
TEXT_SEC = "#94A3B8"

# --- 1. CORE ENGINE (DATABASE) ---
class MobileDB:
    def __init__(self):
        self.conn = sqlite3.connect(DB_NAME, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
        c = self.conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS clients (id INTEGER PRIMARY KEY, name TEXT, balance REAL DEFAULT 0, type TEXT DEFAULT 'Retail', phone TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS products (id INTEGER PRIMARY KEY, name TEXT, price_retail REAL DEFAULT 0, price_wholesale REAL DEFAULT 0, category TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS suppliers (id INTEGER PRIMARY KEY, name TEXT, phone TEXT, balance REAL DEFAULT 0)")
        c.execute("CREATE TABLE IF NOT EXISTS transactions (id INTEGER PRIMARY KEY, client_id INTEGER, type TEXT, amount REAL, date TEXT, notes TEXT)")
        c.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                client_id INTEGER, client_name TEXT, total REAL, 
                json_items TEXT, notes TEXT, status TEXT DEFAULT 'Under Preparation',
                is_synced INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                local_images TEXT,
                delivery_date TEXT,
                custom_notes TEXT
            )
        """)
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('server_url', ?)", (SERVER_URL_DEFAULT,))
        
        # Migration: Add missing columns
        try: c.execute("ALTER TABLE clients ADD COLUMN phone TEXT")
        except: pass
        try: c.execute("ALTER TABLE clients ADD COLUMN type TEXT DEFAULT 'Retail'")
        except: pass
        try: c.execute("ALTER TABLE orders ADD COLUMN local_images TEXT")
        except: pass
        try: c.execute("ALTER TABLE orders ADD COLUMN delivery_date TEXT")
        except: pass
        try: c.execute("ALTER TABLE orders ADD COLUMN custom_notes TEXT")
        except: pass
        
        self.conn.commit()

    def get_setting(self, k):
        res = self.conn.execute("SELECT value FROM settings WHERE key=?", (k,)).fetchone()
        return res[0] if res else ""

    def save_setting(self, k, v):
        self.conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)", (k, str(v)))
        self.conn.commit()

    def get_list(self, table):
        return [dict(r) for r in self.conn.execute(f"SELECT * FROM {table}").fetchall()]

    def add_order(self, client_id, name, total, items, notes, files=[], delivery_date=None, custom_notes=None):
        import json
        self.conn.execute(
            """
            INSERT INTO orders (client_id, client_name, total, json_items, notes, local_images, delivery_date, custom_notes)
            VALUES (?,?,?,?,?,?,?,?)
            """,
            (client_id, name, total, json.dumps(items), notes, json.dumps(files), delivery_date, custom_notes if custom_notes is not None else notes)
        )
        self.conn.commit()

    def update_order_status(self, order_id, new_status):
        self.conn.execute("UPDATE orders SET status=? WHERE id=?", (new_status, order_id))
        self.conn.commit()

    def delete_order(self, order_id):
        self.conn.execute("DELETE FROM orders WHERE id=?", (order_id,))
        self.conn.commit()

    def get_client_statement(self, client_id):
        c = self.conn.cursor()
        client = c.execute("SELECT * FROM clients WHERE id=?", (client_id,)).fetchone()
        if not client: return None
        
        total_sales = c.execute("SELECT SUM(amount) FROM transactions WHERE client_id=? AND type='Order'", (client_id,)).fetchone()[0] or 0
        total_paid = c.execute("SELECT SUM(amount) FROM transactions WHERE client_id=? AND type='Payment'", (client_id,)).fetchone()[0] or 0
        transactions = c.execute("SELECT * FROM transactions WHERE client_id=? ORDER BY date DESC LIMIT 20", (client_id,)).fetchall()
        
        return {
            "name": dict(client)['name'],
            "balance": dict(client)['balance'],
            "total_sales": total_sales,
            "total_paid": total_paid,
            "transactions": [dict(t) for t in transactions]
        }

    def add_payment(self, client_id, amount, notes=""):
        today = datetime.date.today().isoformat()
        self.conn.execute("INSERT INTO transactions (client_id, type, amount, date, notes) VALUES (?,?,?,?,?)",
                         (client_id, 'Payment', amount, today, notes))
        # Update client balance
        self.conn.execute("UPDATE clients SET balance = balance - ? WHERE id=?", (amount, client_id))
        self.conn.commit()

    def get_dashboard_stats(self):
        today = datetime.date.today().isoformat()
        sales_today = self.conn.execute("SELECT COUNT(*) FROM orders WHERE date(created_at) = ?", (today,)).fetchone()[0]
        total_debt = self.conn.execute("SELECT SUM(balance) FROM clients WHERE balance > 0").fetchone()[0] or 0
        unsynced = self.conn.execute("SELECT COUNT(*) FROM orders WHERE is_synced=0").fetchone()[0]
        return {"sales": sales_today, "debt": total_debt, "unsynced": unsynced}

mdb = MobileDB()

# --- 2. UI COMPONENTS (SAFE) ---
def ModernText(text, size=14, color=TEXT_MAIN, weight=None):
    return ft.Text(str(text), size=size, color=color, weight=weight)

class ModernCard(ft.Container):
    def __init__(self, content, color=CARD_COLOR, padding=15, height=None, on_click=None):
        super().__init__(
            content=content,
            bgcolor=color,
            padding=padding,
            border_radius=16,
            height=height,
            on_click=on_click
        )

class StatCard(ModernCard):
    def __init__(self, label, value, emoji, accent_color):
        super().__init__(
            content=ft.Column([
                ft.Row([
                    ModernText(emoji, size=24),
                    ModernText(label, size=12, color=TEXT_SEC, weight="bold")
                ], alignment="spaceBetween"),
                ModernText(str(value), size=28, weight="bold", color=TEXT_MAIN)
            ])
        )

def ModernButton(text, icon_emoji="", color=PRIMARY, on_click=None, width=None):
    return ft.Container(
        content=ft.Row([
            ft.Text(icon_emoji, size=18) if icon_emoji else ft.Container(),
            ModernText(text, weight="bold", color="white")
        ], alignment="center", spacing=8),
        bgcolor=color,
        padding=12,
        border_radius=12,
        on_click=on_click,
        width=width,
        alignment=ft.Alignment(0, 0)
    )

# --- 3. SYNC ENGINE ---
def run_sync(page, feedback_container):
    feedback_container.content = ModernText("⏳ جاري المزامنة...", color=WARNING)
    page.update()
    
    try:
        server = mdb.get_setting('server_url')
        
        # 1. PUSH Unsynced Orders (Local -> Server)
        unsynced_orders = mdb.conn.execute("SELECT * FROM orders WHERE is_synced=0").fetchall()
        for ord in unsynced_orders:
            try:
                payload = {
                    'client_name': ord['client_name'],
                    'total': ord['total'],
                    'items': ord['json_items'], 
                    'notes': ord['notes'],
                    'delivery_date': ord['delivery_date'],
                    'custom_notes': ord['custom_notes'],
                }
                
                # Check for images to upload
                files = []
                if ord['local_images']:
                    import json
                    img_paths = json.loads(ord['local_images'])
                    for p in img_paths:
                        if os.path.exists(p):
                            files.append(('images', (os.path.basename(p), open(p, 'rb'))))
                
                push_r = requests.post(
                    f"{server}/api/mobile/add_order", 
                    data=payload, # Use data for multipart
                    files=files if files else None,
                    timeout=20 # Increased timeout for images
                )
                
                # Close files
                for _, (_, f) in files: f.close()

                if push_r.status_code == 200:
                    mdb.conn.execute("UPDATE orders SET is_synced=1 WHERE id=?", (ord['id'],))
            except: pass
        mdb.conn.commit()

        # 2. PULL Full Data (Server -> Local)
        r = requests.get(f"{server}/api/get_full_data", timeout=10)
        if r.status_code == 200:
            data = r.json()
            c = mdb.conn.cursor()
            
            # Sync Clients
            c.execute("DELETE FROM clients")
            for cl in data.get('customers', []):
                c.execute("INSERT INTO clients (id, name, balance, type, phone) VALUES (?,?,?,?,?)",
                         (cl.get('id'), cl.get('name'), cl.get('total_debt', 0), cl.get('type', 'Retail'), cl.get('phone', '')))
            
            # Sync Products
            c.execute("DELETE FROM products")
            for p in data.get('products', []):
                c.execute("INSERT INTO products (id, name, price_retail, price_wholesale, category) VALUES (?,?,?,?,?)",
                         (p.get('id'), p.get('name'), p.get('price', 0), p.get('price_wholesale', 0), p.get('category', '')))
            
            # Sync Orders (NEW!)
            c.execute("DELETE FROM orders WHERE is_synced=1")  # Only delete synced orders
            for o in data.get('orders', []):
                # Check if order exists locally
                existing = c.execute("SELECT id FROM orders WHERE id=?", (o.get('id'),)).fetchone()
                if not existing:
                    c.execute(
                        """
                        INSERT INTO orders (id, client_name, total, status, notes, is_synced, created_at, delivery_date, custom_notes)
                        VALUES (?,?,?,?,?,1,?,?,?)
                        """,
                        (
                            o.get('id'),
                            o.get('client'),
                            o.get('total', 0),
                            o.get('status', 'Under Preparation'),
                            o.get('notes', ''),
                            o.get('date', ''),
                            o.get('delivery_date'),
                            o.get('custom_notes'),
                        ),
                    )
                else:
                    # Update existing
                    c.execute(
                        """
                        UPDATE orders
                        SET status=?, is_synced=1, delivery_date=?, custom_notes=?, notes=?
                        WHERE id=?
                        """,
                        (
                            o.get('status'),
                            o.get('delivery_date'),
                            o.get('custom_notes'),
                            o.get('notes', ''),
                            o.get('id'),
                        ),
                    )
            
            mdb.conn.commit()
            feedback_container.content = ModernText("✅ تمت المزامنة بنجاح!", color=SUCCESS)
        else:
            feedback_container.content = ModernText(f"❌ خطأ سيرفر: {r.status_code}", color=ERROR)
    except Exception as e:
        feedback_container.content = ModernText(f"❌ فشل: {str(e)[:30]}", color=ERROR)
    page.update()

# --- 4. MAIN APPLICATION ---
def main(page: ft.Page):
    page.title = "Elnagar POS 2026"
    page.theme_mode = "dark"
    page.bgcolor = BG_COLOR
    page.rtl = True
    page.padding = 0

    # State
    current_idx = [0]
    body = ft.Container(expand=True, padding=15)
    sync_feedback = ft.Container(content=ft.Text(""))

    # --- VIEW: DASHBOARD ---
    def show_dashboard():
        stats = mdb.get_dashboard_stats()
        body.content = ft.Column([
            ft.Row([
                ModernText("مركز التحكم", size=24, weight="bold"),
                ModernButton("⚙️", width=50, color=CARD_COLOR, on_click=lambda _: show_settings())
            ], alignment="spaceBetween"),
            
            StatCard("نقدية اليوم", f"{stats['sales']} طلب", "💰", SUCCESS),
            StatCard("إجمالي الديون", f"{stats['debt']:,.0f}", "📉", ERROR),
            StatCard("قيد المزامنة", f"{stats['unsynced']} طلب", "⏳", WARNING),
            
            sync_feedback,
            ModernButton("🔄 مزامنة البيانات الآن", on_click=lambda _: run_sync(page, sync_feedback)),
        ], spacing=15, scroll="auto")
        page.update()

    # --- VIEW: ORDERS ---
    def show_orders(filter_status="All"):
        orders = mdb.get_list('orders')
        
        # Apply filter
        if filter_status == "Processing":
            orders = [o for o in orders if o['status'] == 'Under Preparation']
        elif filter_status == "Done":
            orders = [o for o in orders if o['status'] == 'Done']
        
        def change_status(o_id, new_st):
            mdb.update_order_status(o_id, new_st)
            # Push to server
            try:
                server = mdb.get_setting('server_url')
                requests.post(f"{server}/api/mobile/update_order_status", 
                             json={'order_id': o_id, 'status': new_st}, timeout=5)
            except: pass
            show_orders(filter_status)
        
        def delete_order(o_id):
            mdb.delete_order(o_id)
            # Push to server
            try:
                server = mdb.get_setting('server_url')
                requests.post(f"{server}/api/mobile/delete_order", 
                             json={'order_id': o_id}, timeout=5)
            except: pass
            show_orders(filter_status)

        order_cards = []
        for o in orders:
            status_color = SUCCESS if o['status'] == 'Done' else (WARNING if o['status'] == 'Under Preparation' else TEXT_SEC)
            order_cards.append(
                ModernCard(ft.Column([
                    ft.Row([
                        ModernText(o['client_name'], weight="bold"),
                        ModernText(f"{o['total']:,.0f}", color=SUCCESS, weight="bold")
                    ], alignment="spaceBetween"),
                    ft.Row([
                        ModernText(f"#{o['id']}", size=12, color=TEXT_SEC),
                        ft.Container(
                            content=ModernText(o['status'], size=10, color="white"),
                            bgcolor=status_color, padding=5, border_radius=8
                        )
                    ], alignment="spaceBetween"),
                    ft.Divider(color="#333333"),
                    ft.Row([
                        ModernButton("✅ تم", color=SUCCESS, width=70, on_click=lambda _, oid=o['id']: change_status(oid, "Done")),
                        ModernButton("⏳ تجهيز", color=WARNING, width=80, on_click=lambda _, oid=o['id']: change_status(oid, "Under Preparation")),
                        ModernButton("🗑️", color=ERROR, width=50, on_click=lambda _, oid=o['id']: delete_order(oid)),
                    ], spacing=5)
                ]))
            )
        
        # Filter Tabs
        filter_row = ft.Row([
            ModernButton("📋 الكل", color=PRIMARY if filter_status=="All" else CARD_COLOR, width=90, on_click=lambda _: show_orders("All")),
            ModernButton("⏳ تجهيز", color=WARNING if filter_status=="Processing" else CARD_COLOR, width=90, on_click=lambda _: show_orders("Processing")),
            ModernButton("✅ تم", color=SUCCESS if filter_status=="Done" else CARD_COLOR, width=90, on_click=lambda _: show_orders("Done")),
        ], spacing=5, scroll="auto")
        
        body.content = ft.Column([
            ModernText("سجل الطلبات", size=24, weight="bold"),
            filter_row,
            ft.Divider(color="#333333"),
            ft.Column(order_cards, scroll="auto", expand=True) if order_cards else ModernText("لا توجد طلبات في هذا القسم", color=TEXT_SEC)
        ], spacing=15)
        page.update()

    # --- VIEW: NEW ORDER ---
    class NewOrderView:
        def __init__(self, pg, body_container, show_orders_callback):
            self.pg = pg
            self.body = body_container
            self.show_orders_callback = show_orders_callback
            self.cart = []
            self.products = mdb.get_list('products')
            self.clients = mdb.get_list('clients')
            self.selected_files = [] # Track selected files

            # File Picker (Safe Init)
            # File Picker (DISABLED due to v0.8.0 incompatibility)
            self.file_picker = None

            # --- Product Selection Dialog ---
            self.prod_dropdown = ft.Dropdown(
                label="المنتج",
                options=[ft.dropdown.Option(p['name']) for p in self.products],
                border_radius=12, filled=True, bgcolor=CARD_COLOR, expand=True
            )
            # Property assignment separate from constructor
            self.prod_dropdown.on_change = self.select_product_from_dialog

            self.product_dialog = ft.AlertDialog(
                modal=True,
                title=ModernText("اختر منتج"),
                content=ft.Column([
                    self.prod_dropdown
                ], height=200, scroll="auto"),
                actions=[
                    ModernButton("إلغاء", on_click=self.close_prod_dialog)
                ]
            )
            self.pg.overlay.append(self.product_dialog)

            # --- Add New Product Dialog (Placeholder for future functionality) ---
            self.add_prod_dialog = ft.AlertDialog(
                modal=True,
                title=ModernText("إضافة منتج جديد"),
                content=ModernText("هذه الميزة قيد التطوير."),
                actions=[
                    ModernButton("حسناً", on_click=lambda e: self.close_add_prod_dialog())
                ]
            )
            self.pg.overlay.append(self.add_prod_dialog)

            self.client_picker = ft.Dropdown(
                label="العميل",
                options=[ft.dropdown.Option(c['name']) for c in self.clients],
                border_radius=12, filled=True, bgcolor=CARD_COLOR
            )
            
            # Selection UI
            self.selected_prod_txt = ModernText("لم يتم اختيار منتج", color=TEXT_SEC)
            self.select_prod_btn = ModernButton("اختر المنتج 📦", color=CARD_COLOR, on_click=self.open_prod_dialog)
            self.add_prod_btn = ModernButton("➕", width=50, on_click=self.open_add_prod_dialog)
            
            # Disable upload if picker failed
            if self.file_picker:
                self.upload_btn = ModernButton("📸 رفع صور", color=CARD_COLOR, on_click=lambda _: self.file_picker.pick_files(allow_multiple=True))
            else:
                self.upload_btn = ModernButton("📸 (غير مدعوم)", color=ERROR)
                
            self.files_txt = ModernText("", size=12, color=TEXT_SEC)

            self.qty_input = ft.TextField(label="الكمية", value="1", width=80, border_radius=12, filled=True, bgcolor=CARD_COLOR)
            self.delivery_date_input = ft.TextField(
                label="تاريخ التسليم",
                value=datetime.date.today().isoformat(),
                border_radius=12,
                filled=True,
                bgcolor=CARD_COLOR,
            )
            self.custom_notes_input = ft.TextField(
                label="ملاحظات التشغيل",
                border_radius=12,
                filled=True,
                bgcolor=CARD_COLOR,
                multiline=True,
                min_lines=2,
                max_lines=3,
            )
            self.cart_list = ft.Column(scroll="auto", expand=True)
            self.total_txt = ModernText("0", size=28, weight="bold", color=SUCCESS)

        def open_prod_dialog(self, e):
            self.pg.dialog = self.product_dialog
            self.product_dialog.open = True
            self.pg.update()

        def close_prod_dialog(self, e):
            self.product_dialog.open = False
            self.pg.update()

        def select_product_from_dialog(self, e):
            self.selected_product = next((p for p in self.products if p['name'] == e.control.value), None)
            if self.selected_product:
                self.selected_prod_txt.value = self.selected_product['name']
            self.close_prod_dialog(e)
            self.pg.update()

        def open_add_prod_dialog(self, e):
            self.pg.dialog = self.add_prod_dialog
            self.add_prod_dialog.open = True
            self.pg.update()

        def close_add_prod_dialog(self):
            self.add_prod_dialog.open = False
            self.pg.update()

        def update_total(self):
            self.total_txt.value = f"{sum(i['price'] for i in self.cart):,.0f}"

        def add_to_cart(self, _):
            if not hasattr(self, 'selected_product') or not self.selected_product: return
            try:
                prod = self.selected_product
                qty = float(self.qty_input.value)
                price = prod['price_retail'] * qty
                # Store ID for sync
                self.cart.append({"id": prod['id'], "name": prod['name'], "qty": qty, "price": price})
                
                self.cart_list.controls.append(ft.Row([
                    ModernText(f"{qty}x {prod['name']}"),
                    ModernText(f"{price:.0f}", color=SUCCESS)
                ], alignment="spaceBetween"))
                self.update_total()
                self.pg.update()
            except Exception as e:
                print(f"Error adding to cart: {e}")

        def on_file_result(self, e: ft.FilePickerResultEvent):
            if e.files:
                self.selected_files = [f.path for f in e.files]
                self.files_txt.value = f"تم تحديد {len(self.selected_files)} صور"
                self.pg.update()

        def save_order(self, _):
            if not self.cart: return
            # Use 0 as client_id placeholder, sync will resolve by name
            mdb.add_order(
                0, 
                self.client_picker.value or "نقدي", 
                sum(i['price'] for i in self.cart), 
                self.cart, 
                "Mobile Order", 
                self.selected_files, # Pass files
                self.delivery_date_input.value.strip() or None,
                self.custom_notes_input.value.strip() or "Mobile Order",
            )
            # Clear UI
            self.cart = []
            self.selected_files = []
            self.files_txt.value = ""
            self.delivery_date_input.value = datetime.date.today().isoformat()
            self.custom_notes_input.value = ""
            self.cart_list.controls.clear()
            self.update_total()
            self.pg.update()
            
            self.show_orders_callback() # Go to orders hub
            self.pg.overlay.append(ft.SnackBar(ft.Text("تم حفظ الطلب محلياً ✅")))
            self.pg.update()

        def build(self):
            return ft.Column([
                ModernText("طلب جديد", size=24, weight="bold"),
                self.client_picker,
                # Product Section
                ft.Row([self.select_prod_btn, self.add_prod_btn], spacing=5),
                ft.Row([self.selected_prod_txt, self.qty_input], alignment="spaceBetween"),
                self.delivery_date_input,
                self.custom_notes_input,
                ft.Row([self.upload_btn, self.files_txt], spacing=10),
                
                ModernButton("إضافة للسلة ⬇️", color=CARD_COLOR, on_click=self.add_to_cart),
                
                ft.Divider(color=TEXT_SEC),
                self.cart_list,
                ft.Row([ModernText("الإجمالي:"), self.total_txt], alignment="spaceBetween"),
                ModernButton("💾 حفظ الطلب", on_click=self.save_order)
            ], spacing=15, scroll="auto")

    def show_new_order():
        new_order_view = NewOrderView(page, body, show_orders)
        body.content = new_order_view.build()
        page.update()

    # --- VIEW: CLIENTS ---
    def show_clients():
        clients = mdb.get_list('clients')

        def open_statement(client_id, client_name):
            data = mdb.get_client_statement(client_id)
            if not data:
                body.content = ModernText("خطأ في تحميل البيانات", color=ERROR)
                page.update()
                return
            
            # Payment Dialog
            payment_tf = ft.TextField(label="المبلغ", keyboard_type="number", border_radius=12)
            
            def submit_payment(_):
                try:
                    amount = float(payment_tf.value)
                    mdb.add_payment(client_id, amount)
                    open_statement(client_id, client_name) # Refresh
                except: pass

            trans_list = ft.Column(scroll="auto", height=200)
            for t in data['transactions']:
                color = SUCCESS if t['type'] == 'Payment' else ERROR
                trans_list.controls.append(ft.Row([
                    ModernText(t['date'], size=12, color=TEXT_SEC),
                    ModernText(t['type'], size=12),
                    ModernText(f"{t['amount']:,.0f}", color=color, weight="bold")
                ], alignment="spaceBetween"))

            body.content = ft.Column([
                ModernButton("⬅️ رجوع", color=CARD_COLOR, on_click=lambda _: show_clients()),
                ModernText(f"كشف حساب: {data['name']}", size=22, weight="bold"),
                
                ft.Row([
                    StatCard("إجمالي المبيعات", f"{data['total_sales']:,.0f}", "📦", PRIMARY),
                ]),
                ft.Row([
                    StatCard("إجمالي المدفوع", f"{data['total_paid']:,.0f}", "💵", SUCCESS),
                ]),
                ft.Row([
                    StatCard("الرصيد الحالي", f"{data['balance']:,.0f}", "💳", ERROR),
                ]),
                
                ft.Divider(color="#333333"),
                ModernText("سداد دفعة جديدة", weight="bold"),
                ft.Row([payment_tf, ModernButton("💵 سداد", on_click=submit_payment, width=100)], spacing=5),
                
                ft.Divider(color="#333333"),
                ModernText("آخر الحركات", weight="bold"),
                trans_list
            ], spacing=12, scroll="auto")
            page.update()

        client_cards = []
        for c in clients:
            balance_color = ERROR if c['balance'] > 0 else SUCCESS
            client_cards.append(
                ModernCard(
                    ft.Row([
                        ft.Column([
                            ModernText(c['name'], weight="bold"),
                            ModernText(c.get('type', 'Retail'), size=12, color=TEXT_SEC)
                        ]),
                        ft.Column([
                            ModernText(f"{c['balance']:,.0f}", color=balance_color, weight="bold"),
                            ModernButton("📜 كشف", width=80, on_click=lambda _, cid=c['id'], cname=c['name']: open_statement(cid, cname))
                        ], horizontal_alignment="end")
                    ], alignment="spaceBetween"),
                    on_click=lambda _, cid=c['id'], cname=c['name']: open_statement(cid, cname)
                )
            )
        
        body.content = ft.Column([
            ModernText("العملاء", size=24, weight="bold"),
            ft.Column(client_cards, scroll="auto", expand=True) if client_cards else ModernText("لا يوجد عملاء - قم بالمزامنة أولاً", color=TEXT_SEC)
        ], spacing=15)
        page.update()

    # --- VIEW: SETTINGS ---
    def show_settings():
        url_tf = ft.TextField(label="عنوان السيرفر", value=mdb.get_setting('server_url'), border_radius=12, filled=True, bgcolor=CARD_COLOR)
        
        def save_settings(_):
            mdb.save_setting('server_url', url_tf.value)
            show_dashboard()

        body.content = ft.Column([
            ModernText("الإعدادات", size=24, weight="bold"),
            url_tf,
            ModernButton("💾 حفظ", on_click=save_settings),
            ft.Divider(color="#333333"),
            ModernText("النسخة: 2026.1.28", size=12, color=TEXT_SEC)
        ], spacing=20)
        page.update()

    # --- NAVIGATION ---
    def open_laser_ops():
        script_path = os.path.join(os.path.dirname(__file__), "laser_ops.py")
        python_cmd = sys.executable or "python"
        try:
            subprocess.Popen([python_cmd, script_path], cwd=os.path.dirname(__file__))
        except Exception as exc:
            page.snack_bar = ft.SnackBar(ft.Text(f"تعذر فتح غرفة عمليات الليزر: {exc}"))
            page.snack_bar.open = True
            page.update()

    def nav_click(idx):
        current_idx[0] = idx
        if idx == 0: show_dashboard()
        elif idx == 1: show_orders()
        elif idx == 2: show_new_order()
        elif idx == 3: show_clients()
        elif idx == 4: show_settings()
        elif idx == 5: open_laser_ops()
        update_nav()

    nav_row = ft.Row(alignment="spaceAround")

    def update_nav():
        nav_row.controls.clear()
        items = [("🏠", "الرئيسية"), ("📋", "الطلبات"), ("➕", "إضافة"), ("👥", "العملاء"), ("⚙️", "إعدادات"), ("🔴", "الليزر")]
        for i, (icon, label) in enumerate(items):
            active = i == current_idx[0]
            color = PRIMARY if active else TEXT_SEC
            nav_row.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Text(icon, size=22 if active else 18, color=color),
                        ft.Text(label, size=10, color=color, weight="bold" if active else "normal")
                    ], spacing=2, horizontal_alignment="center"),
                    on_click=lambda _, x=i: nav_click(x),
                    padding=8
                )
            )
        page.update()

    # BOOT
    update_nav()
    show_dashboard()

    page.add(
        ft.Column([
            body,
            ft.Container(
                content=nav_row,
                bgcolor=CARD_COLOR,
                padding=10,
                height=70
            )
        ], expand=True, spacing=0)
    )

# ==========================================
# 🚀 FASTAPI HYBRID SERVER
# Serves both JSON API (for Chrome Extension)
# and the Flet Mobile UI on the same port.
# ==========================================
import database as db_module
import shutil
import os
import uuid
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Ensure directory exists
LASER_IMAGES_DIR = os.path.join("web", "laser_images")
os.makedirs(LASER_IMAGES_DIR, exist_ok=True)

# Allow Chrome Extension connection
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/laser_queue")
async def get_laser_queue():
    """Returns aggregated product list AND active manual tasks."""
    try:
        summary = db_module.get_laser_queue_summary()
        tasks = db_module.get_active_laser_tasks()
        return {"success": True, "aggregated": summary, "tasks": tasks}
    except Exception as e:
        return {"success": False, "message": str(e)}

@app.post("/api/laser_queue/upload")
async def add_laser_task(
    type: str = Form(...), 
    notes: str = Form(""), 
    file: UploadFile = File(None)
):
    try:
        image_filename = None
        if file:
            # Save file
            ext = file.filename.split(".")[-1]
            image_filename = f"{uuid.uuid4()}.{ext}"
            file_path = os.path.join(LASER_IMAGES_DIR, image_filename)
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
        
        db_module.add_production_task(notes, image_filename, 1, type)
        return {"success": True}
    except Exception as e:
        return {"success": False, "message": str(e)}

@app.delete("/api/laser_queue/done/{task_id}")
async def complete_laser_task(task_id: int):
    try:
        db_module.complete_production_task(task_id)
        return {"success": True}
    except Exception as e:
        return {"success": False, "message": str(e)}

# Serve images
app.mount("/api/laser_queue/file", StaticFiles(directory=LASER_IMAGES_DIR), name="laser_images")

# Mount Flet app at root - must be LAST (catch-all)
app.mount("/", ft.app(target=main, export_asgi_app=True))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8550)
