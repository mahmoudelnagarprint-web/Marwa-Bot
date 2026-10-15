import pandas as pd
from database import get_connection

# --- Products ---
def get_products():
    """Fetch all products."""
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM products ORDER BY id DESC", conn)
    conn.close()
    return df

def add_product(name, category, cost_price, selling_price, stock_quantity):
    """Add a new product."""
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "INSERT INTO products (name, category, cost_price, selling_price, stock_quantity) VALUES (?, ?, ?, ?, ?)",
        (name, category, cost_price, selling_price, stock_quantity)
    )
    conn.commit()
    conn.close()

def update_product(product_id, name, category, cost_price, selling_price, stock_quantity):
    """Update an existing product."""
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        """UPDATE products 
           SET name=?, category=?, cost_price=?, selling_price=?, stock_quantity=?
           WHERE id=?""",
        (name, category, cost_price, selling_price, stock_quantity, product_id)
    )
    conn.commit()
    conn.close()

def delete_product(product_id):
    """Delete a product."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM products WHERE id=?", (product_id,))
    conn.commit()
    conn.close()

# --- Clients (Placeholder for future step) ---
def get_clients():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM clients", conn)
    conn.close()
    return df
