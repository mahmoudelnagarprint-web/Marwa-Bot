import sys
import os

DB_FILE = "g:/ai/Elnagar POS/database.py"

REPLACEMENT_BLOCK = """def recalculate_client_balance(client_id):
    \"\"\"
    Audit Function: Re-sums all financial history to fix any balance drift.
    Formula: Balance = (Sum(Orders.net_total) + Sum(ManualDebt)) - Sum(Payments)
    ManualDebt should EXCLUDE system-generated debts linked to Orders to avoid double counting.
    \"\"\"
    conn = get_db_connection()
    c = conn.cursor()
    try:
        # 1. Sum of Orders (Net Total) - INCLUDE ALL VALID STATUSES
        orders_sum = c.execute("SELECT COALESCE(SUM(total_amount), 0) FROM orders WHERE client_id = ? AND status != 'Cancelled'", (client_id,)).fetchone()[0]
        
        # 2. Sum of Manual Debts (Transactions type='debt')
        debt_sum = c.execute(\"\"\"
            SELECT COALESCE(SUM(amount), 0) FROM transactions 
            WHERE client_id = ? 
            AND type = 'debt'
            AND (notes IS NULL OR notes NOT LIKE '%Order #%')
            AND (related_ref IS NULL OR related_ref NOT LIKE '%Order #%')
        \"\"\", (client_id,)).fetchone()[0]
        
        # 3. Sum of Payments (Transactions type='payment' or 'Income')
        payment_sum = c.execute("SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE client_id = ? AND type IN ('payment', 'Income')", (client_id,)).fetchone()[0]
        
        # 4. Calculate Theoretical Balance
        theo_balance = (orders_sum + debt_sum) - payment_sum
        
        # 5. Update Client
        c.execute("UPDATE clients SET balance = ? WHERE id = ?", (theo_balance, client_id))
        conn.commit()
        
        return {
            'success': True, 
            'new_balance': theo_balance,
            'details': {
                'orders': orders_sum,
                'manual_debt': debt_sum,
                'payments': payment_sum
            }
        }
        
    except Exception as e:
        conn.rollback()
        return {'success': False, 'error': str(e)}
    finally:
        conn.close()

def update_product_details(p_id, name, cat, price_w, price_r, sort_order):
    conn = get_db_connection()
    c = conn.cursor()
    
    # Price Protection Layer
    if price_r is not None and price_w is not None:
        price_r = float(price_r)
        price_w = float(price_w)
        if price_r < price_w and price_r > 0:
            price_r, price_w = price_w, price_r # Swap if reversed
        if price_r == 0 and price_w > 0:
            price_r = price_w

    c.execute(\"\"\"
        UPDATE products 
        SET name=?, category=?, price_wholesale=?, price_retail=?, sort_order=?
        WHERE id=?
    \"\"\", (name, cat, price_w, price_r, sort_order, p_id))
    conn.commit()
    conn.close()

def update_product_prices(p_id, price_r, price_w):
    \"\"\"Updates only the pricing of a product.\"\"\"
    conn = get_db_connection()
    c = conn.cursor()
    
    # Price Protection Layer
    if price_r is not None and price_w is not None:
        price_r = float(price_r)
        price_w = float(price_w)
        if price_r < price_w and price_r > 0:
            price_r, price_w = price_w, price_r
        if price_r == 0 and price_w > 0:
            price_r = price_w

    if price_r is not None and price_w is not None:
         c.execute("UPDATE products SET price_retail=?, price_wholesale=? WHERE id=?", (price_r, price_w, p_id))
    elif price_r is not None:
         c.execute("UPDATE products SET price_retail=? WHERE id=?", (price_r, p_id))
    elif price_w is not None:
         c.execute("UPDATE products SET price_wholesale=? WHERE id=?", (price_w, p_id))
         
    conn.commit()
    conn.close()

def delete_product(p_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM products WHERE id = ?", (p_id,))
    conn.commit()
    conn.close()

def update_product_stock_db(p_id, qty_change):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE products SET stock_qty = stock_qty + ? WHERE id = ?", (qty_change, p_id))
    conn.commit()
    conn.close()

def update_order_item_from_statement(order_ids, product_name, new_qty, new_price):
    \"\"\"
    Update Qty/Price for a specific product across one or multiple orders (Batch Update).
    If multiple orders, Price is updated for all.
    Qty is tricky: We will Only update Qty if it's a SINGLE order to avoid ambiguity.
    \"\"\"
    conn = get_db_connection()
    c = conn.cursor()
    try:
        # Convert IDs list
        if isinstance(order_ids, str):
            order_ids = [int(x) for x in order_ids.split(',') if x]
        
        if not order_ids:
            return {'success': False, 'error': \"No orders specified\"}

        # 1. Update Price (Apply to ALL)
        for oid in order_ids:
            # Get current item to calc delta for Total
            row = c.execute("SELECT qty FROM order_items WHERE order_id=? AND product_name=?", (oid, product_name)).fetchone()
            if row:
                current_qty = row['qty']
                
                # If Single Order, we might update Qty too
                final_qty = current_qty
                if len(order_ids) == 1 and new_qty is not None:
                     final_qty = float(new_qty)
                
                # Calc new Total
                new_total = final_qty * float(new_price)
                
                # Update Item
                c.execute(\"\"\"
                    UPDATE order_items 
                    SET price=?, qty=?, total=? 
                    WHERE order_id=? AND product_name=?
                \"\"\", (new_price, final_qty, new_total, oid, product_name))
                
                # Update Order Grand Total
                # Recalculate order total from items
                c.execute(\"\"\"
                    UPDATE orders 
                    SET total_amount = (SELECT SUM(total) FROM order_items WHERE order_id=?)
                    WHERE id=?
                \"\"\", (oid, oid))
        
        conn.commit()
        return {'success': True}
        
    except Exception as e:
        conn.rollback()
        return {'success': False, 'error': str(e)}
    finally:
        conn.close()

# --- Category Management ---
def get_all_categories_db():
    conn = get_db_connection()
    cats = conn.execute("SELECT * FROM categories ORDER BY name ASC").fetchall()
    conn.close()
    return [dict(c) for c in cats]

def add_category_db(name):
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO categories (name) VALUES (?)", (name,))
        conn.commit()
        return {"success": True, "id": c.lastrowid}
    except sqlite3.IntegrityError:
        return {"success": False, "error": "Category already exists"}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        conn.close()

def update_category_db(cat_id, new_name):
    conn = get_db_connection()
    c = conn.cursor()
    try:
        # Get old name first
        old_cat = c.execute("SELECT name FROM categories WHERE id=?", (cat_id,)).fetchone()
        if not old_cat: return {"success": False, "error": "Category not found"}
        old_name = old_cat['name']
        
        # Update category table
        c.execute("UPDATE categories SET name=? WHERE id=?", (new_name, cat_id))
        
        # Update associated products
        c.execute("UPDATE products SET category=? WHERE category=?", (new_name, old_name))
        
        conn.commit()
        return {"success": True}
    except sqlite3.IntegrityError:
        return {"success": False, "error": \"Name already taken\"}
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()

def delete_category_db(cat_id):
    conn = get_db_connection()
    c = conn.cursor()
    try:
        # Get category name
        cat = c.execute("SELECT name FROM categories WHERE id=?", (cat_id,)).fetchone()
        if not cat: return {"success": False, "error": \"Category not found\"}
        cat_name = cat['name']
        
        # Move products to 'Uncategorized'
        c.execute("UPDATE products SET category='Uncategorized' WHERE category=?", (cat_name,))
        
        # Delete category
        c.execute("DELETE FROM categories WHERE id=?", (cat_id,))
        
        conn.commit()
        return {"success": True}
    except Exception as e:
        conn.rollback()
        return {"success": False, "error": str(e)}
    finally:
        conn.close()

def infer_category(name):
    name = name.lower()
    if 'فانوس' in name or 'مصحف' in name or 'رمضان' in name:
        return 'رمضان'
    if 'بوكس' in name or 'هدية' in name or 'هدايا' in name:
        return 'هدايا'
    if 'تابلوه' in name or 'برواز' in name:
        return 'تابلوهات'
    if 'ميدال' in name or 'مديلي' in name or 'سلسلة' in name:
        return 'اكسسوارات'
    if 'مج' in name or 'كوب' in name:
        return 'طباعة'
    if 'نوت' in name or 'أجندة' in name:
        return 'طباعة'
    return 'غير مصنف'

def add_quick_product(name, cat, price_r, price_w):
    if not cat or cat.strip() == "":
        cat = infer_category(name)
        
    # Price Protection Layer
    price_r = float(price_r or 0)
    price_w = float(price_w or 0)
    if price_r < price_w and price_r > 0:
        price_r, price_w = price_w, price_r
    if price_r == 0 and price_w > 0:
        price_r = price_w

    conn = get_db_connection()
    c = conn.cursor()
    c.execute(\"\"\"INSERT INTO products (name, category, price_retail, price_wholesale, stock_qty) VALUES (?, ?, ?, ?, 0)\"\"\",
              (name, cat, price_r, price_w))
    new_id = c.lastrowid
    conn.commit()
    conn.close()
    return new_id

"""

def repair():
    with open(DB_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    start_marker = "def recalculate_client_balance(client_id):"
    end_marker = "def resolve_or_create_product_for_external_order("

    start_idx = content.find(start_marker)
    end_idx = content.find(end_marker)

    if start_idx == -1 or end_idx == -1:
        print(f"Error: Markers not found. Start: {start_idx}, End: {end_idx}")
        return

    # Construct new content
    new_content = content[:start_idx] + REPLACEMENT_BLOCK + content[end_idx:]

    with open(DB_FILE, "w", encoding="utf-8") as f:
        f.write(new_content)
    print("Successfully repaired database.py")

if __name__ == "__main__":
    repair()
