import sqlite3
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

conn = sqlite3.connect(r'G:\ai\Elnagar POS\pos_data.db')
c = conn.cursor()

# Find client for order #335
c.execute("SELECT c.id, c.name, c.balance FROM clients c JOIN orders o ON o.client_id = c.id WHERE o.id = 335")
row = c.fetchone()
print("Client for order #335:", row)

client_id, client_name, balance = row

# Update order status to Delivered
c.execute("UPDATE orders SET status = 'Delivered' WHERE id = 335")
print(f"Updated order #335 status to Delivered.")

# Reduce client balance by order total (150)
c.execute("UPDATE clients SET balance = balance - 150 WHERE id = ?", (client_id,))
print(f"Reduced client balance by 150.")

conn.commit()

# Verify
c.execute("SELECT id, name, balance FROM clients WHERE id = ?", (client_id,))
print("Updated client:", c.fetchone())
c.execute("SELECT id, status FROM orders WHERE id = 335")
print("Updated order:", c.fetchone())
