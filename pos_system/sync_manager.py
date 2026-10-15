import os
import time
import datetime
import traceback
import sqlite3
import re
import io
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import database as db
from file_ops_engine import FileOpsEngine

# --- Configuration ---
CREDENTIALS_FILE = 'credentials.json'
# Target Spreadsheet ID (Hardcoded per user request)
SPREADSHEET_ID = '18oQD-8NVnNMKvRzXMMOVt8uop_TcIX9yOIeuPxCxJpM'
IMAGE_DOWNLOAD_DIR = './static/order_images/'

class GoogleSyncManager:
    def __init__(self):
        self.creds = None
        self.drive_service = None
        self.sheet_service = None
        self._authenticate()
        
        # Ensure image dir exists
        if not os.path.exists(IMAGE_DOWNLOAD_DIR):
            os.makedirs(IMAGE_DOWNLOAD_DIR)

    def _authenticate(self):
        try:
            if not os.path.exists(CREDENTIALS_FILE):
                raise FileNotFoundError(f"Credentials file '{CREDENTIALS_FILE}' not found.")
                
            self.creds = service_account.Credentials.from_service_account_file(
                CREDENTIALS_FILE, scopes=SCOPES)
            
            self.drive_service = build('drive', 'v3', credentials=self.creds)
            self.sheet_service = build('sheets', 'v4', credentials=self.creds)
            print("✅ Google API Authenticated Successfully.")
        except Exception as e:
            print(f"❌ Authentication Failed: {e}")
            raise e

    def _get_spreadsheet_id(self):
        # Return the hardcoded ID
        return SPREADSHEET_ID

    # --- Image Logic ---
    def download_images(self, image_names):
        """
        Downloads images from Drive by Name.
        Args:
            image_names (list): List of filenames (e.g. ['MyPhoto.jpg']) or relative paths.
        Returns:
            str: Comma-separated list of LOCAL paths.
        """
        local_paths = []
        
        for img_name in image_names:
            if not img_name or not str(img_name).strip():
                continue
                
            # AppSheet might send 'Orders_Images/filename.jpg'. Extract basename.
            safe_name = os.path.basename(img_name)
            
            # Check if exists locally
            local_path = os.path.join(IMAGE_DOWNLOAD_DIR, safe_name)
            if os.path.exists(local_path):
                print(f"   ℹ️ Image exists locally: {safe_name}")
                local_paths.append(local_path)
                continue
                
            try:
                # Search in Drive
                # Note: AppSheet saves images in specific folders. 
                # Searching by name is risky if duplicates exist globally.
                # Ideally we search inside the specific folder, but Name search is requested.
                query = f"name = '{safe_name}' and trashed = false"
                results = self.drive_service.files().list(q=query, fields="files(id, name)").execute()
                files = results.get('files', [])
                
                if not files:
                    print(f"   ⚠️ Image not found on Drive: {safe_name}")
                    continue
                
                # Download the first match
                file_id = files[0]['id']
                request = self.drive_service.files().get_media(fileId=file_id)
                
                with open(local_path, 'wb') as f:
                    downloader = MediaIoBaseDownload(f, request)
                    done = False
                    while done is False:
                        status, done = downloader.next_chunk()
                        # print(f"Download {int(status.progress() * 100)}%.")
                
                print(f"   ⬇️ Downloaded: {safe_name}")
                local_paths.append(local_path)
                
            except Exception as e:
                print(f"   HS Download Error for {safe_name}: {e}")
                
        return ",".join(local_paths)

    # --- Sync Direction 1: Cloud -> Local ---
    def sync_from_cloud(self, spreadsheet_id=None):
        sid = spreadsheet_id or self._get_spreadsheet_id()
        if not sid:
            print("❌ Spreadsheet ID not set in Settings.")
            return

        print("🔃 Starting Sync: Cloud -> Local...")
        
        try:
            # 1. Fetch Data
            # Assume 'Orders' sheet or first sheet if not specified
            range_name = "Orders!A1:ZZ" # Wide range to catch all
            result = self.sheet_service.spreadsheets().values().get(
                spreadsheetId=sid, range=range_name).execute()
            rows = result.get('values', [])
            
            if not rows:
                print("   ⚠️ No data found in Sheet.")
                return

            headers = rows[0]
            data = rows[1:]
            
            # 2. Map Columns (Arabic Headers)
            # We map Header Name -> Index
            col_map = {h.strip(): i for i, h in enumerate(headers)}
            
            # Required Columns
            # Flexible mapping
            def get_val(row, col_name, default=''):
                idx = col_map.get(col_name)
                if idx is not None and idx < len(row):
                    return row[idx]
                return default

            # Image Columns: 'صورة 1' ... 'صورة 16'
            img_cols = [f"صورة {i}" for i in range(1, 17)] # 1 to 16
            
            new_count = 0
            
            # 3. Process Rows
            # Optimization: check 'last_synced_row' setting, but AppSheet inserts rows arbitrarily sometimes?
            # Safer: Valid by content/ID. 
            # We assume there is an 'ID' column or 'رقم الطلب'.
            
            conn = db.get_db_connection()
            
            for i, row in enumerate(data):
                row_num = i + 2
                
                # extract ID
                order_ref = get_val(row, 'رقم الطلب') or get_val(row, 'Order ID') or get_val(row, '_RowNumber')
                if not order_ref: continue # Skip empty rows
                
                # Check if exists in DB (using a new column `appsheet_id` if we add it, or just match heuristics)
                # For now, let's use a heuristic check to avoid dupes if we don't have explicit ID column
                # Or create a `synced_ids` table?
                # User asked to "Update local SQLite".
                
                # Let's assume we check if we already have this order.
                # If 'رقم الطلب' matches DB 'id', that's risky if they drift.
                # Better: Check by Client + Product + Date + Price
                
                client_name = get_val(row, 'العميل') or get_val(row, 'Client') or "Unknown_AppSheet"
                product_name = get_val(row, 'المنتج') or get_val(row, 'Product') or "General Product"
                notes = get_val(row, 'ملاحظات') or get_val(row, 'Notes') or ""
                price = float(get_val(row, 'السعر', 0) or 0)
                qty = float(get_val(row, 'الكمية', 1) or 1)
                
                # DUPLICATE CHECK
                # Simple check: Does an order exist with same client, product, date(approx) and notes?
                # We'll use a `notes` tag to identify AppSheet orders?
                # "AppSheet:{order_ref}"
                
                exists = conn.execute("SELECT id FROM orders WHERE notes LIKE ?", (f"%AppSheet:{order_ref}%",)).fetchone()
                if exists:
                    # Already Synced
                    continue
                    
                print(f"   ✨ Found New Order: {client_name} - {product_name}")
                
                # 4. Handle Images
                img_names = []
                for col_name in img_cols:
                    val = get_val(row, col_name)
                    if val:
                        img_names.append(val)
                
                local_images_str = ""
                if img_names:
                    print(f"      📷 Downloading {len(img_names)} images...")
                    local_images_str = self.download_images(img_names)
                
                # 5. Save to DB
                # Ensure Client Exists
                client = conn.execute("SELECT id FROM clients WHERE name=?", (client_name,)).fetchone()
                if client:
                    client_id = client['id']
                else:
                    # Create Client
                    cur = conn.execute("INSERT INTO clients (name, type, notes) VALUES (?, 'Retail', 'From AppSheet')", (client_name,))
                    client_id = cur.lastrowid
                
                # Create Order
                total = price * qty
                # We need a Transaction wrapper? using db.save_order_transaction is better
                # But we can do direct insert for speed/custom logic
                
                # Insert Order
                cur = conn.execute("""
                    INSERT INTO orders (client_id, total_amount, status, notes, local_image_path)
                    VALUES (?, ?, 'Under Preparation', ?, ?)
                """, (client_id, total, f"{notes} [AppSheet:{order_ref}]", local_images_str))
                order_id = cur.lastrowid
                
                # Insert Item
                conn.execute("""
                    INSERT INTO order_items (order_id, product_name, qty, price, total)
                    VALUES (?, ?, ?, ?, ?)
                """, (order_id, product_name, qty, price, total))
                
                new_count += 1
                
            conn.commit()
            conn.close()
            print(f"✅ Sync Complete. {new_count} new orders imported.")
            
        except Exception as e:
            traceback.print_exc()
            print(f"❌ Sync Error: {e}")

    # --- Sync Direction 2: Local -> Cloud ---
    def sync_to_cloud(self, spreadsheet_id=None):
        sid = spreadsheet_id or self._get_spreadsheet_id()
        if not sid: return

        print("🔃 Starting Sync: Local -> Cloud...")
        conn = db.get_db_connection()
        
        # 1. Check for 'synced' column, add if missing (Migration)
        try:
            conn.execute("SELECT synced FROM orders LIMIT 1")
        except:
            print("   🛠️ Migrating DB: Adding 'synced' column...")
            try:
                conn.execute("ALTER TABLE orders ADD COLUMN synced INTEGER DEFAULT 0")
                conn.commit()
            except: pass
            
        # 2. Get Unsynced Orders
        unsynced = conn.execute("""
            SELECT o.id, c.name as client_name, o.total_amount, o.date, o.notes, o.local_image_path
            FROM orders o
            LEFT JOIN clients c ON o.client_id = c.id
            WHERE o.synced = 0 OR o.synced IS NULL
        """).fetchall()
        
        if not unsynced:
            print("   ✅ No local orders to upload.")
            conn.close()
            return
            
        print(f"   Found {len(unsynced)} orders to upload.")
        
        try:
            # 3. Prepare Data for Sheet
            # MAPPING: [ID, Client, Product, Qty, Price, Date, Notes, Image1...]
            # We need to match Sheet Columns structure strictly?
            # Or just append? AppSheet usually requires strict structural match.
            # We'll Append to "Orders" sheet.
            
            # Fetch Sheet headers to know where to put what
            # For this generic implementation, we assume we append to the bottom
            # But the columns must align.
            
            # Let's get Headers first
            range_name = "Orders!A1:ZZ1"
            res = self.sheet_service.spreadsheets().values().get(sid, range=range_name).execute()
            headers = res.get('values', [])[0]
            
            rows_to_upload = []
            ids_to_mark = []
            
            for order in unsynced:
                # We need items for the product info
                items = conn.execute("SELECT product_name, qty, price FROM order_items WHERE order_id=?", (order['id'],)).fetchall()
                prod_str = ", ".join([i['product_name'] for i in items])
                qty_sum = sum([i['qty'] for i in items])
                
                # Build Row Dictionary
                row_dict = {}
                row_dict['رقم الطلب'] = f"LOC-{order['id']}"
                row_dict['العميل'] = order['client_name']
                row_dict['المنتج'] = prod_str
                row_dict['الكمية'] = qty_sum
                row_dict['السعر'] = order['total_amount'] / qty_sum if qty_sum else 0
                row_dict['التاريخ'] = str(order['date'])
                row_dict['ملاحظات'] = order['notes']
                
                # Local Images? We can't easily upload to Drive via API without Write Permission/Logic
                # (User request didn't explicitly ask to UPLOAD images, just 'Export to Sheet')
                # We'll export the local path string to 'Notes' or a dedicated col if available
                # Or just skip images for upload?
                # "Images: AppSheet saves images..." -> Implicitly AppSheet handles uploads usually.
                # If we just put text path in sheet, AppSheet won't see it as image unless it's a URL or Drive Path.
                # We'll leave images empty for upload to avoid complexity unless asked.
                
                # Convert Dict to Ordered List based on Headers
                row_values = []
                for h in headers:
                    h_clean = h.strip()
                    val = row_dict.get(h_clean, "")
                    # Try English mapping too
                    if not val:
                        eng_map = {'Order ID': 'رقم الطلب', 'Client': 'العميل', 'Product': 'المنتج', 'Qty': 'الكمية', 'Price': 'السعر'}
                        # Reverse lookup? No, just map keys
                        pass
                    row_values.append(val)
                
                rows_to_upload.append(row_values)
                ids_to_mark.append(order['id'])
            
            # 4. Batch Append
            body = {'values': rows_to_upload}
            self.sheet_service.spreadsheets().values().append(
                spreadsheetId=sid, range="Orders!A1",
                valueInputOption="USER_ENTERED", body=body).execute()
                
            # 5. Mark as Synced
            q_marks = ",".join(["?"] * len(ids_to_mark))
            conn.execute(f"UPDATE orders SET synced = 1 WHERE id IN ({q_marks})", ids_to_mark)
            conn.commit()
            
            print(f"   ✅ Uploaded {len(rows_to_upload)} orders.")
            
        except Exception as e:
            print(f"❌ Upload Error: {e}")
            traceback.print_exc()
        finally:
            conn.close()

if __name__ == "__main__":
    print("🚀 Starting Sync Manager with Auto-Scheduler (Every 5 Minutes)...")
    
    try:
        manager = GoogleSyncManager()
        # db.save_setting(SPREADSHEET_ID_KEY, "YOUR_SHEET_ID_HERE") # Run once to set
        
        while True:
            print(f"\n⏰ Sync Cycle Started at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            try:
                manager.sync_from_cloud()
                manager.sync_to_cloud()
                print("✅ Cycle Completed.")
            except Exception as inner_e:
                print(f"⚠️ Cycle Error: {inner_e}")
            
            print("💤 Sleeping for 5 minutes...")
            time.sleep(300) # 5 Minutes
            
    except Exception as e:
        print(f"❌ Fatal Init Error: {e}")
        input("Press Enter to exit...")
