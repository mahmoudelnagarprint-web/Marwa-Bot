import os
import shutil
import datetime
import sqlite3
import traceback
from firebase_admin_client import get_db, get_bucket, update_doc_status, now_iso
import database
try:
    import file_ops_engine
except ImportError:
    file_ops_engine = None

DB_PATH = os.path.join(os.path.dirname(__file__), 'pos_data.db')
BACKUP_DIR = os.path.join(os.path.dirname(__file__), 'Backups')

def backup_db():
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BACKUP_DIR, f"pos_data_backup_fb_importer_{timestamp}.db")
    shutil.copy2(DB_PATH, backup_path)
    return backup_path

def get_pending_docs(collection_name):
    db = get_db()
    docs_stream = db.collection(collection_name).where("status", "==", "pending").limit(50).stream()
    docs = list(docs_stream)
    # Sort locally by created_at to avoid composite index requirement
    try:
        docs.sort(key=lambda d: d.to_dict().get("created_at", "") or "", reverse=False)
    except Exception:
        pass
    return docs

def process_clients_queue(collection_name):
    docs = get_pending_docs(collection_name)
    for doc in docs:
        data = doc.to_dict()
        doc_id = doc.id
        update_doc_status(collection_name, doc_id, 'processing')
        try:
            name = data.get('name')
            phone = data.get('phone', '')
            c_type = data.get('type', 'Retail')
            notes = data.get('notes', '')
            
            # Check if exists
            conn = database.get_db_connection()
            c = conn.cursor()
            c.execute("SELECT id FROM clients WHERE name=? AND phone=?", (name, phone))
            existing = c.fetchone()
            conn.close()
            
            if existing:
                update_doc_status(collection_name, doc_id, 'imported')
                continue
                
            new_id = database.add_new_client(name, phone, c_type, notes)
            update_doc_status(collection_name, doc_id, 'imported')
            print(f"[{collection_name}] Imported client {name} -> ID: {new_id}")
        except Exception as e:
            update_doc_status(collection_name, doc_id, 'failed', str(e))
            print(f"[{collection_name}] Failed {doc_id}: {e}")

def process_products_queue(collection_name):
    docs = get_pending_docs(collection_name)
    for doc in docs:
        data = doc.to_dict()
        doc_id = doc.id
        update_doc_status(collection_name, doc_id, 'processing')
        try:
            name = data.get('name')
            cat = data.get('category', '')
            price_r = data.get('retail_price', 0)
            price_w = data.get('wholesale_price', 0)
            
            new_id = database.add_quick_product(name, cat, price_r, price_w)
            update_doc_status(collection_name, doc_id, 'imported')
            print(f"[{collection_name}] Imported product {name} -> ID: {new_id}")
        except Exception as e:
            update_doc_status(collection_name, doc_id, 'failed', str(e))

def process_orders_queue(collection_name):
    docs = get_pending_docs(collection_name)
    for doc in docs:
        data = doc.to_dict()
        doc_id = doc.id
        update_doc_status(collection_name, doc_id, 'processing')
        try:
            client_id = data.get('client_id')
            total_amount = data.get('total_amount', 0)
            discount = data.get('discount', 0)
            net_total = data.get('net_total', total_amount - discount)
            paid_amount = data.get('paid_amount', 0)
            remaining = net_total - paid_amount
            items = data.get('items', [])
            payment_method = data.get('payment_method', 'Cash')
            notes = data.get('notes', '')
            
            # Map Android items to DB expected format
            mapped_items = []
            for item in items:
                p_id = item.get('product_id')
                p_name = item.get('product_name', 'Unknown')
                qty = item.get('qty', item.get('quantity', 1))
                price = item.get('price', 0)
                total = item.get('total', qty * price)
                
                # Resolve or create product if needed
                if item.get('needs_product_creation') or not p_id:
                    resolved = database.resolve_or_create_product_for_external_order(
                        product_id=p_id,
                        product_name=p_name,
                        client_type=data.get('client_type', 'Retail'),
                        external_price=price
                    )
                    if resolved and resolved.get('success') and resolved.get('product'):
                        p_id = resolved['product']['id']
                        p_name = resolved['product']['name']
                
                mapped_items.append({
                    'id': p_id or 0,
                    'name': p_name,
                    'qty': qty,
                    'price': price,
                    'total': total
                })
            
            # Avoid duplicate external_order_id
            external_order_id = data.get('external_order_id', doc_id)
            conn = database.get_db_connection()
            c = conn.cursor()
            c.execute("SELECT id FROM orders WHERE notes LIKE ?", (f"%{external_order_id}%",))
            existing = c.fetchone()
            conn.close()
            
            if existing:
                update_doc_status(collection_name, doc_id, 'imported', "Already exists")
                continue

            if not notes:
                notes = f"Source: {collection_name}, ExtID: {external_order_id}"
            else:
                notes += f" | ExtID: {external_order_id}"

            res = database.save_order_transaction(client_id, total_amount, discount, net_total, paid_amount, remaining, mapped_items, payment_method, notes)
            
            if res.get('success'):
                update_doc_status(collection_name, doc_id, 'imported')
                print(f"[{collection_name}] Imported order {doc_id} -> ID: {res.get('order_id')}")
            else:
                update_doc_status(collection_name, doc_id, 'failed', res.get('error'))
        except Exception as e:
            update_doc_status(collection_name, doc_id, 'failed', str(e))

