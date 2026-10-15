from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import database as db
import os
import datetime
import re
from werkzeug.utils import secure_filename
from server_extensions import sync_bp
from laser_engine import laser_engine

# Clipboard support
import win32clipboard
from PIL import Image
import io
import time

# Flask app with static folder support for mobile access
app = Flask(__name__, static_folder='web', static_url_path='')
app.register_blueprint(sync_bp)
# Allow all origins for extension
CORS(app, resources={r"/*": {"origins": "*"}})

@app.errorhandler(404)
def not_found(e):
    return jsonify({'success': False, 'message': '404 Not Found (API Endpoint Missing)'}), 404

@app.errorhandler(500)
def internal_error(e):
    return jsonify({'success': False, 'message': f'500 Server Error: {str(e)}'}), 500

# Helper to ensure directories exist
def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)

def sanitize_name(name):
    # Sanitize for Windows paths, keeping Arabic characters
    # Remove invalid chars: < > : " / \ | ? *
    return re.sub(r'[<>:"/\\|?*]', '_', str(name)).strip()

def get_storage_root():
    # Try to get from DB settings
    path = db.get_setting('local_images_path') # Correct Key
    if not path or not os.path.exists(path):
        # Fallback to current dir / pos_images
        return os.path.join(os.getcwd(), 'pos_images')
    return path



# --- Endpoints ---

