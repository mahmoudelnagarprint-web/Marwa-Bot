import os
import sqlite3
import argparse
from firebase_admin_client import get_db, now_iso

DB_PATH = os.path.join(os.path.dirname(__file__), 'pos_data.db')

def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

def mirror_collection(db, cursor, table_name, collection_name, query, dry_run=False):
    print(f"Mirroring {table_name} to {collection_name}...")
    cursor.execute(query)
    rows = cursor.fetchall()
    
    if dry_run:
        print(f"[DRY-RUN] Would mirror {len(rows)} records to {collection_name}.")
        return

    fs_db = get_db()
    batch = fs_db.batch()
    count = 0
    
    # We fetch all existing documents to mark stale ones later if needed, but for now we just overwrite/update
    collection_ref = fs_db.collection(collection_name)
    
    current_time = now_iso()

    for row in rows:
        doc_id = str(row.pop('id', row.get('name'))) # use 'id' or 'name' as doc id
        
        row['sync_state'] = 'active'
        row['updated_at'] = current_time
        
        doc_ref = collection_ref.document(doc_id)
        batch.set(doc_ref, row, merge=True)
        count += 1
        
        if count == 500:
            batch.commit()
            batch = fs_db.batch()
            count = 0

    if count > 0:
        batch.commit()
    
    print(f"Successfully mirrored {len(rows)} records to {collection_name}.")

def mirror_dashboard(db, cursor, dry_run=False):
    query = """
    SELECT
        (SELECT COUNT(*) FROM orders) as orders_total,
        (SELECT COUNT(*) FROM orders WHERE date(date) = date('now')) as orders_today,
        (SELECT COUNT(*) FROM orders WHERE status IN ('pending', 'processing')) as under_preparation_count,
        (SELECT IFNULL(SUM(total_amount),0) FROM orders WHERE status IN ('pending', 'processing')) as under_preparation_value,
        (SELECT COUNT(*) FROM orders WHERE status = 'ready') as ready_count,
        (SELECT IFNULL(SUM(total_amount),0) FROM orders WHERE status = 'ready') as ready_value,
        (SELECT COUNT(*) FROM orders WHERE status = 'delivered') as delivered_count,
        (SELECT IFNULL(SUM(total_amount),0) FROM orders WHERE status = 'delivered') as delivered_value,
        (SELECT COUNT(*) FROM clients) as clients_count,
        (SELECT COUNT(*) FROM clients WHERE balance < 0) as debt_clients_count,
        (SELECT IFNULL(SUM(balance),0) FROM clients WHERE balance < 0) as total_receivables,
        (SELECT COUNT(*) FROM products) as products_count
    """
    cursor.execute(query)
    row = cursor.fetchone()
    if dry_run:
        print(f"[DRY-RUN] Would mirror dashboard summary: {row}")
        return

    fs_db = get_db()
    row['last_mirror_at'] = now_iso()
    fs_db.collection('dashboard_summary').document('latest').set(row, merge=True)
    print("Successfully mirrored dashboard_summary.")

def mirror_all(dry_run=False):
    if not os.path.exists(DB_PATH):
        print(f"Error: {DB_PATH} not found.")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = dict_factory
    cursor = conn.cursor()

    try:
        # Clients
        mirror_collection(conn, cursor, 'clients', 'clients', """
            SELECT 
                c.id, c.name, c.phone, c.type, c.balance, c.notes,
                (SELECT COUNT(*) FROM orders WHERE client_id = c.id) as orders_count,
                (SELECT COUNT(*) FROM orders WHERE client_id = c.id AND status NOT IN ('delivered', 'cancelled')) as open_orders_count,
                (SELECT MAX(date) FROM orders WHERE client_id = c.id) as last_order_date,
                (SELECT MAX(date) FROM transactions WHERE client_id = c.id AND type IN ('payment', 'Income')) as last_payment_date
            FROM clients c;
        """, dry_run)

        # Products
        mirror_collection(conn, cursor, 'products', 'products', """
            SELECT 
                p.id, p.name, p.category, p.stock_qty, p.price_retail as retail_price, p.price_wholesale as wholesale_price, p.last_cost_price as cost_price, p.sort_order, p.stock as legacy_stock,
                (SELECT COUNT(*) FROM order_items WHERE product_id = p.id) as orders_count,
                (SELECT SUM(qty) FROM order_items WHERE product_id = p.id) as total_sold_qty,
                (SELECT MAX(o.date) FROM order_items oi JOIN orders o ON oi.order_id = o.id WHERE oi.product_id = p.id) as last_sold_at
            FROM products p;
        """, dry_run)

        # Orders
        mirror_collection(conn, cursor, 'orders', 'orders', """
            SELECT 
                o.id, o.client_id, c.name as client_name, c.phone as client_phone, c.type as client_type, 
                o.total_amount, 
                o.status, o.date, o.notes, o.local_image_path, o.source_path as source,
                (SELECT COUNT(*) FROM order_items WHERE order_id = o.id) as items_count
            FROM orders o LEFT JOIN clients c ON o.client_id = c.id;
        """, dry_run)

        # Order Items
        mirror_collection(conn, cursor, 'order_items', 'order_items', """
            SELECT id, order_id, product_id, product_name, qty, price, total FROM order_items;
        """, dry_run)

        # Transactions
        mirror_collection(conn, cursor, 'transactions', 'transactions', """
            SELECT t.id, t.client_id, c.name as client_name, t.type, t.amount, t.category, t.notes, t.date, t.related_ref, t.user
            FROM transactions t LEFT JOIN clients c ON t.client_id = c.id;
        """, dry_run)

        # Categories
        mirror_collection(conn, cursor, 'categories', 'categories', """
            SELECT id, name FROM categories;
        """, dry_run)

        mirror_dashboard(conn, cursor, dry_run)
        
        # Log sync
        if not dry_run:
            fs_db = get_db()
            fs_db.collection('sync_log').add({
                'type': 'full_mirror',
                'status': 'success',
                'timestamp': now_iso()
            })
            
            fs_db.collection('sync_status').document('mirror_status').set({
                'last_mirror_at': now_iso(),
                'status': 'active'
            }, merge=True)

    finally:
        conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mirror POS Data to Firebase Firestore")
    parser.add_argument('--dry-run', action='store_true', help="Run without writing to Firebase")
    parser.add_argument('--once', action='store_true', help="Run once and exit")
    args = parser.parse_args()

    print(f"Starting Firebase Mirror (Dry Run: {args.dry_run})...")
    mirror_all(dry_run=args.dry_run)
    print("Mirror process complete.")
