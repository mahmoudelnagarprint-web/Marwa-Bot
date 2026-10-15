import datetime
import json
import os
import sqlite3
import threading
import time
from uuid import uuid4

import flet as ft
import requests

# ==========================================
# ELNAGAR POS MOBILE (Offline-First)
# ==========================================

DEFAULT_SERVER = "http://127.0.0.1:7777"
DB_NAME = "elnagar_mobile_v2.db"
FONT_URL = "https://github.com/google/fonts/raw/main/ofl/cairo/Cairo-VariableFont_slnt%2Cwght.ttf"


class MobileDB:
    def __init__(self):
        self.conn = sqlite3.connect(DB_NAME, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._bootstrap()

    def _bootstrap(self):
        c = self.conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
        c.execute("CREATE TABLE IF NOT EXISTS clients (id INTEGER PRIMARY KEY, name TEXT, balance REAL, type TEXT)")
        c.execute(
            "CREATE TABLE IF NOT EXISTS products (id INTEGER PRIMARY KEY, name TEXT, price_retail REAL, price_wholesale REAL, category TEXT)"
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER,
                client_name TEXT,
                total REAL,
                json_items TEXT,
                notes TEXT,
                status TEXT DEFAULT 'Under Preparation',
                is_synced INTEGER DEFAULT 0,
                sync_attempts INTEGER DEFAULT 0,
                sync_error TEXT,
                external_order_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        c.execute("CREATE TABLE IF NOT EXISTS stats_cache (key TEXT PRIMARY KEY, value TEXT)")
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('server_url', ?)", (DEFAULT_SERVER,))

        for column_sql in [
            "ALTER TABLE orders ADD COLUMN sync_attempts INTEGER DEFAULT 0",
            "ALTER TABLE orders ADD COLUMN sync_error TEXT",
            "ALTER TABLE orders ADD COLUMN external_order_id TEXT",
        ]:
            try:
                c.execute(column_sql)
            except Exception:
                pass

        self.conn.commit()

    def get_setting(self, key, default=None):
        row = self.conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row[0] if row else default

    def set_setting(self, key, value):
        self.conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)", (key, str(value)))
        self.conn.commit()

    def get_stats(self):
        rows = self.conn.execute("SELECT * FROM stats_cache").fetchall()
        return {r["key"]: r["value"] for r in rows}

    def save_stats(self, stats_dict):
        for k, v in stats_dict.items():
            self.conn.execute("INSERT OR REPLACE INTO stats_cache (key, value) VALUES (?,?)", (k, str(v)))
        self.conn.commit()

    def get_clients(self):
        return [dict(r) for r in self.conn.execute("SELECT * FROM clients ORDER BY name").fetchall()]

    def get_products(self):
        return [dict(r) for r in self.conn.execute("SELECT * FROM products ORDER BY name").fetchall()]

    def add_offline_order(self, client_id, client_name, total, items, notes, external_order_id=None):
        ext_id = external_order_id or str(uuid4())
        payload = json.dumps(items, ensure_ascii=False)
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT INTO orders (client_id, client_name, total, json_items, notes, external_order_id)
            VALUES (?,?,?,?,?,?)
            """,
            (client_id, client_name, total, payload, notes, ext_id),
        )
        self.conn.commit()
        return cur.lastrowid, ext_id

    def get_unsynced_orders(self):
        return [
            dict(r)
            for r in self.conn.execute(
                "SELECT * FROM orders WHERE is_synced=0 ORDER BY created_at ASC, id ASC"
            ).fetchall()
        ]

    def get_unsynced_count(self):
        return self.conn.execute("SELECT COUNT(*) FROM orders WHERE is_synced=0").fetchone()[0]

    def mark_synced(self, order_id):
        self.conn.execute(
            "UPDATE orders SET is_synced=1, sync_error=NULL, sync_attempts=sync_attempts+1 WHERE id=?",
            (order_id,),
        )
        self.conn.commit()

    def mark_sync_error(self, order_id, error_text):
        self.conn.execute(
            "UPDATE orders SET sync_error=?, sync_attempts=sync_attempts+1 WHERE id=?",
            (str(error_text)[:500], order_id),
        )
        self.conn.commit()

    def get_dashboard_stats(self):
        today = datetime.date.today().isoformat()
        sales_today = self.conn.execute(
            "SELECT COUNT(*) FROM orders WHERE date(created_at) = ?", (today,)
        ).fetchone()[0]
        total_debt = self.conn.execute("SELECT SUM(balance) FROM clients WHERE balance > 0").fetchone()[0] or 0
        unsynced = self.get_unsynced_count()
        return {"sales": sales_today, "debt": total_debt, "unsynced": unsynced}


mdb = MobileDB()
sync_lock = threading.Lock()


class SyncEngine:
    @staticmethod
    def test_connection(url):
        try:
            r = requests.get(f"{url.rstrip('/')}/api/get_full_data", timeout=4)
            return r.status_code == 200
        except Exception:
            return False

    @staticmethod
    def _build_notes(notes, external_order_id):
        base = (notes or "").strip()
        ext_tag = f"ExtID: {external_order_id}"
        if ext_tag in base:
            return base
        if base:
            return f"{base} | {ext_tag}"
        return ext_tag

    @staticmethod
    def push_pending_orders():
        server = mdb.get_setting("server_url", DEFAULT_SERVER).rstrip("/")
        synced = 0
        for order in mdb.get_unsynced_orders():
            try:
                items = order.get("json_items", [])
                if isinstance(items, str):
                    items = json.loads(items or "[]")
                external_order_id = order.get("external_order_id") or f"mobile-{order['id']}"
                payload = {
                    "client_id": order.get("client_id"),
                    "client_name": order.get("client_name") or "نقدي",
                    "total": order.get("total", 0),
                    "items": items,
                    "notes": SyncEngine._build_notes(order.get("notes", ""), external_order_id),
                    "external_order_id": external_order_id,
                }
                response = requests.post(f"{server}/api/mobile/add_order", json=payload, timeout=20)
                body = {}
                try:
                    body = response.json()
                except Exception:
                    body = {}

                if response.status_code == 200 and body.get("success", True):
                    mdb.mark_synced(order["id"])
                    synced += 1
                else:
                    mdb.mark_sync_error(order["id"], body.get("message") or body.get("error") or response.text)
            except Exception as exc:
                mdb.mark_sync_error(order["id"], str(exc))
        return synced

    @staticmethod
    def pull_data():
        server = mdb.get_setting("server_url", DEFAULT_SERVER).rstrip("/")
        r = requests.get(f"{server}/api/get_full_data", timeout=10)
        if r.status_code != 200:
            return False, f"خطأ سيرفر: {r.status_code}"

        data = r.json()
        c = mdb.conn.cursor()
        c.execute("DELETE FROM clients")
        for cl in data.get("customers", []):
            c.execute(
                "INSERT INTO clients (id, name, balance, type) VALUES (?,?,?,?)",
                (cl.get("id"), cl.get("name"), cl.get("total_debt", 0), cl.get("type", "Retail")),
            )

        c.execute("DELETE FROM products")
        for p in data.get("products", []):
            c.execute(
                "INSERT INTO products (id, name, price_retail, price_wholesale, category) VALUES (?,?,?,?,?)",
                (
                    p.get("id"),
                    p.get("name"),
                    p.get("price", 0),
                    p.get("price_wholesale", 0),
                    p.get("category", ""),
                ),
            )

        mdb.save_stats(
            {
                "total_debt": f"{sum(cl.get('total_debt', 0) for cl in data.get('customers', [])):,.0f}",
                "today_sales": f"{len(data.get('orders', []))}",
                "unsynced": str(mdb.get_unsynced_count()),
            }
        )
        mdb.conn.commit()
        return True, "تم تحديث البيانات بنجاح"

    @staticmethod
    def sync_all():
        with sync_lock:
            pushed = SyncEngine.push_pending_orders()
            pulled_ok, message = SyncEngine.pull_data()
            return {"success": pulled_ok, "message": message, "pushed": pushed}


class SafeCard(ft.Container):
    def __init__(self, title, value, emoji, color):
        super().__init__(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Text(emoji, size=28),
                            ft.Text(title, size=14, color="grey", weight="bold"),
                        ],
                        alignment="spaceBetween",
                    ),
                    ft.Text(value, size=32, weight="bold", color="white"),
                ],
                spacing=10,
            ),
            padding=20,
            border_radius=20,
            bgcolor="#1f2937",
            expand=True,
        )


def main(page: ft.Page):
    page.title = "Elnagar POS Mobile"
    page.theme_mode = "dark"
    page.bgcolor = "#111827"
    page.rtl = True
    page.padding = 0
    page.fonts = {"Cairo": FONT_URL}
    page.theme = ft.Theme(font_family="Cairo")

    main_view = ft.Container(expand=True, padding=20)
    main_view.current_nav_idx = 0
    conn_status = ft.Text("🔴 غير متصل", size=12, color="red")
    sync_feedback = ft.Text("", size=12, color="grey")

    def refresh_dashboard_feedback():
        stats = mdb.get_dashboard_stats()
        if hasattr(main_view, "content") and isinstance(main_view.content, ft.Column):
            for ctrl in main_view.content.controls:
                if isinstance(ctrl, ft.Container) and getattr(ctrl, "data", None) == "unsynced_card":
                    try:
                        ctrl.content.controls[1].value = f"طلبات غير مزامنة: {stats['unsynced']}"
                    except Exception:
                        pass
        page.update()

    def show_dashboard():
        stats = mdb.get_dashboard_stats()
        main_view.content = ft.Column(
            [
                ft.Row([ft.Text("مركز التحكم", size=28, weight="bold"), conn_status], alignment="spaceBetween"),
                ft.Row(
                    [
                        SafeCard("مبيعات اليوم", stats.get("sales", 0), "🛒", "#F59E0B"),
                        SafeCard("إجمالي الديون", stats.get("debt", 0), "💳", "#EF4444"),
                    ]
                ),
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Text("☁️", size=20),
                            ft.Text(f"طلبات غير مزامنة: {stats.get('unsynced', 0)}", weight="bold"),
                        ],
                        alignment="center",
                    ),
                    bgcolor="#3B82F6",
                    padding=15,
                    border_radius=15,
                    data="unsynced_card",
                    on_click=lambda _: on_nav_click(1),
                ),
                sync_feedback,
            ],
            spacing=25,
            scroll="auto",
        )
        page.update()

    def show_orders():
        orders = mdb.get_unsynced_orders()
        all_orders = [dict(r) for r in mdb.conn.execute("SELECT * FROM orders ORDER BY created_at DESC, id DESC").fetchall()]

        def sync_now(_):
            with sync_lock:
                result = SyncEngine.sync_all()
            sync_feedback.value = f"{'✅' if result['success'] else '❌'} {result['message']} | تم رفع: {result['pushed']}"
            refresh_dashboard_feedback()
            show_orders()

        cards = []
        for o in all_orders:
            status = "مزامن" if o.get("is_synced") else "بانتظار المزامنة"
            color = "#10B981" if o.get("is_synced") else "#F59E0B"
            cards.append(
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Text(o.get("client_name") or "نقدي", weight="bold"),
                                    ft.Text(f"{o.get('total', 0):,.0f} ج.م", color="#10B981", weight="bold"),
                                ],
                                alignment="spaceBetween",
                            ),
                            ft.Row(
                                [
                                    ft.Text(f"#{o.get('id')}"),
                                    ft.Container(
                                        content=ft.Text(status, size=10, color="white"),
                                        bgcolor=color,
                                        padding=5,
                                        border_radius=8,
                                    ),
                                ],
                                alignment="spaceBetween",
                            ),
                            ft.Text(o.get("notes") or "", size=12, color="grey"),
                        ]
                    ),
                    padding=15,
                    bgcolor="#1f2937",
                    border_radius=15,
                )
            )

        main_view.content = ft.Column(
            [
                ft.Row(
                    [
                        ft.Text("سجل الطلبات", size=28, weight="bold"),
                        ft.ElevatedButton("مزامنة الآن", on_click=sync_now),
                    ],
                    alignment="spaceBetween",
                ),
                ft.Text(f"الطلبات غير المزامنة: {len(orders)}", color="#F59E0B", weight="bold"),
                ft.Column(cards, scroll="auto", expand=True) if cards else ft.Text("لا توجد طلبات محلية بعد", color="grey"),
            ],
            spacing=15,
            expand=True,
            scroll="auto",
        )
        page.update()

    def show_pos():
        products = mdb.get_products()
        clients = mdb.get_clients()
        cart = []
        selected_product = {"value": None}

        client_picker = ft.Dropdown(
            label="اختر العميل",
            options=[ft.dropdown.Option(c["name"]) for c in clients] or [ft.dropdown.Option("نقدي")],
            value="نقدي" if not clients else None,
            expand=True,
            border_radius=10,
        )
        product_picker = ft.Dropdown(
            label="المنتج",
            options=[ft.dropdown.Option(p["name"]) for p in products],
            expand=True,
            border_radius=10,
        )
        qty_field = ft.TextField(label="الكمية", value="1", width=110, border_radius=10)
        cart_list = ft.Column(scroll="auto", expand=True)
        total_text = ft.Text("0", size=28, weight="bold", color="#10B981")
        order_feedback = ft.Text("", size=12, color="grey")

        def find_product(name):
            return next((p for p in products if p["name"] == name), None)

        def update_total():
            total_text.value = f"{sum(item['total'] for item in cart):,.0f}"

        def add_to_cart(_):
            prod = find_product(product_picker.value)
            if not prod:
                order_feedback.value = "اختر منتج أولًا"
                page.update()
                return
            try:
                qty = float(qty_field.value or "1")
                price = float(prod.get("price_retail") or 0)
                row_total = qty * price
                cart.append(
                    {
                        "id": prod.get("id"),
                        "name": prod.get("name"),
                        "qty": qty,
                        "price": price,
                        "total": row_total,
                    }
                )
                cart_list.controls.append(
                    ft.Row(
                        [
                            ft.Text(f"{qty}x {prod['name']}", expand=True),
                            ft.Text(f"{row_total:,.0f}", color="#10B981", weight="bold"),
                        ],
                        alignment="spaceBetween",
                    )
                )
                update_total()
                order_feedback.value = "تمت الإضافة للسلة"
                page.update()
            except Exception as exc:
                order_feedback.value = f"خطأ في إضافة المنتج: {exc}"
                page.update()

        def save_order(_):
            if not cart:
                order_feedback.value = "السلة فارغة"
                page.update()
                return

            client_name = client_picker.value or "نقدي"
            client = next((c for c in clients if c["name"] == client_name), None)
            order_id, external_order_id = mdb.add_offline_order(
                client["id"] if client else 0,
                client_name,
                sum(item["total"] for item in cart),
                cart,
                "Mobile Order",
            )

            cart.clear()
            cart_list.controls.clear()
            update_total()
            order_feedback.value = f"تم حفظ الطلب محلياً #{order_id} | ExtID: {external_order_id}"
            refresh_dashboard_feedback()
            page.update()

        main_view.content = ft.Column(
            [
                ft.Text("إضافة طلب جديد", size=28, weight="bold"),
                client_picker,
                ft.Text("المنتجات", size=18, weight="bold"),
                product_picker,
                ft.Row([qty_field, ft.ElevatedButton("إضافة للسلة", on_click=add_to_cart)], spacing=10),
                ft.Container(
                    content=ft.Column([cart_list, ft.Divider(), ft.Row([ft.Text("الإجمالي:"), total_text], alignment="spaceBetween")], expand=True),
                    height=300,
                    padding=15,
                    bgcolor="#1f2937",
                    border_radius=15,
                ),
                ft.ElevatedButton("💾 حفظ الطلب", on_click=save_order, bgcolor="#10B981", color="white", height=50),
                order_feedback,
            ],
            spacing=15,
            scroll="auto",
        )
        page.update()

    def show_clients():
        clients = mdb.get_clients()
        main_view.content = ft.Column(
            [
                ft.Text("سجل العملاء", size=28, weight="bold"),
                ft.Column(
                    [
                        ft.Container(
                            content=ft.Row(
                                [
                                    ft.Column(
                                        [
                                            ft.Text(c["name"], weight="bold"),
                                            ft.Text(c.get("type", "Retail"), size=12, color="grey"),
                                        ],
                                        expand=True,
                                    ),
                                    ft.Text(f"{c['balance']:,.2f}", color="#EF4444", weight="bold"),
                                ]
                            ),
                            padding=15,
                            bgcolor="#1f2937",
                            border_radius=15,
                        )
                        for c in clients
                    ],
                    scroll="auto",
                    expand=True,
                )
                if clients
                else ft.Text("لا يوجد عملاء - قم بالمزامنة أولاً", color="grey"),
            ],
            spacing=20,
        )
        page.update()

    def show_settings():
        url_field = ft.TextField(label="عنوان السيرفر", value=mdb.get_setting("server_url", DEFAULT_SERVER), border_radius=10)

        def save_conf(_):
            mdb.set_setting("server_url", url_field.value.strip() or DEFAULT_SERVER)
            sync_feedback.value = "تم حفظ عنوان السيرفر"
            check_online_once()
            page.update()

        def run_sync(_):
            with sync_lock:
                result = SyncEngine.sync_all()
            sync_feedback.value = f"{'✅' if result['success'] else '❌'} {result['message']} | تم رفع: {result['pushed']}"
            page.update()
            if result["success"]:
                show_dashboard()

        main_view.content = ft.Column(
            [
                ft.Text("الإعدادات", size=28, weight="bold"),
                ft.Container(
                    content=ft.Column([url_field, ft.ElevatedButton("✅ حفظ التغييرات", on_click=save_conf)]),
                    padding=20,
                    bgcolor="#1f2937",
                    border_radius=20,
                ),
                ft.ElevatedButton("🔄 مزامنة الآن", height=50, on_click=run_sync),
                ft.Text("النسخة: 2026.6 offline-first", color="grey", size=12),
            ],
            spacing=30,
        )
        page.update()

    def on_nav_click(idx):
        main_view.current_nav_idx = idx
        if idx == 0:
            show_dashboard()
        elif idx == 1:
            show_orders()
        elif idx == 2:
            show_pos()
        elif idx == 3:
            show_clients()
        elif idx == 4:
            show_settings()
        page.update()

    def render_nav():
        idx = main_view.current_nav_idx

        def nav_item(label, i):
            active = i == idx
            return ft.TextButton(
                content=ft.Text(label, color="#3B82F6" if active else "grey", weight="bold"),
                on_click=lambda _, x=i: on_nav_click(x),
            )

        return ft.Container(
            content=ft.Row(
                [
                    nav_item("🏠 الرئيسية", 0),
                    nav_item("📋 الطلبات", 1),
                    nav_item("➕ طلب", 2),
                    nav_item("👥 عملاء", 3),
                    nav_item("⚙️ إعدادات", 4),
                ],
                alignment="spaceAround",
            ),
            bgcolor="#1f2937",
            padding=5,
            height=60,
        )

    def check_online_once():
        try:
            is_up = SyncEngine.test_connection(mdb.get_setting("server_url", DEFAULT_SERVER))
            conn_status.value = "🟢 متصل" if is_up else "🔴 غير متصل"
            conn_status.color = "green" if is_up else "red"
        except Exception:
            conn_status.value = "🔴 غير متصل"
            conn_status.color = "red"

    def background_loop():
        while True:
            try:
                check_online_once()
                if conn_status.value.startswith("🟢"):
                    with sync_lock:
                        if mdb.get_unsynced_count() > 0:
                            SyncEngine.push_pending_orders()
                    SyncEngine.pull_data()
                    refresh_dashboard_feedback()
            except Exception:
                pass
            time.sleep(30)

    show_dashboard()
    page.add(
        ft.Column(
            [
                main_view,
                ft.Divider(height=1, color="transparent"),
                render_nav(),
            ],
            expand=True,
            spacing=0,
        )
    )

    check_online_once()
    threading.Thread(target=background_loop, daemon=True).start()


if __name__ == "__main__":
    ft.app(target=main)
