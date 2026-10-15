import csv
import urllib.request
import io
import os
import re
import time
from database import get_db_connection, get_setting

def fetch_and_sync_orders():
    """
    Smart Sync from Google Sheets:
    1. Fetches CSV.
    2. Parses Product Name (extracts Price).
    3. Auto-creates Products & Clients.
    4. Downloads Images into Intelligent Folder Structure (No Duplicates).
    """
    
    sheet_url = get_setting("google_sheet_url")
    if not sheet_url:
        return {'success': False, 'error': "No Sheet URL defined in Settings."}

    # 1. Resolve URL (Robust Regex)
    id_match = re.search(r'/d/([a-zA-Z0-9-_]+)', sheet_url)
    if not id_match:
        return {'success': False, 'error': "Invalid Sheet URL format (Missing ID)"}
    
    sheet_id = id_match.group(1)
    csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
    
    gid_match = re.search(r'[?&]gid=([0-9]+)', sheet_url)
    if gid_match:
        csv_url += f"&gid={gid_match.group(1)}"

    print(f"DEBUG: Fetching from {csv_url}")
    
    stats = {'added': 0, 'skipped': 0, 'errors': []}

    try:
        # 2. Fetch CSV
        req = urllib.request.Request(csv_url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        response = urllib.request.urlopen(req)
        content = response.read().decode('utf-8')
        
        f = io.StringIO(content)
        reader = csv.DictReader(f)
        
        conn = get_db_connection()
        c = conn.cursor()
        
        # Helper for Sanity
        def clean_folder_name(n): 
            return "".join([c for c in n if c.isalnum() or c in (' ','-','_')]).strip()

        for row in reader:
            try:
                # 3. Read & Parse Data
                raw_product_name = row.get('Product') or row.get('Item') or row.get('المنتج') or row.get('الصنف') or ""
                client_name = row.get('Client') or row.get('Customer') or row.get('العميل') or row.get('الاسم') or "Unknown Client"
                phone = row.get('Phone') or row.get('Mobile') or row.get('الهاتف') or row.get('رقم الهاتف') or ""
                qty_str = row.get('Qty') or row.get('Quantity') or row.get('العدد') or row.get('الكمية') or "1"
                image_url = row.get('Image') or row.get('Photo') or row.get('صورة') or row.get('الصورة') or row.get('المرفقات') or ""
                
                if not raw_product_name: continue # Skip empty rows

                # --- A. Smart Product Parsing (Extract Price) ---
                # Look for number at the end: "Tray 150" -> Price=150
                price_retail = 0.0
                clean_product_name = raw_product_name.strip()
                
                # Regex: Find number at end (e.g. " 150", "-150", "150")
                # Group 1 is the number.
                price_match = re.search(r'[\s\-](\d+(\.\d+)?)(\s|$)', raw_product_name) 
                # Or even simpler: just find the last number in string?
                # User example: "Wooden Tray 150" -> 150. "Box - 200" -> 200.
                
                # Let's try searching for the last number sequence
                all_nums = re.findall(r'(\d+(?:\.\d+)?)', raw_product_name)
                if all_nums:
                    # Assume price is the last number found? Risky if name is "Box 20x20 500". 
                    # User implied price is usually distinct. 
                    # Let's take the last one as price_retail.
                    price_retail = float(all_nums[-1])
                    
                    # Remove that price string from name to clean it
                    # Find last occurrence of that number and remove it
                    # (Simple replace might remove "150" from "150 Box 150", so be careful, but accept minor risk)
                    parts = raw_product_name.rpartition(all_nums[-1])
                    clean_product_name = parts[0] + parts[2]
                    # Cleanup extra spaces/dashes
                    clean_product_name = clean_product_name.strip(" -_")

                # --- B. Product Sync (DB Check) ---
                p_row = c.execute("SELECT id, category FROM products WHERE name = ?", (clean_product_name,)).fetchone()
                if p_row:
                    p_id = p_row['id']
                    category = p_row['category'] or "Uncategorized"
                else:
                    # CREATE PRODUCT
                    # Default Category for now (Or could extract from Sheet if column exists? User didn't specify)
                    # Let's assume Sheet has 'Category' column? If not, 'New Products'.
                    category = row.get('Category') or row.get('Cat') or row.get('التصنيف') or "New Products"
                    c.execute("""
                        INSERT INTO products (name, category, price_retail, price_wholesale, stock) 
                        VALUES (?, ?, ?, 0, 0)
                    """, (clean_product_name, category, price_retail))
                    p_id = c.lastrowid
                
                # --- C. Client Sync ---
                c_row = c.execute("SELECT id FROM clients WHERE phone = ? AND phone != ''", (phone,)).fetchone()
                if c_row:
                    client_id = c_row['id']
                    # Could update name here if changed? Skip for safety.
                else:
                    c.execute("INSERT INTO clients (name, phone, type, balance) VALUES (?, ?, 'Retail', 0)", 
                              (client_name, phone))
                    client_id = c.lastrowid

                # --- D. Intelligent Folder & Image Download (Unified with FileOpsEngine) ---
                local_rel_path = ""
                if image_url:
                    from file_ops_engine import FileOpsEngine
                    
                    local_base = get_setting("local_images_path")
                    if local_base:
                         engine = FileOpsEngine(local_base)
                         
                         # Determine Client Type (Default Retail)
                         c_type = 'Retail'
                         client_row = c.execute("SELECT type FROM clients WHERE id=?", (client_id,)).fetchone()
                         if client_row and client_row['type']: c_type = client_row['type']

                         # Generate Standard Atomic Path
                         # Note: Sync orders might not have 'notes' yet, or we use empty string
                         # Order ID is needed for Atomic Path. We have p_id, but order_id is next.
                         # Wait, we create order *after* this block in original code. 
                         # We need order_id for the folder name: {Product}_{Note}_{ID}
                         # So we must insert Order FIRST, then handle Images.
                         pass 
                
                # --- E. Create Order FIRST (Reordered for Atomic Naming) ---
                # Calculate Total
                try: 
                    qty = int(float(qty_str.replace(',','').strip()))
                except: qty = 1
                
                total_amount = price_retail * qty
                status_english = 'Under Preparation' 

                c.execute("""
                    INSERT INTO orders (client_id, total_amount, status, date, local_image_path)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?)
                """, (client_id, total_amount, status_english, "")) # Temp Check: Empty Path
                order_id = c.lastrowid
                
                # Order Item
                c.execute("""
                    INSERT INTO order_items (order_id, product_id, product_name, qty, price, total)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (order_id, p_id, clean_product_name, qty, price_retail, total_amount))
                
                # --- F. ALWAYS Handle Folder Creation (Atomic Naming) ---
                # User Requirement: Folder must exist immediately upon sync.
                try:
                    from file_ops_engine import FileOpsEngine
                    local_base = get_setting("local_images_path")
                    if local_base:
                         engine = FileOpsEngine(local_base)
                         
                         # Get Client Info
                         c_type = 'Retail'
                         client_row = c.execute("SELECT type, name FROM clients WHERE id=?", (client_id,)).fetchone()
                         if client_row: c_type = client_row['type']
                         
                         # Generate Path
                         target_dir = engine.get_creation_path(c_type, client_name, clean_product_name, "", order_id)
                         os.makedirs(target_dir, exist_ok=True)
                         
                         # Update Order with Path IMMEDIATELY
                         c.execute("UPDATE orders SET local_image_path = ? WHERE id = ?", (target_dir, order_id))

                         # Download Image if exists
                         if image_url:
                             img_id_match = re.search(r'id=([a-zA-Z0-9-_]+)', image_url)
                             if not img_id_match: img_id_match = re.search(r'/d/([a-zA-Z0-9-_]+)', image_url)

                             if img_id_match:
                                img_id = img_id_match.group(1)
                                dl_link = f"https://drive.google.com/uc?export=download&id={img_id}"
                                fname = f"sync_{int(time.time()*1000)}.jpg"
                                full_path = os.path.join(target_dir, fname)
                                
                                req_img = urllib.request.Request(dl_link, headers={'User-Agent': 'Mozilla/5.0'})
                                with urllib.request.urlopen(req_img, timeout=20) as r_img, open(full_path, 'wb') as f_out:
                                    f_out.write(r_img.read())

                except Exception as e_img:
                     print(f"Folder/Image Error: {e_img}")
                     stats['errors'].append(f"Folder Fail: {clean_product_name}")

                stats['added'] += 1

            except Exception as row_e:
                print(f"Row Error: {row_e}")
                stats['errors'].append(str(row_e))
        
        conn.commit()
        conn.close()
        
        return {'success': True, 'stats': stats}

    except Exception as e:
        return {'success': False, 'error': str(e)}

def retry_failed_images():
    """
    Scans orders with image_url but NO local_image_path, and tries to download them.
    """
    conn = get_db_connection()
    c = conn.cursor()
    
    # Select failed images
    orders = c.execute("SELECT o.id, o.image_url, o.client_id, c.name, c.phone, oi.product_name, p.category FROM orders o JOIN clients c ON o.client_id = c.id JOIN order_items oi ON o.id = oi.order_id LEFT JOIN products p ON oi.product_id = p.id WHERE o.image_url != '' AND (o.local_image_path IS NULL OR o.local_image_path = '')").fetchall()
    
    local_base = get_setting("local_images_path") or "C:/Ramadan_POS_Images"
    success_count = 0
    errors = []
    
    import urllib.request
    import os
    import re
    import time

    def clean_folder_name(n): 
        return "".join([c for c in n if c.isalnum() or c in (' ','-','_')]).strip()

    seen_orders = set()

    for row in orders:
        if row['id'] in seen_orders: continue
        seen_orders.add(row['id'])

        try:
            image_url = row['image_url']
            client_name = row['name']
            phone = row['phone']
            product_name = row['product_name']
            category = row['category'] or "Uncategorized"
            
            # Construct Path
            safe_cat = clean_folder_name(category)
            safe_prod = clean_folder_name(product_name)
            safe_client = clean_folder_name(f"{client_name}_{phone}")
            
            target_dir = os.path.join(local_base, safe_cat, safe_prod, safe_client)
            os.makedirs(target_dir, exist_ok=True)
            
            # Download Logic
            img_id_match = re.search(r'id=([a-zA-Z0-9-_]+)', image_url)
            if not img_id_match: img_id_match = re.search(r'/d/([a-zA-Z0-9-_]+)', image_url)

            if img_id_match:
                img_id = img_id_match.group(1)
                dl_link = f"https://drive.google.com/uc?export=download&id={img_id}"
                
                fname = f"retry_{int(time.time()*1000)}.jpg"
                full_path = os.path.join(target_dir, fname)
                
                req_img = urllib.request.Request(dl_link, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req_img, timeout=20) as r_img, open(full_path, 'wb') as f_out:
                    f_out.write(r_img.read())
                
                # Update DB
                c.execute("UPDATE orders SET local_image_path = ? WHERE id = ?", (full_path, row['id']))
                success_count += 1
                
        except Exception as e:
            errors.append(f"Order {row['id']}: {e}")
    
    conn.commit()
    conn.close()
    return {'success': True, 'fixed': success_count, 'errors': errors}
