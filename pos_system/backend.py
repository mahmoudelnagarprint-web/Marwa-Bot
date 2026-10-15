import eel
import sys
import os
import datetime
import traceback

# --- CRASH LOGGING ---
# Redirect outputs to logging file to capture "sudden stops"
log_file = os.path.join(os.getcwd(), "backend_crash.log")

# Handle pythonw.exe where stdout/stderr may be None
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

class Logger(object):
    def __init__(self, stream, filename):
        self.terminal = stream
        self.log = open(filename, "a", encoding='utf-8')
    def write(self, message):
        try:
            if self.terminal:
                self.terminal.write(message)
            self.log.write(message)
            self.log.flush()
        except: pass
    def flush(self):
        try:
            if self.terminal:
                self.terminal.flush()
            self.log.flush()
        except: pass

sys.stdout = Logger(sys.stdout, log_file)
sys.stderr = Logger(sys.stderr, log_file)

print(f"\n{'='*50}")
print(f"Backend Started: {datetime.datetime.now()}")
print(f"{'='*50}\n")
from database import init_db, save_setting, get_setting

# Initialize DB on import
init_db()

class Backend:
    def __init__(self):
        pass

    def save_config(self, sheet_url, drive_link, local_path):
        print(f"Saving Settings: {sheet_url}, {drive_link}, {local_path}")
        try:
            save_setting("google_sheet_url", sheet_url)
            save_setting("drive_folder_link", drive_link)
            save_setting("local_images_path", local_path)
            return True
        except Exception as e:
            print(f"Error saving settings: {e}")
            return False

    def get_current_settings(self):
        return {
            "sheet_url": get_setting("google_sheet_url"),
            "drive_link": get_setting("drive_folder_link"),
            "local_path": get_setting("local_images_path")
        }

# Instantiate Backend
backend_instance = Backend()

# --- Expose Functions to JS ---
@eel.expose
def py_save_settings(sheet, drive, local):
    return backend_instance.save_config(sheet, drive, local)

@eel.expose
def py_get_settings():
    return backend_instance.get_current_settings()

