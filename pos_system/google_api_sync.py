
import os
import pickle
import hashlib
import re
import io
import time
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from database import get_db_connection, get_setting

# Scopes required
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets.readonly',
    'https://www.googleapis.com/auth/drive.readonly'
]

# Client Secret File (Hardcoded based on user provided file)
CLIENT_SECRET_FILE = 'client_secret_1003126827898-o1hmot1ks4sv4ddj2s7u06hmgu445jrh.apps.googleusercontent.com.json'

class OrderSyncEngine:
    def __init__(self):
        self.creds = None
        self.service_sheets = None
        self.service_drive = None
        self.local_images_path = get_setting("local_images_path") or "C:/Ramadan_POS_Images"

    def authenticate(self):
        """Standard OAuth2 Flow"""
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                self.creds = pickle.load(token)
        
        # Refresh or Login
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                self.creds.refresh(Request())
            else:
                if not os.path.exists(CLIENT_SECRET_FILE):
                    raise FileNotFoundError(f"Missing Client Secret: {CLIENT_SECRET_FILE}")
                    
                flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
                self.creds = flow.run_local_server(port=0)
            
            # Save token
            with open('token.pickle', 'wb') as token:
                pickle.dump(self.creds, token)
        
        self.service_sheets = build('sheets', 'v4', credentials=self.creds)
        self.service_drive = build('drive', 'v3', credentials=self.creds)
        print("Authenticated Successfully.")

    def get_sheet_id_from_url(self, url):
        match = re.search(r'/d/([a-zA-Z0-9-_]+)', url)
        return match.group(1) if match else None

    def parse_product_price(self, raw_text):
        """
        Logic: Extract last number as price. Remainder is name.
        Example: "فانوس سداسي 100" -> Name: "فانوس سداسي", Price: 100
        """
        if not raw_text: return "", 0.0
        
        # Regex to find the last floating point number in the string
        # Captures: 150, 150.5, etc at the end or surrounded by spaces
        # We look for the LAST match
        matches = re.findall(r'(\d+(?:\.\d+)?)', raw_text)
        
        if matches:
            price_str = matches[-1]
            try:
                price = float(price_str)
            except:
                price = 0.0
            
            # Remove price from text
            # We use rpartition to remove the *last* occurrence only
            parts = raw_text.rpartition(price_str)
            name = parts[0] + parts[2]
            name = name.strip(" -_")
            return name, price
        
        return raw_text, 0.0

    def download_image(self, file_id, target_dir, file_name):
        """Authenticated Drive Download"""
        try:
            request = self.service_drive.files().get_media(fileId=file_id)
            full_path = os.path.join(target_dir, file_name)
            
            # Streaming download
            with io.FileIO(full_path, 'wb') as fh:
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while done is False:
                    status, done = downloader.next_chunk()
            
            return full_path
        except Exception as e:
            print(f"Drive Download Error ({file_id}): {e}")
            return None

    def run_sync(self):
        print("Starting Sync...")
        sheet_url = get_setting("google_sheet_url")
        if not sheet_url: return {'success': False, 'error': 'No Sheet URL'}

        sheet_id = self.get_sheet_id_from_url(sheet_url)
        if not sheet_id: return {'success': False, 'error': 'Invalid URL'}

        try:
            self.authenticate()
            
            # Fetch Data
            # Assuming "Form Responses 1" is the tab name
            range_name = "Form Responses 1!A2:J"  # Columns A to J (Timestamp to Name?)
            result = self.service_sheets.spreadsheets().values().get(
                spreadsheetId=sheet_id, range=range_name).execute()
            rows = result.get('values', [])
            
            print(f"Fetched {len(rows)} rows.")
            
            stats = {'added': 0, 'skipped': 0, 'errors': []}
            
            conn = get_db_connection()
            c = conn.cursor()

            # Process Rows
            for idx, row in enumerate(rows):
                # Columns Mapping (0-indexed) based on user description:
                # A (0): Timestamp
                # C (2): Product 1 (فوانيس)
                # D (3): Product 2 (هلال) -> Fallback
                # E (4): Notes / Phrase (Atomic Label)
                # F (5): Phone
                # I (8): Images (Multiple links)
                # J (9): Customer Name
                
                # Safety pad
                while len(row) < 11: row.append("")
                
                # Parse Timestamp
                raw_ts = row[0]
                timestamp = raw_ts
                try:
                    from datetime import datetime
                    for fmt in ("%m/%d/%Y %H:%M:%S", "%m/%d/%Y %H:%M", "%d/%m/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
                        try:
                            dt = datetime.strptime(raw_ts, fmt)
                            timestamp = dt.strftime("%Y-%m-%d %H:%M:%S")
                            break
                        except ValueError: continue
                except: pass
                
                col_c = row[2]
                col_d = row[3]
                notes = row[4] # Col E
                phone = str(row[5])
                images_cell = row[8]
                customer_name = row[9]
                
                if not customer_name: customer_name = "Unknown"
                
                # 1. Product Logic
                raw_prod = col_c if col_c.strip() else col_d
                if not raw_prod.strip(): continue # Skip empty
                
                prod_name, price = self.parse_product_price(raw_prod)
                
                # Lookup Product ID & Category
                p_row = c.execute("SELECT id, category FROM products WHERE name = ?", (prod_name,)).fetchone()
                p_id = p_row['id'] if p_row else 0
                category = p_row['category'] if p_row and p_row['category'] else "Uncategorized"
                
                if p_id == 0:
                     # Auto-create product? Or leave as 0 (General)?
                     # For safety, let's keep 0 or "Unknown".
                     pass

                # 2. Hash Generation
                hash_input = f"{timestamp}_{customer_name}_{raw_prod}"
                unique_hash = hashlib.md5(hash_input.encode()).hexdigest()
                
                # 3. Check Duplicate
                existing_order = c.execute("SELECT id, image_url, local_image_path FROM orders WHERE unique_hash = ?", (unique_hash,)).fetchone()
                
                order_id = None
                is_new = False
                
                if existing_order:
                    if images_cell and not existing_order['local_image_path']:
                        # Healing needed
                        order_id = existing_order['id']
                        print(f"    > HEALING Order {order_id}...")
                    else:
                        stats['skipped'] += 1
                        continue
                else:
                    # INSERT NEW ORDER (First, to get ID)
                    status = "Under Preparation"
                    total = price * 1
                    
                    # Ensure client exists
                    c_row = c.execute("SELECT id FROM clients WHERE phone = ? AND phone != ''", (phone,)).fetchone()
                    if c_row:
                        client_id = c_row['id']
                    else:
                        c.execute("INSERT INTO clients (name, phone, type, balance) VALUES (?, ?, 'Retail', 0)", (customer_name, phone))
                        client_id = c.lastrowid
                    
                    c.execute("""
                        INSERT INTO orders (client_id, total_amount, status, date, unique_hash, image_url, notes)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (client_id, total, status, timestamp, unique_hash, images_cell, notes))
                    order_id = c.lastrowid
                    is_new = True
                    
                    # Insert Items
                    c.execute("""
                        INSERT INTO order_items (order_id, product_id, product_name, qty, price, total)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (order_id, p_id, prod_name, 1, price, total))
                    
                    stats['added'] += 1

                # 4. Atomic Folder Logic
                # Logic: Root / Category / Product / {Label}_Order{ID}
                def sanitize(n): return str(n).replace('/', '_').replace('\\', '_').replace(':', '_').replace('*', '_').replace('?', '_').replace('"', '_').replace('<', '_').replace('>', '_').replace('|', '_').strip()
                
                label_safe = sanitize(customer_name)
                parts = [label_safe]
                if notes and notes.strip():
                     parts.append(sanitize(notes))
                
                base_name = "_".join(parts)
                folder_name = f"{base_name}_Order{order_id}"
                
                safe_cat = sanitize(category)
                safe_prod = sanitize(prod_name)
                
                target_dir = os.path.join(self.local_images_path, safe_cat, safe_prod, folder_name)

                # 5. Image Download
                local_img_paths = []
                if images_cell:
                    import re
                    raw_urls = re.findall(r'(https?://.*?)(?=https?://|$)', images_cell, flags=re.IGNORECASE | re.DOTALL)
                    urls = [u.strip().rstrip(', \n\r') for u in raw_urls if u.strip()]
                    
                    if urls:
                        os.makedirs(target_dir, exist_ok=True)
                        
                        # Create Order_Details.txt
                        try:
                            with open(os.path.join(target_dir, "Order_Details.txt"), "w", encoding="utf-8") as f:
                                f.write(f"Order #{order_id}\nClient: {customer_name}\nLabel: {label_name}\nNotes: {notes}\nProduct: {prod_name}\n")
                        except: pass

                    for idx, url in enumerate(urls):
                        file_id = None
                        match = re.search(r'id=([^&]+)', url) or re.search(r'/d/([^/]+)', url)
                        if match: file_id = match.group(1)
                        
                        if file_id:
                            fname = f"{unique_hash[:8]}_{idx}.jpg"
                            full_path = os.path.join(target_dir, fname)
                            
                            if os.path.exists(full_path) and os.path.getsize(full_path) > 0:
                                local_img_paths.append(full_path)
                            else:
                                downloaded = self.download_image(file_id, target_dir, fname)
                                if downloaded: local_img_paths.append(downloaded)

                # 6. Update Order Path
                path_str = ",".join(local_img_paths) if local_img_paths else target_dir
                c.execute("UPDATE orders SET local_image_path = ? WHERE id = ?", (path_str, order_id))
            
            conn.commit()
            conn.close()
            return {'success': True, 'stats': stats}

        except Exception as e:
            import traceback
            traceback.print_exc()
            return {'success': False, 'error': str(e)}

if __name__ == "__main__":
    engine = OrderSyncEngine()
    print(engine.run_sync())