def process_payments_queue(collection_name):
    docs = get_pending_docs(collection_name)
    for doc in docs:
        data = doc.to_dict()
        doc_id = doc.id
        update_doc_status(collection_name, doc_id, 'processing')
        try:
            client_id = data.get('client_id')
            amount = data.get('amount')
            method = data.get('method', 'Cash')
            notes = data.get('notes', f"Payment via {collection_name}")
            
            conn = database.get_db_connection()
            c = conn.cursor()
            
            # Check for duplicate action_id
            action_id = data.get('action_id', doc_id)
            c.execute("SELECT id FROM transactions WHERE related_ref = ?", (f"PAY_ACT_{action_id}",))
            if c.fetchone():
                conn.close()
                update_doc_status(collection_name, doc_id, 'imported', "Duplicate action")
                continue

            c.execute("""
                INSERT INTO transactions (client_id, type, category, amount, notes, user, related_ref) 
                VALUES (?, 'Income', 'Payment', ?, ?, 'System', ?)
            """, (client_id, amount, notes, 'System', f"PAY_ACT_{action_id}"))
            
            c.execute("UPDATE clients SET balance = balance - ? WHERE id = ?", (amount, client_id))
            conn.commit()
            conn.close()
            
            update_doc_status(collection_name, doc_id, 'imported')
            print(f"[{collection_name}] Imported payment {amount} for client {client_id}")
        except Exception as e:
            update_doc_status(collection_name, doc_id, 'failed', str(e))

def process_status_queue(collection_name):
    docs = get_pending_docs(collection_name)
    for doc in docs:
        data = doc.to_dict()
        doc_id = doc.id
        update_doc_status(collection_name, doc_id, 'processing')
        try:
            order_id = data.get('order_id')
            new_status = data.get('status')
            payment = data.get('payment', 0)
            method = data.get('payment_method', 'Cash')
            
            res = database.update_order_status(order_id, new_status, payment, method)
            if res is True:
                update_doc_status(collection_name, doc_id, 'imported')
                print(f"[{collection_name}] Updated status order {order_id} -> {new_status}")
            else:
                update_doc_status(collection_name, doc_id, 'failed', str(res))
        except Exception as e:
            update_doc_status(collection_name, doc_id, 'failed', str(e))

def process_images_queue(collection_name):
    docs = get_pending_docs(collection_name)
    bucket = get_bucket()
    for doc in docs:
        data = doc.to_dict()
        doc_id = doc.id
        update_doc_status(collection_name, doc_id, 'processing')
        try:
            order_id = data.get('order_id')
            storage_path = data.get('storage_path')
            
            if not order_id or not storage_path:
                raise ValueError("Missing order_id or storage_path")
                
            blob = bucket.blob(storage_path)
            if not blob.exists():
                raise FileNotFoundError(f"Blob {storage_path} not found")
                
            local_filename = os.path.basename(storage_path)
            local_dir = os.path.join(os.path.dirname(__file__), 'pos_images', 'raw')
            if not os.path.exists(local_dir):
                os.makedirs(local_dir)
                
            local_path = os.path.join(local_dir, local_filename)
            blob.download_to_filename(local_path)
            
            conn = database.get_db_connection()
            c = conn.cursor()
            c.execute("UPDATE orders SET local_image_path = ? WHERE id = ?", (local_path, order_id))
            conn.commit()
            conn.close()
            
            update_doc_status(collection_name, doc_id, 'imported')
            print(f"[{collection_name}] Downloaded image for order {order_id}")
        except Exception as e:
            update_doc_status(collection_name, doc_id, 'failed', str(e))

def run_import_cycle(dry_run=False):
    if dry_run:
        print("[DRY-RUN] Simulating import cycle without executing DB changes...")
        return
        
    print(f"[{now_iso()}] Starting Firebase import cycle...")
    
    # Backup DB before changes
    try:
        backup_db()
    except Exception as e:
        print(f"Warning: DB Backup failed! {e}")

    # Process queues in order
    queues = [
        ('android_clients_queue', process_clients_queue),
        ('android_products_queue', process_products_queue),
        ('android_orders_queue', process_orders_queue),
        ('android_order_images', process_images_queue),
        ('android_payments_queue', process_payments_queue),
        ('android_status_queue', process_status_queue),
        ('telegram_orders_queue', process_orders_queue),
        ('telegram_images_queue', process_images_queue),
        ('telegram_payments_queue', process_payments_queue)
    ]
    
    for q_name, q_func in queues:
        try:
            q_func(q_name)
        except Exception as e:
            print(f"Error processing {q_name}: {e}")
            traceback.print_exc()

    # Avoid triggering full mirror here to save quota
    # print("Triggering quick mirror...")
    # try:
    #     import firebase_mirror_from_pos
    #     firebase_mirror_from_pos.mirror_all(dry_run=False)
    # except Exception as e:
    #     print(f"Quick mirror failed: {e}")

    print("Import cycle finished.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    
    run_import_cycle(args.dry_run)
