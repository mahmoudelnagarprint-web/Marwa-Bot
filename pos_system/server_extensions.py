from flask import Blueprint, jsonify, request
import database as db
import json

sync_bp = Blueprint('sync_bp', __name__)

@sync_bp.route('/api/sync/push', methods=['POST'])
def sync_push():
    """
    Receives list of orders from Mobile.
    Payload: [ {client_name, total, date, items: [], ...}, ... ]
    """
    try:
        orders = request.json
        if not orders:
            return jsonify({'success': True, 'message': 'No orders to sync'})

        synced_count = 0
        errors = []

        for order_data in orders:
            try:
                # 1. Resolve Client
                client_name = order_data.get('client_name')
                client_phone = order_data.get('client_phone', '')
                client_type = order_data.get('client_type', 'Retail')
                
                conn = db.get_db_connection()
                client = conn.execute("SELECT id FROM clients WHERE name = ?", (client_name,)).fetchone()
                
                client_id = None
                if client:
                    client_id = client['id']
                else:
                    client_id = db.add_new_client(client_name, client_phone, client_type, 'Created via Mobile Sync')
                
                conn.close()

                # 2. Extract Metadata
                total = float(order_data.get('total', 0))
                paid = float(order_data.get('paid', 0))
                discount = float(order_data.get('discount', 0))
                remaining = total - paid - discount
                notes = order_data.get('notes', 'Mobile Order')
                items = order_data.get('items', [])
                if isinstance(items, str):
                    items = json.loads(items)

                # 3. Save Order
                result = db.save_order_transaction(
                    client_id=client_id,
                    total_amount=total,
                    discount=discount,
                    net_total=total - discount,
                    paid_amount=paid,
                    remaining=remaining,
                    items=items,
                    payment_method=order_data.get('payment_method', "Credit"),
                    notes=notes
                )
                
                if result.get('success'):
                    synced_count += 1
                else:
                    errors.append(f"Failed to save order for {client_name}: {result.get('error')}")

            except Exception as e:
                errors.append(f"Error processing order: {str(e)}")

        return jsonify({
            'success': True, 
            'synced': synced_count, 
            'errors': errors
        })

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@sync_bp.route('/api/sync/pull', methods=['GET'])
def sync_pull():
    """
    Returns latest Clients and Products for Mobile to Cache.
    """
    try:
        # 1. Clients
        clients = db.get_all_clients()
        clients_data = [{
            'id': c['id'],
            'name': c['name'],
            'phone': c['phone'],
            'balance': c['balance'],
            'type': c.get('type', 'Retail')
        } for c in clients]

        # 2. Products
        products = db.get_all_products()
        products_data = [{
            'id': p['id'],
            'name': p['name'],
            'price': p['price_retail'],
            'price_wholesale': p.get('price_wholesale', p['price_retail']),
            'category': p['category'],
            'stock': p.get('stock_qty', 0)
        } for p in products]

        # 3. Stats (Carbon Copy Dashboard)
        import datetime
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        conn = db.get_db_connection()
        today_sales = conn.execute("SELECT SUM(total_amount) FROM orders WHERE date(date) = ?", (today,)).fetchone()[0] or 0
        total_clients = conn.execute("SELECT COUNT(*) FROM clients").fetchone()[0] or 0
        total_balance = conn.execute("SELECT SUM(balance) FROM clients").fetchone()[0] or 0
        pending_orders = conn.execute("SELECT COUNT(*) FROM orders WHERE status != 'Delivered'").fetchone()[0] or 0
        conn.close()

        return jsonify({
            'success': True,
            'clients': clients_data,
            'products': products_data,
            'stats': {
                'today_sales': today_sales,
                'total_clients': total_clients,
                'total_debt': total_balance,
                'pending_orders': pending_orders
            }
        })

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