@app.route('/api/get_client_details', methods=['POST'])
def get_client_details():
    try:
        data = request.json
        name = data.get('name')
        if not name:
            return jsonify({'success': False, 'message': 'Name required'}), 400

        conn = db.get_db_connection()
        # Search by exact name or partial? User wants verification. Let's do Exact first, then phone.
        # Actually sidepanel sends the name found in WhatsApp.
        
        client = conn.execute("SELECT * FROM clients WHERE name = ?", (name,)).fetchone()
        conn.close()

        if client:
            return jsonify({
                'success': True,
                'found': True,
                'client': {
                    'id': client['id'],
                    'name': client['name'],
                    'phone': client['phone'],
                    'type': client['type'], # Wholesale / Retail
                    'notes': client['notes']
                }
            })
        else:
            return jsonify({'success': True, 'found': False})

    except Exception as e:
        print(f"Error in get_client_details: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/get_full_data', methods=['GET'])
def get_full_data():
    """Returns JSON {customers: [], products: [], orders: []}."""
    try:
        # Customers
        clients = db.get_all_clients()
        customers_data = [{
            'id': c['id'],
            'name': c['name'],
            'phone': c['phone'], # NEW
            'type': c['type'], # Retail/Wholesale
            'total_debt': c['balance']
        } for c in clients]

        # Products
        products = db.get_all_products()
        products_data = [{
            'id': p['id'],
            'name': p['name'],
            'price': p['price_retail'], 
            'price_wholesale': p['price_wholesale'],
            'stock': p['stock_qty'],
            'category': p['category']
        } for p in products]

        # Orders (Last 50)
        conn = db.get_db_connection()
        orders_rows = conn.execute("""
            SELECT o.id, o.date, c.name as client_name, o.status, o.total_amount, o.notes
            FROM orders o
            LEFT JOIN clients c ON o.client_id = c.id
            ORDER BY o.date DESC LIMIT 50
        """).fetchall()
        conn.close()

        orders_data = [{
            'id': row['id'],
            'date': row['date'],
            'client': row['client_name'] if row['client_name'] else "عميل غير معروف",
            'status': row['status'],
            'total': row['total_amount'],
            'notes': row['notes'] if row['notes'] else ""
        } for row in orders_rows]

        return jsonify({
            'customers': customers_data,
            'products': products_data,
            'orders': orders_data
        })

    except Exception as e:
        print(f"Error in get_full_data: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/products', methods=['GET'])
def get_products_api():
    try:
        conn = db.get_db_connection()
        products = conn.execute("SELECT id, name, price_retail, price_wholesale, stock_qty, category FROM products ORDER BY name ASC").fetchall()
        conn.close()
        
        products_list = [{
            'id': row['id'],
            'name': row['name'],
            'price_retail': row['price_retail'],
            'price_wholesale': row['price_wholesale'],
            'stock': row['stock_qty'],
            'category': row['category']
        } for row in products]
        
        return jsonify({'success': True, 'products': products_list})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/get_categories', methods=['GET'])
def get_categories_api_ext():
    try:
        cats = db.get_all_categories_db()
        return jsonify({'success': True, 'categories': cats})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/clients', methods=['GET'])
def get_clients_api():
    try:
        clients = db.get_all_clients()
        customers_data = [{
            'id': c['id'],
            'name': c['name'],
            'phone': c['phone'],
            'type': c['type'], 
            'total_debt': c['balance']
        } for c in clients]
        return jsonify({'success': True, 'customers': customers_data})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/orders', methods=['GET'])
def get_orders_api():
    try:
        conn = db.get_db_connection()
        # Same logic as get_full_data but for orders only
        orders_rows = conn.execute("""
            SELECT o.id, o.date, c.name as client_name, o.status, o.total_amount, o.notes
            FROM orders o
            LEFT JOIN clients c ON o.client_id = c.id
            ORDER BY o.date DESC LIMIT 50
        """).fetchall()
        conn.close()

        orders_data = [{
            'id': row['id'],
            'date': row['date'],
            'client': row['client_name'] if row['client_name'] else "عميل غير معروف",
            'status': row['status'],
            'total': row['total_amount'],
            'notes': row['notes'] if row['notes'] else ""
        } for row in orders_rows]

        return jsonify({'success': True, 'orders': orders_data})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/whatsapp_sync', methods=['POST'])
def whatsapp_sync():
    """
    Arabic Logic:
    1. Check/Create Client.
    2. Parse Items (Multi-Product Support).
    3. Create Order -> Deduct Stock -> Update Debt.
    4. Save Images PER PRODUCT in subfolders.
    """
    try:
        # 1. Parse Data
        client_name = request.form.get('client_name')
        client_phone = request.form.get('client_phone', '') 
        client_type = request.form.get('client_type', 'Retail')
        notes = request.form.get('notes', '')
        
        # Multi-Product Logic
        items_json = request.form.get('items') # JSON String
        items_data = []
        
        if items_json:
            import json
            try:
                items_data = json.loads(items_json)
            except:
                return jsonify({'success': False, 'message': 'Invalid items format'}), 400
        else:
            # Fallback for single item (Legacy or Quick Add)
            p_id = request.form.get('product_id')
            p_qty = float(request.form.get('qty', 1))
            p_price = float(request.form.get('price', 0))
            if p_id:
                items_data.append({'id': p_id, 'qty': p_qty, 'price': p_price})

        if not client_name:
            return jsonify({'success': False, 'message': 'اسم العميل مطلوب'}), 400
            
        if not items_data:
             return jsonify({'success': False, 'message': 'لا توجد منتجات'}), 400

        # 2. Check/Create Client
        conn = db.get_db_connection()
        client = conn.execute("SELECT * FROM clients WHERE name = ?", (client_name,)).fetchone()
        
        if not client and client_phone:
             client = conn.execute("SELECT * FROM clients WHERE phone = ?", (client_phone,)).fetchone()
             
        conn.close()

        client_id = None
        if client:
            client_id = client['id']
        else:
            client_id = db.add_new_client(client_name, client_phone, client_type, f"إضافة تلقائية من الامتداد. {notes}")
        
        # 3. Prepare Items & Calculate Total
        final_items = []
        total_order = 0
        
        conn = db.get_db_connection()
        for idx, item in enumerate(items_data):
            pid = item.get('id')
            qty = float(item.get('qty', 1))
            price = float(item.get('price', 0))
            item_index = item.get('item_index', idx)  # Get index for image matching
            
            # Fetch Name and Price if not provided or 0 (Safety)
            prod_db = conn.execute("SELECT name, price_retail FROM products WHERE id=?", (pid,)).fetchone()
            p_name = prod_db['name'] if prod_db else "Unknown Product"
            
            # --- UPDATE PRICES IF PROVIDED ---
            # If extension sends new prices, update them in DB
            new_price_r = float(item.get('price', 0)) # Retail from ext
            new_price_w = float(item.get('price_wholesale', 0)) # Wholesale from ext (might be 0 if not set)
            
            if pid:
                # Only update if > 0 to avoid wiping data with zeros
                # If valid retail provided
                r_update = new_price_r if new_price_r > 0 else None
                # If valid wholesale provided
                w_update = new_price_w if new_price_w > 0 else None
                
                if r_update or w_update:
                    db.update_product_prices(pid, r_update, w_update)

            # ZERO PRICE FIX: If price is 0, use current retail price (Logic for ORDER TOTAL)
            # This logic uses the 'price' for the calculation. 
            # If user sent 0, we use DB price. If user sent a price (and we updated DB above), we use that price.
            calc_price = price
            if calc_price == 0 and prod_db:
                calc_price = prod_db['price_retail']
            
            line_total = calc_price * qty
            total_order += line_total
            
            final_items.append({
                'id': pid,
                'name': p_name,
                'qty': qty,
                'price': calc_price,
                'total': line_total,
                'item_index': item_index  # Keep for image matching
            })
        conn.close()

        # 4. Create Order
        result = db.save_order_transaction(
            client_id=client_id,
            total_amount=total_order,
            discount=0,
            net_total=total_order,
            paid_amount=0,
            remaining=total_order,
            items=final_items,
            payment_method="Credit",
            notes=notes
        )
        
        if not result.get('success'):
             return jsonify({'success': False, 'message': 'فشل إنشاء الطلب: ' + str(result.get('error', 'Unknown'))}), 500
             
        order_id = result['order_id']
        
        # 5. Handle Images - CREATE PRODUCT SUBFOLDERS
        from file_ops_engine import FileOpsEngine
        
        # Get root path from settings
        root_path = get_storage_root()
        
        # Create variable to track if folder was created properly
        folder_created = False
        order_folder = None
        
        # Get first product name for main folder naming
        first_product_name = final_items[0]['name'] if final_items else "Product"
        
        # Try to create main order folder
        try:
            engine = FileOpsEngine(root_path)
            
            # Generate the correct path based on client type
            order_folder = engine.get_creation_path(
                client_type,  # 'Wholesale' or 'Retail'
                client_name,
                first_product_name,
                notes,
                order_id
            )
            
            # Actually create the folder
            os.makedirs(order_folder, exist_ok=True)
            folder_created = os.path.exists(order_folder)
            
            # Update database with the folder path
            if folder_created:
                conn = db.get_db_connection()
                conn.execute("UPDATE orders SET local_image_path = ? WHERE id = ?", (order_folder, order_id))
                conn.commit()
                conn.close()
                
        except Exception as folder_err:
            print(f"Folder creation error: {folder_err}")
            # Fallback: Try simple folder in root
            try:
                order_folder = os.path.join(root_path, f"Order_{order_id}")
                os.makedirs(order_folder, exist_ok=True)
                folder_created = os.path.exists(order_folder)
                if folder_created:
                    conn = db.get_db_connection()
                    conn.execute("UPDATE orders SET local_image_path = ? WHERE id = ?", (order_folder, order_id))
                    conn.commit()
                    conn.close()
            except:
                pass
        
        # NOW SAVE IMAGES IN PRODUCT SUBFOLDERS
        saved_files = []
        if folder_created and order_folder:
            
            # Process images for each product (images_0, images_1, etc.)
            for item in final_items:
                item_idx = item.get('item_index', 0)
                product_name = sanitize_name(item.get('name', 'Product'))
                
                # Check if there are images for this item
                images_key = f'images_{item_idx}'
                if images_key in request.files:
                    files = request.files.getlist(images_key)
                    
                    if files and len(files) > 0:
                        # Create product subfolder: "1_فانوس_15_سم"
                        product_folder_name = f"{item_idx + 1}_{product_name}"
                        product_folder = os.path.join(order_folder, product_folder_name)
                        os.makedirs(product_folder, exist_ok=True)
                        
                        # Save images in product folder
                        for img_idx, file in enumerate(files):
                            if file.filename:
                                ts = datetime.datetime.now().strftime("%H%M%S")
                                fname = sanitize_name(file.filename)
                                final_name = f"{ts}_{img_idx}_{fname}"
                                file_path = os.path.join(product_folder, final_name)
                                try:
                                    file.save(file_path)
                                    saved_files.append(file_path)
                                except Exception as save_err:
                                    print(f"Image save error: {save_err}")
            
            # Also handle global images (backward compatibility) - save in main order folder
            if 'images_global' in request.files:
                global_files = request.files.getlist('images_global')
                for idx, file in enumerate(global_files):
                    if file.filename:
                        ts = datetime.datetime.now().strftime("%H%M%S")
                        fname = sanitize_name(file.filename)
                        final_name = f"{ts}_global_{idx}_{fname}"
                        file_path = os.path.join(order_folder, final_name)
                        try:
                            file.save(file_path)
                            saved_files.append(file_path)
                        except Exception as save_err:
                            print(f"Global image save error: {save_err}")
                
        return jsonify({'success': True, 'message': f'تم إنشاء الطلب #{order_id} بنجاح', 'order_id': order_id, 'images_saved': len(saved_files)})

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/quick_add', methods=['POST'])
def quick_add():
    """Add new Client or Product"""
    data = request.json
    action_type = data.get('type') 
    
    try:
        if action_type == 'client':
            name = data.get('name')
            phone = data.get('phone', '')
            c_type = data.get('client_type', 'Retail')
            if not name: return jsonify({'success': False, 'message': 'الاسم مطلوب'}), 400
            
            new_id = db.add_new_client(name, phone, c_type, "إضافة سريعة")
            return jsonify({'success': True, 'id': new_id, 'message': 'تم إضافة العميل'})
            
        elif action_type == 'product':
            name = data.get('name')
            price_r = float(data.get('price_retail', 0) or 0)
            price_w = float(data.get('price_wholesale', 0) or 0)
            category = data.get('category', 'جديد') # Default to New
            if not name: return jsonify({'success': False, 'message': 'الاسم مطلوب'}), 400
            
            new_id = db.add_quick_product(name, category, price_r, price_w)
            return jsonify({'success': True, 'id': new_id, 'message': 'تم إضافة المنتج'})
            
        elif action_type == 'category':
            name = data.get('name')
            if not name: return jsonify({'success': False, 'message': 'الاسم مطلوب'}), 400
            
            res = db.add_category_db(name)
            if res.get('success'):
                return jsonify({'success': True, 'message': 'تم إضافة التصنيف'})
            else:
                return jsonify({'success': False, 'message': res.get('error')}), 500
            
        else:
            return jsonify({'success': False, 'message': 'نوع الطلب غير صحيح'}), 400
            
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/pay_debt', methods=['POST'])
def pay_debt():
    data = request.json
    client_id = data.get('client_id')
    amount = float(data.get('amount', 0))
    material_cost_recovery = float(data.get('material_cost_recovery', 0.0))
    net_profit_portion = float(data.get('net_profit_portion', amount))
    
    if not client_id or amount <= 0:
        return jsonify({'success': False, 'message': 'بيانات غير صحيحة'}), 400
        
    try:
        db.update_client_transaction(client_id, amount, 'payment', 'دفع عن طريق الامتداد', material_cost_recovery, net_profit_portion)
        return jsonify({'success': True, 'message': 'تم تسجيل الدفع'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/update_client', methods=['POST'])
def update_client_api():
    try:
        data = request.json
        client_id = data.get('client_id')
        name = data.get('name')
        phone = data.get('phone', '')
        c_type = data.get('client_type', 'Retail')
        notes = data.get('notes', '')
        
        if not client_id or not name:
            return jsonify({'success': False, 'message': 'Client ID and Name are required'}), 400
            
        success = db.update_client_details(int(client_id), name, phone, c_type, notes)
        return jsonify({'success': success, 'message': 'Client updated successfully' if success else 'Failed to update client'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/delete_client', methods=['POST'])
def delete_client():
    data = request.json
    c_id = data.get('client_id')
    try:
        if db.delete_client(c_id):
            return jsonify({'success': True, 'message': 'تم حذف العميل وطلباته'})
        return jsonify({'success': False, 'message': 'فشل الحذف'}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/delete_order', methods=['POST'])
def delete_order():
    data = request.json
    o_id = data.get('order_id')
    try:
        if db.delete_order(o_id):
            return jsonify({'success': True, 'message': 'تم حذف الطلب'})
        return jsonify({'success': False, 'message': 'فشل الحذف'}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/get_order_details', methods=['POST'])
def get_order_details():
    try:
        data = request.json
        if not data or 'order_id' not in data:
            return jsonify({'success': False, 'message': 'Order ID required'}), 400
        
        details = db.get_order_details(data['order_id'])
        if details:
            return jsonify({'success': True, 'data': details})
        return jsonify({'success': False, 'message': 'NOT FOUND'}), 404
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/get_client_last_order', methods=['POST'])
def get_client_last_order():
    try:
        data = request.json
        client_id = data.get('client_id')
        if not client_id:
             return jsonify({'success': False, 'message': 'Client ID required'}), 400
        
        order = db.get_last_order_by_client(client_id)
        if order:
            return jsonify({'success': True, 'order': order})
        else:
            return jsonify({'success': True, 'order': None, 'message': 'No orders found'})
            
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/update_order', methods=['POST'])
def update_order():
    try:
        # Similar logic to whatsapp_sync but for update
        # Data: order_id, client_id, note, items (json), paid_amount
        
        order_id = request.form.get('order_id')
        items_json = request.form.get('items')
        client_id = request.form.get('client_id')
        notes = request.form.get('notes', '')
        paid_amount = request.form.get('paid_amount', 0)
        
        if not order_id or not client_id:
             return jsonify({'success': False, 'message': 'Missing Data'}), 400
             
        import json
        items_data = []
        if items_json:
             items_data = json.loads(items_json)
             
        # Payload for DB
        payload = {
            'client_id': client_id,
            'notes': notes,
            'items': items_data,
            'paid_amount': paid_amount
        }
        
        res = db.update_order_full(order_id, payload)
        
        # Handle New Images if any (Append to existing)
        if res.get('success') and 'images' in request.files:
             # Just save them to the same path
             conn = db.get_db_connection()
             saved_order = conn.execute("SELECT local_image_path FROM orders WHERE id=?", (order_id,)).fetchone()
             conn.close()
             
             if saved_order and saved_order['local_image_path']:
                 save_path = saved_order['local_image_path']
                 files = request.files.getlist('images')
                 for idx, file in enumerate(files):
                    if file.filename:
                        ts = datetime.datetime.now().strftime("%H%M%S")
                        fname = sanitize_name(file.filename)
                        final_name = f"{ts}_EDIT_{idx}_{fname}"
                        file_path = os.path.join(save_path, final_name)
                        file.save(file_path)
             
        return jsonify(res)
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
        return jsonify({'success': False, 'message': str(e)}), 500

# --- Mobile Sync: Simple Status Update ---
@app.route('/api/mobile/update_order_status', methods=['POST'])
def mobile_update_order_status():
    """Simple endpoint for mobile to update order status only."""
    try:
        data = request.get_json() or request.form
        order_id = data.get('order_id')
        new_status = data.get('status')
        
        if not order_id or not new_status:
            return jsonify({'success': False, 'message': 'Missing order_id or status'}), 400
        
        conn = db.get_db_connection()
        conn.execute("UPDATE orders SET status=? WHERE id=?", (new_status, order_id))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Status updated'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/mobile/delete_order', methods=['POST'])
def mobile_delete_order():
    """Simple endpoint for mobile to delete an order."""
    try:
        data = request.get_json() or request.form
        order_id = data.get('order_id')
        
        if not order_id:
            return jsonify({'success': False, 'message': 'Missing order_id'}), 400
        
        conn = db.get_db_connection()
        conn.execute("DELETE FROM orders WHERE id=?", (order_id,))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Order deleted'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/mobile/add_order', methods=['POST'])
def mobile_add_order():
    """Receive new order from mobile."""
    try:
        data = request.get_json() or request.form
        client_name = data.get('client_name')
        client_id_mobile = data.get('client_id') # Might be useful
        total = data.get('total')
        items = data.get('items') # JSON List
        notes = data.get('notes', '')
        external_order_id = str(data.get('external_order_id', '') or '').strip()
        
        # Reuse whatsapp_sync logic partially or calls db.save_order_transaction
        # 1. Resolve Client
        conn = db.get_db_connection()
        client = conn.execute("SELECT * FROM clients WHERE name = ?", (client_name,)).fetchone()

        if external_order_id:
            existing = conn.execute(
                "SELECT id FROM orders WHERE notes LIKE ?",
                (f"%ExtID: {external_order_id}%",),
            ).fetchone()
            if existing:
                conn.close()
                return jsonify({'success': True, 'order_id': existing['id'], 'message': 'Order already exists'})

        conn.close()
        
        real_client_id = None
        if client:
            real_client_id = client['id']
        else:
            # Create if not exists (Mobile user should have synced clients, but just in case)
            real_client_id = db.add_new_client(client_name, "", "Retail", "Mobile Order")
            
        # 2. Parse Items
        if isinstance(items, str):
            import json
            items = json.loads(items)
            
        final_items = []
        for item in items:
             final_items.append({
                 'id': item.get('id'), # Product ID
                 'name': item.get('name'),
                 'qty': item.get('qty'),
                 'price': item.get('price'),
                 'total': item.get('price') * item.get('qty')
             })
             
        # 3. Save
        if external_order_id:
            notes = notes.strip()
            ext_tag = f"ExtID: {external_order_id}"
            if ext_tag not in notes:
                notes = f"{notes} | {ext_tag}" if notes else ext_tag

        res = db.save_order_transaction(
            client_id=real_client_id,
            total_amount=total,
            discount=0,
            net_total=total,
            paid_amount=0,
            remaining=total,
            items=final_items,
            payment_method="Mobile",
            notes=f"Mobile Order. {notes}"
        )
        
        # 4. Handle Images (Reuse Logic)
        if res.get('success'):
            order_id = res['order_id']
            try:
                if 'images' in request.files:
                    from file_ops_engine import FileOpsEngine
                    root_path = get_storage_root()
                    engine = FileOpsEngine(root_path)
                    
                    # Create Folder
                    first_prod = final_items[0]['name'] if final_items else "Mobile Product"
                    order_folder = engine.get_creation_path(
                        client['type'] if client else "Retail",
                        client_name,
                        first_prod,
                        notes or "", 
                        str(order_id)
                    )
                    engine.create_folder(order_folder)
                    
                    # Save DB Path
                    conn = db.get_db_connection()
                    conn.execute("UPDATE orders SET local_image_path = ? WHERE id = ?", (order_folder, order_id))
                    conn.commit()
                    conn.close()
                    
                    # Save Files
                    files = request.files.getlist('images')
                    for idx, file in enumerate(files):
                        if file.filename:
                            safe_name = sanitize_name(file.filename)
                            # Generate unique name
                            ts = datetime.datetime.now().strftime("%H%M%S")
                            final_path = os.path.join(order_folder, f"{ts}_MOB_{idx}_{safe_name}")
                            file.save(final_path)
            except Exception as e:
                print(f"Mobile Image Error: {e}") 
        
        return jsonify(res)
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/copy_hd_image', methods=['POST'])
def copy_hd_image():
    """
    High-Fidelity Clipboard Copy (CF_DIB) for Photoshop Compatibility.
    Accepts JSON: {'filename': 'full_path_or_filename'}
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400
            
        # User prompt requested "filename" key, but our robust logic handles paths
        raw_path = data.get('filename') or data.get('image_path', '')
        
        if not raw_path:
             return jsonify({'success': False, 'message': 'No filename/path provided'}), 400
        
        # Sanitize and Resolve Path (Robust Logic)
        if os.path.exists(raw_path):
            abs_path = os.path.abspath(raw_path)
        else:
            abs_path = os.path.abspath(os.path.join(os.getcwd(), raw_path))
            if not os.path.exists(abs_path) and raw_path.startswith('/'):
                 abs_path = os.path.abspath(os.path.join(os.getcwd(), raw_path.lstrip('/')))
        
        if not os.path.exists(abs_path):
            # Fallback for "static/images" assumption in user prompt, just in case
            abs_path_fallback = os.path.join(os.getcwd(), 'static', 'images', raw_path)
            if os.path.exists(abs_path_fallback):
                abs_path = abs_path_fallback
            else:
                 return jsonify({'success': False, 'message': f'File not found: {raw_path}'}), 404

        # Retry loop for clipboard access
        for attempt in range(3):
            try:
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
                
                w, h = image.size
                return jsonify({'success': True, 'message': f'Copied ({w}x{h}) ✅'})
                
            except Exception as clip_err:
                if attempt < 2:
                    time.sleep(0.1)
                    continue
                print(f"Clipboard Retry Error: {clip_err}")
                raise clip_err

    except Exception as e:
        print(f"Clipboard Endpoint Error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

# --- Financial Module Endpoints ---

@app.route('/api/financial/stats', methods=['GET'])
def get_financial_stats_api():
    try:
        stats = db.get_financial_stats()
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/financial/ledger', methods=['GET'])
def get_financial_ledger_api():
    try:
        start = request.args.get('start')
        end = request.args.get('end')
        rows = db.get_financial_ledger(start, end)
        return jsonify(rows)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/financial/categories', methods=['GET'])
def get_categories_api():
    try:
        cats = db.get_unique_categories()
        return jsonify(cats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/financial/transaction', methods=['POST'])
def add_transaction_api():
    try:
        data = request.json
        t_type = data.get('type') # Income, Expense
        category = data.get('category')
        amount = float(data.get('amount', 0))
        description = data.get('description', '')
        user = data.get('user', 'Admin') # Placeholder user
        expense_type = data.get('expense_type', 'Business')
        
        if not t_type or not category or amount <= 0:
            return jsonify({'success': False, 'message': 'Invalid Data'}), 400
            
        res = db.add_general_transaction(t_type, category, amount, description, user, expense_type)
        return jsonify(res)
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/financial/verify_transaction', methods=['POST'])
def verify_transaction_api():
    try:
        data = request.json
        t_id = data.get('id')
        status = data.get('verified', False)
        if not t_id: return jsonify({'success': False})
        
        db.toggle_transaction_verify(t_id, 1 if status else 0)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# --- Obligations API ---
@app.route('/api/financial/obligations', methods=['GET', 'POST', 'DELETE'])
def obligations_api():
    try:
        if request.method == 'GET':
            obs = db.get_obligations()
            return jsonify(obs)
            
        elif request.method == 'POST':
            # Add New
            data = request.json
            name = data.get('name')
            amount = float(data.get('amount', 0))
            day = int(data.get('day', 1))
            
            if not name: return jsonify({'success': False, 'message': 'Name required'}), 400
            
            db.add_obligation(name, amount, day)
            return jsonify({'success': True})
            
        elif request.method == 'DELETE':
            o_id = request.json.get('id')
            db.delete_obligation(o_id)
            return jsonify({'success': True})
            
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/financial/pay_obligation', methods=['POST'])
def pay_obligation_api():
    try:
        data = request.json
        o_id = data.get('id')
        amount = float(data.get('amount', 0))
        note = data.get('note', '')
        
        res = db.pay_obligation(o_id, amount, note)
        return jsonify(res)
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# --- Savings API ---
@app.route('/api/financial/savings', methods=['GET', 'POST'])
def savings_api():
    try:
        if request.method == 'GET':
            balance = db.get_savings_balance()
            return jsonify({'balance': balance})
            
        elif request.method == 'POST':
            # Deposit / Withdraw
            data = request.json
            action = data.get('action') # 'deposit' or 'withdraw'
            amount = float(data.get('amount', 0))
            reason = data.get('reason', '')
            
            if amount <= 0: return jsonify({'success': False, 'message': 'Invalid Amount'}), 400
            
            res = db.process_savings_transaction(action, amount, reason)
            return jsonify(res)
            
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/financial/close_shift', methods=['POST'])
def close_shift_api():
    try:
        # Generate Text Summary for Today
        conn = db.get_db_connection()
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        
        income = conn.execute("SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE type='Income' AND date(date) = ?", (today,)).fetchone()[0]
        expenses = conn.execute("SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE type='Expense' AND date(date) = ?", (today,)).fetchone()[0]
        
        # Detail Sales
        sales_count = conn.execute("SELECT COUNT(*) FROM orders WHERE date(date) = ?", (today,)).fetchone()[0]
        
        txt = f"""--- 📊 تقرير الوردية ({today}) ---
✅ إجمالي الوارد (Income): {income:,.2f} ج.م
🔻 إجمالي المصروفات (Expense): {expenses:,.2f} ج.م
💰 الصافي اليومي: {(income - expenses):,.2f} ج.م

📦 عدد الطلبات الجديدة: {sales_count}

تم الاستخراج: {datetime.datetime.now().strftime("%I:%M %p")}
"""
        conn.close()
        return jsonify({'success': True, 'text': txt})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


# ===================================================================
# 📈 NEXT-GEN FINANCIAL ERP ENDPOINTS (PHASE 2)
# ===================================================================

@app.route('/api/financial/analytics', methods=['GET'])
def get_financial_analytics():
    try:
        import financial_engine
        res = financial_engine.calculate_financial_analytics()
        return jsonify(res)
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/financial/scheduled_obligations', methods=['GET'])
def get_scheduled_obligations_api():
    try:
        obs = db.get_scheduled_obligations()
        return jsonify(obs)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/financial/scheduled_obligations', methods=['POST'])
def add_scheduled_obligation_api():
    try:
        data = request.json or {}
        title = data.get('title')
        total = float(data.get('total_monthly_amount', 0))
        weekly = float(data.get('weekly_deduction_target', 0))
        due_date = data.get('next_due_date')
        
        if not title or total <= 0 or weekly <= 0 or not due_date:
            return jsonify({'success': False, 'message': 'بيانات غير مكتملة'}), 400
            
        res = db.add_scheduled_obligation(title, total, weekly, due_date)
        return jsonify(res)
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/financial/scheduled_obligations/<int:ob_id>', methods=['DELETE'])
def delete_scheduled_obligation_api(ob_id):
    try:
        res = db.delete_scheduled_obligation(ob_id)
        return jsonify(res)
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/financial/scheduled_obligations/<int:ob_id>/history', methods=['GET'])
def get_obligation_history_api(ob_id):
    try:
        res = db.get_obligation_history(ob_id)
        return jsonify(res)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/financial/scheduled_obligations/<int:ob_id>', methods=['PUT', 'PATCH'])
def edit_scheduled_obligation_api(ob_id):
    try:
        data = request.json or {}
        title = data.get('title')
        total = float(data.get('total_monthly_amount', 0))
        
        if not title or total <= 0:
            return jsonify({'success': False, 'message': 'بيانات غير مكتملة'}), 400
            
        res = db.update_scheduled_obligation(ob_id, title, total)
        return jsonify(res)
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/financial/scheduled_obligations/<int:ob_id>/weekly_cut', methods=['POST'])
def weekly_cut_obligation_api(ob_id):
    try:
        import financial_engine
        res = financial_engine.deduct_weekly_obligation(ob_id)
        return jsonify(res)
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/financial/shortages', methods=['GET'])
def get_shortages_api():
    try:
        shortages = db.get_shortages()
        return jsonify(shortages)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/financial/shortages', methods=['POST'])
def add_shortage_api():
    try:
        data = request.json or {}
        name = data.get('name')
        cost = float(data.get('estimated_cost', 0))
        qty = int(data.get('qty', 1))
        
        if not name or cost <= 0:
            return jsonify({'success': False, 'message': 'بيانات غير مكتملة'}), 400
            
        res = db.add_shortage(name, cost, qty)
        return jsonify(res)
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/financial/shortages/<int:shortage_id>/purchase', methods=['POST'])
def purchase_shortage_api(shortage_id):
    try:
        import financial_engine
        res = financial_engine.execute_shortage_purchase(shortage_id)
        return jsonify(res)
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/financial/archive', methods=['GET'])
def get_financial_archive_api():
    try:
        archive = db.get_daily_archive()
        return jsonify(archive)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/financial/shift/close', methods=['POST'])
def close_daily_shift_api():
    try:
        import financial_engine
        user = request.json.get('user', 'System') if request.json else 'System'
        res = financial_engine.close_daily_shift(user)
        return jsonify(res)
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/financial/shift/history', methods=['GET'])
def get_shift_history_api():
    try:
        history = db.get_shift_history()
        return jsonify(history)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/financial/scheduled_obligations/<int:ob_id>/pay_daily', methods=['POST'])
def pay_daily_obligation_api(ob_id):
    try:
        import financial_engine
        res = financial_engine.pay_daily_obligation(ob_id)
        return jsonify(res)
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/financial/scheduled_obligations/<int:ob_id>/pay_weekly', methods=['POST'])
def pay_weekly_obligation_api(ob_id):
    try:
        import financial_engine
        res = financial_engine.pay_weekly_obligation(ob_id)
        return jsonify(res)
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/financial/export_to_purchases', methods=['POST'])
def export_to_purchases_api():
    try:
        import financial_engine
        res = financial_engine.export_weekly_sold_to_purchases()
        return jsonify(res)
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


# --- Mobile Access Routes ---

@app.route('/mobile')
@app.route('/mobile.html')
def serve_mobile():
    """Serve mobile app page"""
    return send_from_directory('web', 'mobile.html')

@app.route('/m')
def mobile_redirect():
    """Short redirect to mobile"""
    from flask import redirect
    return redirect('/mobile.html')

@app.route('/css/<path:filename>')
def serve_css(filename):
    return send_from_directory('web/css', filename)

@app.route('/js/<path:filename>')
def serve_js(filename):
    return send_from_directory('web/js', filename)

@app.route('/api/mobile/login', methods=['POST'])
def mobile_login():
    """Mobile PIN login endpoint"""
    import hashlib
    data = request.json
    pin = data.get('pin', '')
    
    if not pin:
        return jsonify({'success': False, 'error': 'PIN مطلوب'})
    
    pin_hash = hashlib.sha256(pin.encode()).hexdigest()
    
    conn = db.get_db_connection()
    staff = conn.execute(
        "SELECT id, name, role, photo_path FROM staff WHERE pin_hash = ? AND is_active = 1",
        (pin_hash,)
    ).fetchone()
    
    if staff:
        # Auto log attendance
        today = datetime.datetime.now().strftime('%Y-%m-%d')
        existing = conn.execute(
            "SELECT id FROM attendance WHERE staff_id = ? AND date = ?",
            (staff['id'], today)
        ).fetchone()
        
        if not existing:
            db.log_attendance_action(staff['id'], 'check_in')
        
        conn.close()
        return jsonify({
            'success': True,
            'staff': dict(staff),
            'attendance_logged': not existing
        })
    
    conn.close()
    return jsonify({'success': False, 'error': 'رمز خاطئ'})

@app.route('/api/mobile/orders', methods=['GET'])
def mobile_get_orders():
    """Get orders for mobile view with items"""
    conn = db.get_db_connection()
    orders = conn.execute("""
        SELECT o.*, c.name as client_name
        FROM orders o
        LEFT JOIN clients c ON o.client_id = c.id
        ORDER BY o.date DESC LIMIT 100
    """).fetchall()
    
    result = {"prep": [], "ready": [], "done": []}
    
    for o in orders:
        od = dict(o)
        
        # Fetch items for this order
        items = conn.execute("""
            SELECT product_name, qty, price, total 
            FROM order_items 
            WHERE order_id = ?
        """, (od['id'],)).fetchall()
        od['items'] = [dict(i) for i in items]
        
        status = od.get('status', '')
        
        if 'Prep' in status or 'تجهيز' in status:
            result["prep"].append(od)
        elif 'Ready' in status or 'جاهز' in status:
            result["ready"].append(od)
        elif 'Delivered' in status or 'Done' in status or 'تسليم' in status:
            result["done"].append(od)
        else:
            result["prep"].append(od)
            
    conn.close()
    return jsonify(result)

@app.route('/api/mobile/products', methods=['GET'])
def mobile_get_products():
    """Get products for mobile (no cost price)"""
    products = db.get_all_products()
    # Remove cost price
    for p in products:
        if 'cost_price' in p:
            del p['cost_price']
        if 'price_cost' in p:
            del p['price_cost']
    return jsonify(products)

@app.route('/api/network_info', methods=['GET'])
def get_network_info():
    """Get local network IP for sharing"""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        
        return jsonify({
            'success': True,
            'ip': local_ip,
            'port': 7777,
            'url': f"http://{local_ip}:7777/mobile.html"
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'ip': '127.0.0.1',
            'port': 7777,
            'url': 'http://127.0.0.1:7777/mobile.html',
            'error': str(e)
        })



@app.route('/api/mobile/clients', methods=['GET'])
def mobile_get_clients():
    """Get all clients for mobile"""
    try:
        clients = db.get_all_clients()
        return jsonify(clients)
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# --- Mobile Staff System API ---

@app.route('/api/mobile/tasks', methods=['GET'])
def mobile_get_tasks():
    try:
        staff_name = request.args.get('staff_name')
        tasks = db.get_tasks(staff_name)
        return jsonify(tasks)
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/mobile/tasks/add', methods=['POST'])
def mobile_add_task():
    try:
        title = request.form.get('title')
        desc = request.form.get('description')
        assigned_to = request.form.get('assigned_to')
        product_id = request.form.get('product_id')
        
        image_path = None
        if 'image' in request.files:
            file = request.files['image']
            if file.filename:
                root = get_storage_root()
                folder = os.path.join(root, 'tasks')
                ensure_dir(folder)
                filename = f"{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{sanitize_name(file.filename)}"
                save_path = os.path.join(folder, filename)
                file.save(save_path)
                image_path = save_path

        db.add_task(title, desc, assigned_to, product_id, image_path)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/mobile/tasks/update', methods=['POST'])
def mobile_update_task():
    try:
        data = request.json
        task_id = data.get('id')
        status = data.get('status')
        db.update_task_status(task_id, status)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/mobile/chat', methods=['GET'])
def mobile_get_chat():
    try:
        limit = int(request.args.get('limit', 50))
        msgs = db.get_chat_messages(limit)
        return jsonify(msgs)
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/mobile/chat/send', methods=['POST'])
def mobile_send_chat():
    try:
        sender = request.form.get('sender')
        message = request.form.get('message')
        
        image_path = None
        if 'image' in request.files:
            file = request.files['image']
            if file.filename:
                root = get_storage_root()
                folder = os.path.join(root, 'chat')
                ensure_dir(folder)
                filename = f"{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{sanitize_name(file.filename)}"
                save_path = os.path.join(folder, filename)
                file.save(save_path)
                image_path = save_path
                
        db.add_chat_message(sender, message, image_path)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/mobile/calls', methods=['GET'])
def mobile_get_calls():
    try:
        target = request.args.get('target')
        calls = db.get_active_staff_calls(target)
        return jsonify(calls)
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/mobile/calls/add', methods=['POST'])
def mobile_add_call():
    try:
        data = request.json
        res = db.add_staff_call(data.get('caller'), data.get('target'), data.get('type', 'summon'))
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/mobile/calls/resolve', methods=['POST'])
def mobile_resolve_call():
    try:
        data = request.json
        res = db.resolve_staff_call(data.get('id'))
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/mobile/production', methods=['GET'])
def mobile_get_production():
    try:
        summary = db.get_production_summary()
        return jsonify(summary)
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/mobile/production/decrement', methods=['POST'])
def mobile_decrement_production():
    try:
        data = request.json
        db.decrement_production_item(data.get('product_id'), data.get('qty', 1))
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# --- Mobile Order Details API ---
@app.route('/api/mobile/order_details/<int:order_id>', methods=['GET'])
def mobile_order_details(order_id):
    """Get order details with items for mobile view"""
    try:
        details = db.get_order_details(order_id)
        if details:
            return jsonify({'success': True, 'data': details})
        return jsonify({'success': False, 'message': 'Order not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# --- Mobile Client Statement API ---
@app.route('/api/mobile/client_statement/<int:client_id>', methods=['GET'])
def mobile_client_statement(client_id):
    """Get client statement data for mobile view"""
    try:
        data = db.get_client_statement_data(client_id)
        if data:
            return jsonify({'success': True, 'data': data})
        return jsonify({'success': False, 'message': 'Client not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# --- Mobile Inventory Count API ---
@app.route('/api/mobile/inventory', methods=['GET'])
def mobile_get_inventory():
    """Get all products with stock for inventory counting"""
    try:
        products = db.get_all_products()
        # Return only necessary fields for inventory
        inventory_list = [{
            'id': p['id'],
            'name': p['name'],
            'category': p.get('category', ''),
            'system_qty': p.get('stock_qty', 0)
        } for p in products]
        return jsonify(inventory_list)
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/mobile/inventory/count', methods=['POST'])
def mobile_save_inventory_count():
    """Save inventory count from employee"""
    try:
        data = request.json
        product_id = data.get('product_id')
        counted_qty = data.get('counted_qty')
        staff_id = data.get('staff_id')
        notes = data.get('notes', '')
        
        if not product_id or counted_qty is None:
            return jsonify({'success': False, 'message': 'Missing required data'}), 400
        
        result = db.save_inventory_count(product_id, staff_id, counted_qty, notes)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/mobile/inventory/counts', methods=['GET'])
def mobile_get_inventory_counts():
    """Get inventory counts for staff review"""
    try:
        staff_id = request.args.get('staff_id')
        status = request.args.get('status', 'all')
        counts = db.get_inventory_counts(staff_id, status)
        return jsonify(counts)
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# ═══════════════════════════════════════════════════════════════════
# 🔴 LASER OPS CENTER API
# ═══════════════════════════════════════════════════════════════════



@app.route('/api/upload_defect', methods=['POST'])
def upload_defect():
    """Handle defect report from extension."""
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400
            
        product_name = data.get('product_name')
        image_base64 = data.get('image_base64')
        notes = data.get('notes', '')
        
        if not product_name:
             return jsonify({'success': False, 'message': 'Product name required'}), 400

        filename = None
        if image_base64:
            import base64
            if ',' in image_base64:
                image_base64 = image_base64.split(',', 1)[1]
            img_bytes = base64.b64decode(image_base64)
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"defect_{ts}.jpg"
            filepath = os.path.join(LASER_QUEUE_DIR, filename)
            with open(filepath, 'wb') as f:
                f.write(img_bytes)
        
        # Combine product name into notes for clarity
        full_notes = f"Defect: {product_name} - {notes}"
        
        # Add as specific task type
        task_id = db.add_production_task('defect', filename, 1, full_notes)
        
        return jsonify({'success': True, 'task_id': task_id})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

LASER_QUEUE_DIR = os.path.join('web', 'laser_images')
if not os.path.exists(LASER_QUEUE_DIR):
    os.makedirs(LASER_QUEUE_DIR)

@app.route('/api/laser_queue/images', methods=['GET'])
def laser_queue_images():
    """List all images in the laser_queue folder."""
    try:
        images = []
        if os.path.exists(LASER_QUEUE_DIR):
            for f in sorted(os.listdir(LASER_QUEUE_DIR), reverse=True):
                if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.bmp')):
                    images.append({
                        'filename': f,
                        'url': f'/api/laser_queue/file/{f}',
                        'size': os.path.getsize(os.path.join(LASER_QUEUE_DIR, f))
                    })
        return jsonify({'success': True, 'images': images})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/laser_queue/file/<filename>', methods=['GET'])
def laser_queue_serve_file(filename):
    """Serve an image file from laser_queue."""
    return send_from_directory(LASER_QUEUE_DIR, filename)

@app.route('/api/laser_queue/done/<filename>', methods=['DELETE', 'POST'])
def laser_queue_done(filename):
    """Mark image as DONE: delete file and complete associated task."""
    try:
        filepath = os.path.join(LASER_QUEUE_DIR, filename)
        
        # Delete the file
        if os.path.exists(filepath):
            os.remove(filepath)
        
        # Find and complete associated task
        tasks = db.get_production_tasks('pending')
        for t in tasks:
            if t.get('reference_image') == filename:
                db.complete_production_task(t['id'])
                break
        
        return jsonify({'success': True, 'message': f'{filename} removed'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/laser_queue', methods=['GET'])
def get_laser_queue():
    return jsonify(laser_engine.get_queue_summary())

@app.route('/api/laser_queue/upload', methods=['POST'])
def add_laser_task_endpoint():
    try:
        task_type = request.form.get('type', 'manual')
        notes = request.form.get('notes', '')
        file = request.files.get('file')
        
        image_filename = None
        if file and file.filename:
            import uuid
            ext = file.filename.split(".")[-1]
            image_filename = f"{uuid.uuid4()}.{ext}"
            # Save to web/laser_images so it can be served directly
            save_dir = os.path.join('web', 'laser_images')
            os.makedirs(save_dir, exist_ok=True)
            file.save(os.path.join(save_dir, image_filename))
        
        laser_engine.add_manual_task(notes, 1, image_filename)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/laser_queue/done/<int:task_id>', methods=['DELETE'])
def complete_laser_task_endpoint(task_id):
    try:
        laser_engine.complete_task(task_id)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/bootstrap', methods=['GET'])
def get_bootstrap_data():
    try:
        conn = db.get_db_connection()
        clients = [dict(row) for row in conn.execute("SELECT * FROM clients").fetchall()]
        products = [dict(row) for row in conn.execute("SELECT * FROM products").fetchall()]
        categories = [dict(row) for row in conn.execute("SELECT * FROM categories").fetchall()]
        
        # Calculate Dashboard Summary including Weekly Revenue and Expenses
        query = """
        SELECT
            (SELECT COUNT(*) FROM orders) as orders_total,
            (SELECT COUNT(*) FROM orders WHERE date(date) = date('now')) as orders_today,
            (SELECT COUNT(*) FROM orders WHERE status IN ('Under Preparation', 'pending', 'processing', 'تحت التجهيز')) as under_preparation_count,
            (SELECT IFNULL(SUM(total_amount),0) FROM orders WHERE status IN ('Under Preparation', 'pending', 'processing', 'تحت التجهيز')) as under_preparation_value,
            (SELECT COUNT(*) FROM orders WHERE status IN ('Ready', 'ready', 'جاهز للتسليم', 'جاهز')) as ready_count,
            (SELECT IFNULL(SUM(total_amount),0) FROM orders WHERE status IN ('Ready', 'ready', 'جاهز للتسليم', 'جاهز')) as ready_value,
            (SELECT COUNT(*) FROM orders WHERE status IN ('Delivered', 'delivered', 'تم التسليم')) as delivered_count,
            (SELECT IFNULL(SUM(total_amount),0) FROM orders WHERE status IN ('Delivered', 'delivered', 'تم التسليم')) as delivered_value,
            (SELECT COUNT(*) FROM clients) as clients_count,
            (SELECT COUNT(*) FROM clients WHERE balance > 0) as debt_clients_count,
            (SELECT IFNULL(SUM(balance),0) FROM clients WHERE balance > 0) as total_receivables,
            (SELECT COUNT(*) FROM products) as products_count,
            (SELECT IFNULL(SUM(amount), 0) FROM transactions WHERE type='Income' AND date >= date('now', '-7 days')) as weekly_revenue_raw,
            (SELECT IFNULL(SUM(amount), 0) FROM transactions WHERE type='Expense' AND date >= date('now', '-7 days')) as weekly_expenses,
            (SELECT IFNULL(SUM(amount), 0) FROM transactions WHERE type='Income' AND date(date) = date('now')) as daily_revenue,
            500 as daily_expense_target
        """
        raw_summary = dict(conn.execute(query).fetchone())
        
        purchases_list = []
        try:
            invoices = conn.execute("SELECT * FROM purchase_invoices ORDER BY date DESC LIMIT 50").fetchall()
            for inv in invoices:
                inv_dict = dict(inv)
                items = conn.execute("SELECT * FROM purchase_items WHERE invoice_id = ?", (inv_dict['id'],)).fetchall()
                inv_dict['total'] = inv_dict['total_cost']
                inv_dict['created_at'] = inv_dict['date']
                inv_dict['items'] = [dict(item) for item in items]
                purchases_list.append(inv_dict)
        except Exception as pe:
            print(f"Error fetching purchases for bootstrap: {pe}")

        conn.close()

        # Calculate Net Weekly Revenue
        raw_summary['weekly_revenue'] = max(0, raw_summary['weekly_revenue_raw'] - raw_summary['weekly_expenses'])

        orders = db.get_kanban_orders()

        return jsonify({
            "success": True,
            "clients": clients,
            "products": products,
            "categories": categories,
            "orders": orders,
            "dashboard_summary": raw_summary,
            "purchases": purchases_list
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/dashboard-summary', methods=['GET'])
def get_dashboard_summary():
    try:
        conn = db.get_db_connection()
        query = """
        SELECT
            (SELECT COUNT(*) FROM orders) as orders_total,
            (SELECT COUNT(*) FROM orders WHERE date(date) = date('now')) as orders_today,
            (SELECT COUNT(*) FROM orders WHERE status IN ('Under Preparation', 'pending', 'processing', 'تحت التجهيز')) as under_preparation_count,
            (SELECT IFNULL(SUM(total_amount),0) FROM orders WHERE status IN ('Under Preparation', 'pending', 'processing', 'تحت التجهيز')) as under_preparation_value,
            (SELECT COUNT(*) FROM orders WHERE status IN ('Ready', 'ready', 'جاهز للتسليم', 'جاهز')) as ready_count,
            (SELECT IFNULL(SUM(total_amount),0) FROM orders WHERE status IN ('Ready', 'ready', 'جاهز للتسليم', 'جاهز')) as ready_value,
            (SELECT COUNT(*) FROM orders WHERE status IN ('Delivered', 'delivered', 'تم التسليم')) as delivered_count,
            (SELECT IFNULL(SUM(total_amount),0) FROM orders WHERE status IN ('Delivered', 'delivered', 'تم التسليم')) as delivered_value,
            (SELECT COUNT(*) FROM clients) as clients_count,
            (SELECT COUNT(*) FROM clients WHERE balance > 0) as debt_clients_count,
            (SELECT IFNULL(SUM(balance),0) FROM clients WHERE balance > 0) as total_receivables,
            (SELECT COUNT(*) FROM products) as products_count,
            (SELECT IFNULL(SUM(amount), 0) FROM transactions WHERE type='Income' AND date >= date('now', '-7 days')) as weekly_revenue_raw,
            (SELECT IFNULL(SUM(amount), 0) FROM transactions WHERE type='Expense' AND date >= date('now', '-7 days')) as weekly_expenses,
            (SELECT IFNULL(SUM(amount), 0) FROM transactions WHERE type='Income' AND date >= date('now')) as daily_revenue_raw,
            (SELECT IFNULL(SUM(amount), 0) FROM transactions WHERE type='Expense' AND date >= date('now')) as daily_expenses
        """
        raw_summary = dict(conn.execute(query).fetchone())
        conn.close()
        
        raw_summary['weekly_revenue'] = max(0, raw_summary['weekly_revenue_raw'] - raw_summary['weekly_expenses'])
        raw_summary['daily_revenue'] = max(0, raw_summary['daily_revenue_raw'] - raw_summary['daily_expenses'])

        return jsonify({"success": True, "dashboard_summary": raw_summary})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/expenses', methods=['POST'])
def add_expense():
    try:
        data = request.json
        amount = float(data.get('amount', 0))
        category = data.get('category', 'نثريات')
        notes = data.get('notes', '')
        
        if amount <= 0:
            return jsonify({"success": False, "error": "Invalid amount"}), 400
            
        conn = db.get_db_connection()
        c = conn.cursor()
        c.execute("""
            INSERT INTO transactions (client_id, type, category, amount, notes, user, related_ref) 
            VALUES (NULL, 'Expense', ?, ?, ?, 'System', 'Expense')
        """, (category, amount, notes))
        conn.commit()
        conn.close()
        
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/purchases', methods=['POST'])
def add_purchase():
    # 2026-10-12 fix (owner order): the old body wrote direct SQL, invented prices
    # for unknown products (retail = cost*1.5, wholesale = cost*1.2), and set
    # status 'Completed' off the official Pending/Received flow.
    # Now: official functions only. Unknown products are created via
    # db.add_quick_product with 0/0 prices (no invented prices — the owner sets
    # catalog prices deliberately). Stock, last_cost_price and the per-invoice
    # expense (related_ref='Purchase Invoice #N') come from toggle Received.
    try:
        data = request.json
        supplier_name = data.get('supplier_name', 'Unknown Supplier')
        notes = data.get('notes', '')
        items = data.get('items', [])

        if not items:
            return jsonify({"success": False, "error": "No items provided"}), 400

        conn = db.get_db_connection()
        c = conn.cursor()
        prepared = []
        new_products = []
        for item in items:
            product_id = item.get('product_id')
            product_name = item.get('product_name')
            qty = int(item.get('qty', 1))
            cost_price = float(item.get('cost_price', 0))
            if qty <= 0:
                conn.close()
                return jsonify({"success": False, "error": f"Invalid qty for {product_name}"}), 400
            if not product_id:
                if not product_name:
                    conn.close()
                    return jsonify({"success": False, "error": "Item missing product_name"}), 400
                p = c.execute("SELECT id FROM products WHERE name = ?", (product_name,)).fetchone()
                if p:
                    product_id = p['id']
                else:
                    product_id = db.add_quick_product(product_name, 'مشتريات', 0, 0)
                    new_products.append(product_name)
            prepared.append({"product_id": product_id, "product_name": product_name,
                             "qty": qty, "cost": cost_price})
        conn.close()

        payload = {
            "supplier_id": None,
            "supplier_name": supplier_name,
            "notes": notes,
            "date": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "items": prepared,
        }
        res = db.save_purchase_invoice(payload)
        if not res.get('success'):
            return jsonify(res), 400
        invoice_id = res['invoice_id']

        rec = db.toggle_purchase_status(invoice_id, 'Received')
        if not rec.get('success'):
            db.delete_purchase(invoice_id)  # roll back: no orphan invoice
            return jsonify(rec), 500

        resp = {"success": True, "invoice_id": invoice_id}
        if new_products:
            resp["warning"] = "منتجات أُنشئت بأسعار 0 — عيّن أسعارها من الكتالوج: " + ", ".join(new_products)
        return jsonify(resp)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

import os
import gevent
from flask import Response

@app.route('/api/stream_events')
def stream_events():
    def event_stream():
        last_mtime = 0
        db_path = "pos_data.db"
        wal_path = "pos_data.db-wal"
        
        while True:
            try:
                mtime = 0
                if os.path.exists(db_path):
                    mtime = max(mtime, os.path.getmtime(db_path))
                if os.path.exists(wal_path):
                    mtime = max(mtime, os.path.getmtime(wal_path))
                    
                if last_mtime == 0:
                    last_mtime = mtime
                elif mtime > last_mtime:
                    last_mtime = mtime
                    yield 'data: {"type": "update"}\n\n'
                    
                yield ": ping\n\n"
            except Exception:
                pass
            gevent.sleep(1)
            
    return Response(event_stream(), mimetype="text/event-stream")

if __name__ == '__main__':
    # Ensure DB init
    db.init_db()
    
    # Next-Gen Financial ERP auto-archive and self-heal checks
    try:
        import financial_engine
        print("[INFO] Running daily financial archiving and obligations checks...")
        arch_res = financial_engine.run_auto_archive()
        financial_engine.check_and_reset_obligations()
        print(f"[OK] Archiving completed: {arch_res}")
    except Exception as init_err:
        print(f"[WARNING] Failed to run financial startup checks: {init_err}")
        
    port = 7777
    print(f"Server running on http://127.0.0.1:{port}")
    # app.run(host='0.0.0.0', port=port, debug=True)
    from gevent.pywsgi import WSGIServer
    http_server = WSGIServer(('0.0.0.0', port), app)
    http_server.serve_forever()
