import sqlite3
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

conn = sqlite3.connect(r'G:\ai\Elnagar POS\pos_data.db')
c = conn.cursor()

# Find client for order #337
c.execute("SELECT c.id, c.name, c.balance, o.total_amount FROM clients c JOIN orders o ON o.client_id = c.id WHERE o.id = 337")
row = c.fetchone()
print("Client for order #337:", row)

client_id, client_name, balance, total_amount = row

# Update order status to Delivered
c.execute("UPDATE orders SET status = 'Delivered' WHERE id = 337")
print(f"Updated order #337 status to Delivered.")

# Reduce client balance by order total
c.execute("UPDATE clients SET balance = balance - ? WHERE id = ?", (total_amount, client_id))
print(f"Reduced client balance by {total_amount}.")

conn.commit()

# Verify
c.execute("SELECT id, name, balance FROM clients WHERE id = ?", (client_id,))
print("Updated client:", c.fetchone())
c.execute("SELECT id, status FROM orders WHERE id = 337")
print("Updated order:", c.fetchone())