@eel.expose
def py_test_connection(ctype, url):
    import urllib.request
    import re
    try:
        if ctype == 'sheet':
            # Extract Sheet ID using Regex
            id_match = re.search(r'/d/([a-zA-Z0-9-_]+)', url)
            if id_match:
                sheet_id = id_match.group(1)
                # Construct Export URL
                url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
                
                # Check for GID
                gid_match = re.search(r'[?&]gid=([0-9]+)', url)
                if gid_match:
                    url += f"&gid={gid_match.group(1)}"
            else:
                return {'success': False, 'error': "Invalid Google Sheet URL"}

        # Prepare Request with Headers
        req = urllib.request.Request(url, method='GET', headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        response = urllib.request.urlopen(req, timeout=10)
        return {'success': True}
    except Exception as e:
        return {'success': False, 'error': str(e)}

# --- Clients API ---
@eel.expose
def py_get_clients():
    from database import get_all_clients
    return get_all_clients()

@eel.expose
def py_add_client(name, phone, c_type, notes):
    from database import add_new_client
    add_new_client(name, phone, c_type, notes)
    return True

@eel.expose
def py_update_client(client_id, name, phone, c_type, notes):
    from database import update_client_details
    return update_client_details(client_id, name, phone, c_type, notes)

@eel.expose
def py_add_transaction(client_id, amount, t_type, notes, material_cost_recovery=0.0, net_profit_portion=0.0):
    from database import update_client_transaction
    update_client_transaction(client_id, float(amount), t_type, notes, float(material_cost_recovery), float(net_profit_portion))
    return True

    return True

@eel.expose
def py_get_kanban_orders():
    from database import get_kanban_orders
    return get_kanban_orders()

@eel.expose
def py_update_order_status(order_id, status, payment=0, method=None):
    from database import update_order_status
    return update_order_status(order_id, status, payment, method)

@eel.expose
def py_update_batch_order_status(order_ids, status, payment=0, method=None):
    from database import update_batch_order_status
    return update_batch_order_status(order_ids, status, payment, method)

@eel.expose
def py_get_order_images(order_id):
    from database import get_order_images
    return get_order_images(order_id)

@eel.expose
def py_get_last_payments(client_id):
    from database import get_last_client_payments
    return get_last_client_payments(client_id)

@eel.expose
def py_get_statement(client_id):
    from database import get_client_statement_data
    return get_client_statement_data(client_id)

@eel.expose
def py_get_products(category=None):
    from database import get_all_products
    return get_all_products(category)

@eel.expose
def py_update_product(p_id, name, cat, price_w, price_r, sort_order):
    from database import update_product_details
    update_product_details(p_id, name, cat, price_w, price_r, sort_order)
    return True

@eel.expose
def py_delete_product(p_id):
    from database import delete_product
    delete_product(p_id)
    return True

@eel.expose
def py_update_stock(p_id, qty):
    from database import update_product_stock_db
    update_product_stock_db(p_id, qty)
    update_product_stock_db(p_id, qty)
    return True

# --- Category Management ---
@eel.expose
def py_get_all_categories():
    from database import get_all_categories_db
    return get_all_categories_db()

@eel.expose
def py_add_category(name):
    from database import add_category_db
    return add_category_db(name)

@eel.expose
def py_update_category(cat_id, new_name):
    from database import update_category_db
    return update_category_db(cat_id, new_name)

@eel.expose
def py_delete_category(cat_id):
    from database import delete_category_db
    return delete_category_db(cat_id)

@eel.expose
def py_delete_client(client_id):
    from database import delete_client
    return delete_client(client_id)

@eel.expose
def py_recalculate_balance(client_id):
    from database import recalculate_client_balance
    return recalculate_client_balance(client_id)

# --- Staff Module API (Tasks, Chat, Calls, Production) ---

@eel.expose
def py_get_tasks(staff_name=None):
    from database import get_tasks
    return get_tasks(staff_name)

@eel.expose
def py_add_task(title, desc, assigned_to, product_id=None, image_path=None):
    from database import add_task
    return add_task(title, desc, assigned_to, product_id, image_path)

@eel.expose
def py_update_task_status(task_id, status):
    from database import update_task_status
    return update_task_status(task_id, status)

@eel.expose
def py_get_chat_messages(limit=50):
    from database import get_chat_messages
    return get_chat_messages(limit)

@eel.expose
def py_add_chat_message(sender, message, image_path=None):
    from database import add_chat_message
    return add_chat_message(sender, message, image_path)

@eel.expose
def py_get_active_staff_calls(target_user=None):
    from database import get_active_staff_calls
    return get_active_staff_calls(target_user)

@eel.expose
def py_add_staff_call(caller, target, call_type='summon'):
    from database import add_staff_call
    return add_staff_call(caller, target, call_type)

@eel.expose
def py_resolve_staff_call(call_id):
    from database import resolve_staff_call
    return resolve_staff_call(call_id)

@eel.expose
def py_get_production_summary():
    from database import get_production_summary
    return get_production_summary()

@eel.expose
def py_decrement_production_item(product_id, qty=1):
    from database import decrement_production_item
    return decrement_production_item(product_id, qty)

@eel.expose
def py_adjust_balance(client_id, new_amount):
    from database import adjust_balance
    return adjust_balance(client_id, new_amount)

@eel.expose
def py_delete_order(order_id):
    from database import delete_order
    return delete_order(order_id)

@eel.expose
def py_update_order_total(order_id, new_total):
    from database import update_order_total_db
    return update_order_total_db(order_id, new_total)

@eel.expose
def py_delete_transaction(txn_id):
    from database import delete_transaction
    return delete_transaction(txn_id)

@eel.expose
def py_clear_old_debt(client_id):
    """Clear old/delivered debt by setting balance = prep + ready (active orders only)"""
    from database import clear_old_debt
    return clear_old_debt(client_id)
    
@eel.expose
def py_update_statement_item(order_ids, product_name, new_qty, new_price):
    from database import update_order_item_from_statement
    return update_order_item_from_statement(order_ids, product_name, new_qty, new_price)

# --- Phase 4: POS API ---
@eel.expose
def py_save_order(client_id, total, discount, net, paid, remaining, items, method, notes=""):
    from database import save_order_transaction
    return save_order_transaction(client_id, total, discount, net, paid, remaining, items, method, notes)

@eel.expose
def py_add_quick_product(name, cat, price_r, price_w):
    from database import add_quick_product
    return add_quick_product(name, cat, price_r, price_w)

@eel.expose
def py_sync_orders():
    # Phase 7: Use New Robust Engine
    try:
        from google_api_sync import OrderSyncEngine
        engine = OrderSyncEngine()
        return engine.run_sync()
    except Exception as e:
        return {'success': False, 'error': f"Engine Error: {str(e)}"}

@eel.expose
def py_get_telegram_sync_status():
    try:
        import sys
        from pathlib import Path

        telegram_dir = Path(__file__).resolve().parent / "telegram_bot"
        if str(telegram_dir) not in sys.path:
            sys.path.insert(0, str(telegram_dir))

        from config import load_settings
        from sheets_queue import TelegramSheetsQueue

        settings = load_settings()
        queue = TelegramSheetsQueue(settings)
        return {"success": True, "data": queue.get_telegram_sync_status_summary()}
    except Exception as e:
        return {"success": False, "error": str(e)}

@eel.expose
def py_trigger_telegram_import_now():
    try:
        import sys
        from pathlib import Path

        telegram_dir = Path(__file__).resolve().parent / "telegram_bot"
        if str(telegram_dir) not in sys.path:
            sys.path.insert(0, str(telegram_dir))

        from config import load_settings

        settings = load_settings()
        settings.telegram_import_flag_path.write_text("import-now\n", encoding="utf-8")
        return {"success": True, "flag_path": str(settings.telegram_import_flag_path)}
    except Exception as e:
        return {"success": False, "error": str(e)}

@eel.expose
def py_retry_images():
    from sheets_sync import retry_failed_images
    return retry_failed_images()

@eel.expose
def py_link_order_folder(order_id, path):
    """
    Smart Link: Ingests the folder into the System Hierarchy (FileOpsEngine)
    Then updates the DB with the new internal path.
    """
    from database import get_db_connection, update_order_image_path, get_setting
    from file_ops_engine import FileOpsEngine
    
    try:
        root_path = get_setting("local_images_path")
        if not root_path:
            return "Error: System Image Path not set in Settings."

        engine = FileOpsEngine(root_path)
        
        # Ingest (Copy & Organize)
        # We pass get_db_connection as a callable factory
        success, result_path = engine.ingest_external_folder(order_id, path, get_db_connection)
        
        if success:
            # Save the NEW internal path
            return update_order_image_path(order_id, result_path)
        else:
            return f"Ingestion Failed: {result_path}"
            
    except Exception as e:
        return f"Error: {str(e)}"

@eel.expose
def py_create_order_folder(order_id):
    """
    Auto-Creates the standard folder for an order based on FileOpsEngine rules.
    Path: Root / Type / Client / Product_Note_ID
    """
    from database import get_db_connection, update_order_image_path, get_setting
    from file_ops_engine import FileOpsEngine
    import os
    
    try:
        conn = get_db_connection()
        order = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
        if not order: return {"success": False, "error": "Order not found"}
        
        client = conn.execute("SELECT * FROM clients WHERE id=?", (order['client_id'],)).fetchone()
        item = conn.execute("SELECT product_name FROM order_items WHERE order_id=? LIMIT 1", (order_id,)).fetchone()
        conn.close()
        
        root_path = get_setting("local_images_path")
        if not root_path: return {"success": False, "error": "Settings: Image Path not set"}
        
        engine = FileOpsEngine(root_path)
        
        # Generate Standard Path
        target_path = engine.get_creation_path(
            client['type'] if client else 'Retail',
            client['name'] if client else 'Unknown',
            item['product_name'] if item else 'Product',
            order['notes'],
            order_id
        )
        
        # Create
        if not os.path.exists(target_path):
            os.makedirs(target_path)
            
        # Update DB
        update_order_image_path(order_id, target_path)
        
        # Open it immediately
        engine._retry_operation(lambda: os.system(f'explorer "{target_path}"'))
        
        return {"success": True, "path": target_path}
        
    except Exception as e:
        return {"success": False, "error": str(e)}

@eel.expose
def py_open_image_folder(path):
    """Opens the folder containing order images in Windows Explorer"""
    import os
    import subprocess
    try:
        if not path:
            return False
        # If path is a file, get its directory
        if os.path.isfile(path):
            folder = os.path.dirname(path)
        else:
            folder = path
        # If it's a comma-separated list of paths, get the first one's directory
        if ',' in folder:
            folder = os.path.dirname(folder.split(',')[0].strip())
        if os.path.exists(folder):
            subprocess.Popen(f'explorer "{folder}"', shell=True)
            return True
        return False
    except Exception as e:
        print(f"Error opening folder: {e}")
        return False

@eel.expose
def py_get_folder_images(path_str):
    """
    Smart resolver: 
    - If path is a folder, returns all images inside it.
    - If path is comma-separated string, splits and returns list.
    - Returns list of absolute file paths.
    """
    import os
    
    if not path_str or path_str == 'null':
        return []

    valid_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp')
    results = []

    # Case 1: Is a Directory?
    if os.path.isdir(path_str):
        try:
            for root, dirs, files in os.walk(path_str):
                for file in files:
                    if file.lower().endswith(valid_extensions):
                        results.append(os.path.join(root, file))
        except Exception as e:
            print(f"Error listing folder: {e}")
            
    # Case 2: Comma separated list (Legacy or drag-drop link)
    elif ',' in path_str:
        paths = path_str.split(',')
        for p in paths:
            p = p.strip()
            if p and os.path.exists(p) and os.path.isfile(p):
                results.append(p)
                
    # Case 3: Single File
    elif os.path.isfile(path_str):
        results.append(path_str)
        
    return results

@eel.expose
def py_get_image_base64(path):
    import base64
    import os
    if not os.path.exists(path):
        return None
    try:
        with open(path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
            return encoded_string
    except Exception as e:
        print(f"Error reading image {path}: {e}")
        return None

@eel.expose
def py_copy_image_high_quality(path):
    """High-Fidelity Clipboard Copy (CF_DIB) for Photoshop Compatibility."""
    import win32clipboard
    from PIL import Image
    import io
    import os
    
    try:
        abs_path = os.path.abspath(path)
        if not os.path.exists(abs_path):
            return {"success": False, "message": "ملف الصورة غير موجود"}

        # 1. Load Original Image
        image = Image.open(abs_path)
        
        # 2. Convert to DIB (BMP format minus header)
        output = io.BytesIO()
        image.convert("RGB").save(output, "BMP")
        data = output.getvalue()[14:]  # Remove 14-byte BMP header
        output.close()
        
        # 3. Inject to Clipboard
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
        win32clipboard.CloseClipboard()
        
        # Get Info/Size for toast
        w, h = image.size
        size_mb = os.path.getsize(abs_path) / (1024 * 1024)
        
        return {"success": True, "message": f"تم النسخ بجودة أصلية ({w}x{h} | {size_mb:.2f}MB) ✅"}
            
    except Exception as e:
        print(f"Clipboard Error: {e}")
        return {"success": False, "message": f"فشل النسخ: {e}"}
@eel.expose
def py_get_dashboard_stats():
    from database import get_dashboard_stats
    return get_dashboard_stats()

@eel.expose
def py_get_customers_stats():
    from database import get_customers_stats
    return get_customers_stats()

@eel.expose
def py_get_orders_stats():
    from database import get_orders_stats
    return get_orders_stats()

@eel.expose
def py_get_products_stats():
    from database import get_products_stats
    return get_products_stats()



# --- Phase 8: Purchase Invoices ---
@eel.expose
def py_save_purchase_invoice(data):
    from database import save_purchase_invoice
    return save_purchase_invoice(data)

@eel.expose
def py_toggle_purchase_status(invoice_id, new_status):
    from database import toggle_purchase_status
    return toggle_purchase_status(invoice_id, new_status)

@eel.expose
def py_get_all_purchases():
    from database import get_all_purchases
    return get_all_purchases()

@eel.expose
def py_get_purchase_details(invoice_id):
    from database import get_purchase_details
    return get_purchase_details(invoice_id)

@eel.expose
def py_delete_purchase(invoice_id):
    from database import delete_purchase
    return delete_purchase(invoice_id)

@eel.expose
def py_get_order_details(order_id):
    try:
        from database import get_order_details
        details = get_order_details(order_id)
        if details:
            return {'success': True, 'data': details}
        return {'success': False, 'message': 'Order not found'}
    except Exception as e:
        return {'success': False, 'message': str(e)}

@eel.expose
def py_update_order_full(order_id, data):
    from database import update_order_full
    return update_order_full(order_id, data)

# --- Staff Management (New) ---

@eel.expose
def py_get_all_staff(include_inactive=False):
    from database import get_all_staff
    return get_all_staff(include_inactive)

@eel.expose
def py_save_staff(data):
    from database import save_staff
    return save_staff(data)

@eel.expose
def py_delete_staff(staff_id):
    from database import delete_staff
    return delete_staff(staff_id)

@eel.expose
def py_log_attendance(staff_id, action):
    from database import log_attendance_action
    return log_attendance_action(staff_id, action)

@eel.expose
def py_get_attendance_log(staff_id=None, date_from=None, date_to=None):
    from database import get_attendance_log
    return get_attendance_log(staff_id, date_from, date_to)

@eel.expose
def py_get_payroll_draft(staff_id):
    from database import get_payroll_draft
    return get_payroll_draft(staff_id)

@eel.expose
def py_add_payroll_txn(staff_id, t_type, amount, reason):
    from database import add_payroll_transaction
    return add_payroll_transaction(staff_id, t_type, amount, reason)

@eel.expose
def py_confirm_payout(staff_id):
    from database import confirm_payout
    return confirm_payout(staff_id)

@eel.expose
def py_get_requests():
    from database import get_staff_requests
    return get_staff_requests()

@eel.expose
def py_update_request_status(req_id, status):
    from database import update_request_status
    return update_request_status(req_id, status)

@eel.expose
def py_send_chat(sender_id, recipient_id, message, image_path=None):
    from database import send_chat_message
    return send_chat_message(sender_id, recipient_id, message, image_path)



@eel.expose
def py_get_security_token():
    from database import generate_qr_token
    return generate_qr_token()

# --- Mobile API ---

@eel.expose
def py_mobile_login(pin):
    """Authenticate employee by PIN and return their data. Auto-logs attendance on first daily login."""
    from database import get_db_connection, log_attendance_action
    import hashlib
    from datetime import datetime
    
    if not pin:
        return {"success": False, "error": "PIN required"}
    
    pin_hash = hashlib.sha256(pin.encode()).hexdigest()
    
    conn = get_db_connection()
    staff = conn.execute(
        "SELECT id, name, role, photo_path, base_salary, commission_rate FROM staff WHERE pin_hash = ? AND is_active = 1",
        (pin_hash,)
    ).fetchone()
    
    if staff:
        staff_id = staff['id']
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Check if already logged in today
        existing = conn.execute(
            "SELECT id FROM attendance WHERE staff_id = ? AND date = ?",
            (staff_id, today)
        ).fetchone()
        
        conn.close()
        
        # Auto log attendance if first login today
        if not existing:
            log_attendance_action(staff_id, 'check_in')
        
        return {
            "success": True,
            "staff": dict(staff),
            "attendance_logged": not existing
        }
    
    conn.close()
    return {"success": False, "error": "رمز خاطئ"}

@eel.expose
def py_get_orders_mobile():
    """Get orders for mobile view (grouped by status)"""
    from database import get_db_connection
    
    conn = get_db_connection()
    orders = conn.execute("""
        SELECT o.*, c.name as client_name, c.phone as client_phone
        FROM orders o
        LEFT JOIN clients c ON o.client_id = c.id
        ORDER BY o.date DESC
    """).fetchall()
    conn.close()
    
    result = {
        "prep": [],
        "ready": [],
        "done": []
    }
    
    for o in orders:
        order_dict = dict(o)
        status = order_dict.get('status', '')
        
        if 'تحت التجهيز' in status or 'Under Preparation' in status or 'Prep' in status:
            result["prep"].append(order_dict)
        elif 'جاهز' in status or 'Ready' in status:
            result["ready"].append(order_dict)
        elif 'تم التسليم' in status or 'Delivered' in status or 'Done' in status:
            result["done"].append(order_dict)
        else:
            result["prep"].append(order_dict)  # Default to prep
    
    return result

@eel.expose
def py_get_products_mobile():
    """Get products WITHOUT cost price for employee view"""
    from database import get_db_connection, get_all_products
    
    try:
        conn = get_db_connection()
        products = conn.execute("""
            SELECT id, name, category, retail_price, wholesale_price, stock, image_path, sort_order
            FROM products
            ORDER BY sort_order ASC, name ASC
        """).fetchall()
        conn.close()
        
        if products:
            return [dict(p) for p in products]
        
        # Fallback to get_all_products if direct query returns nothing
        all_prods = get_all_products()
        # Remove cost_price from each product
        for p in all_prods:
            if 'cost_price' in p:
                del p['cost_price']
        return all_prods
    except Exception as e:
        print(f"Error loading products for mobile: {e}")
        # Fallback
        try:
            from database import get_all_products
            all_prods = get_all_products()
            for p in all_prods:
                if 'cost_price' in p:
                    del p['cost_price']
            return all_prods
        except:
            return []

@eel.expose
def py_get_employee_stats(staff_id):
    """Get attendance and performance stats for employee"""
    from database import get_db_connection
    from datetime import datetime, timedelta
    
    conn = get_db_connection()
    
    # This month's attendance
    month_start = datetime.now().replace(day=1).strftime('%Y-%m-%d')
    attendance = conn.execute("""
        SELECT COUNT(*) as days_present
        FROM attendance
        WHERE staff_id = ? AND date >= ? AND status IN ('Present', 'Late')
    """, (staff_id, month_start)).fetchone()
    
    # Late count
    late = conn.execute("""
        SELECT COUNT(*) as late_count
        FROM attendance
        WHERE staff_id = ? AND date >= ? AND status = 'Late'
    """, (staff_id, month_start)).fetchone()
    
    conn.close()
    
    return {
        "days_present": attendance['days_present'] if attendance else 0,
        "late_count": late['late_count'] if late else 0,
        "orders_count": 0,  # TODO: Link orders to staff
        "commission_earned": 0  # TODO: Calculate from sales
    }

@eel.expose
def py_get_network_info():
    """Get local network IP for mobile connection"""
    import socket
    
    try:
        # Get local IP by connecting to external address (doesn't actually connect)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        
        # Get port for mobile (Flask server is on 5000)
        port = 7777
        
        return {
            "success": True,
            "ip": local_ip,
            "port": port,
            "url": f"http://{local_ip}:{port}/mobile.html"
        }
    except Exception as e:
        # Fallback to localhost
        return {
            "success": False,
            "ip": "127.0.0.1",
            "port": 7777,
            "url": "http://127.0.0.1:7777/mobile.html",
            "error": str(e)
        }

# --- Main Entry Point ---
if __name__ == '__main__':
    try:
        # Start Flask App in a separate thread for Mobile API
        import threading
        from app import app as flask_app
        
        def run_flask():
            # Run Flask without reloader to avoid main thread issues
            print(f"Starting Mobile Flask API on port 7777...")
            flask_app.run(host='0.0.0.0', port=7777, debug=False, use_reloader=False)
            
        flask_thread = threading.Thread(target=run_flask, daemon=True)
        flask_thread.start()

        # Initialize Eel
        eel.init('web')
        
        # Start Sidebar (Hidden - no console window)
        import subprocess
        try:
            # Use pythonw.exe for windowless execution
            pythonw_path = os.path.join(os.path.dirname(sys.executable), 'pythonw.exe')
            sidebar_python = pythonw_path if os.path.exists(pythonw_path) else sys.executable
            
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = 0  # SW_HIDE
            
            subprocess.Popen([sidebar_python, 'desktop_sidebar.py'], 
                             creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0,
                             startupinfo=si if sys.platform == 'win32' else None)
        except Exception as e:
            print(f"Sidebar Launch Error: {e}")

        # Start App in Independent Window (Chrome App Mode)
        # mode='chrome' forces an app window (no address bar/tabs)
        print("Starting Elnagar POS in Independent Window...")
        anti_sleep_args = [
            '--disable-backgrounding-occluded-windows', 
            '--disable-renderer-backgrounding', 
            '--disable-background-timer-throttling'
        ]
        try:
            eel.start('index.html', mode='chrome', size=(1300, 900), port=8888, cmdline_args=anti_sleep_args)
        except EnvironmentError:
             # If Chrome not found, try Edge
            print("Chrome not found, trying Edge...")
            try:
                eel.start('index.html', mode='edge', size=(1300, 900), port=8888, cmdline_args=anti_sleep_args)
            except Exception as edge_err:
                print(f"Edge launch failed or not supported ({edge_err}), falling back to default...")
                eel.start('index.html', mode='default', port=8888)
        
    except Exception as e:
        print(f"Startup Error: {e}")
        traceback.print_exc()
        # Fallback
        try:
           eel.start('index.html', mode='default', port=8888)
        except:
           pass
