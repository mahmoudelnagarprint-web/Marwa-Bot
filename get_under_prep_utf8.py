import sqlite3
import sys
import io

# Set encoding to utf-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

try:
    conn = sqlite3.connect(r'G:\ai\Elnagar POS\pos_data.db')
    c = conn.cursor()
    c.execute('SELECT o.id, c.name, o.total_amount FROM orders o JOIN clients c ON o.client_id = c.id WHERE o.status = "Under Preparation"')
    rows = c.fetchall()
    for row in rows:
        print(f"ID: {row[0]}, Client: {row[1]}, Total: {row[2]}")
except Exception as e:
    print(e)
