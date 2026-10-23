import sqlite3
try:
    conn = sqlite3.connect(r'G:\ai\Elnagar POS\pos_data.db')
    c = conn.cursor()
    c.execute('SELECT o.id, c.name, o.total_amount FROM orders o JOIN clients c ON o.client_id = c.id WHERE o.status = "Under Preparation"')
    print(c.fetchall())
except Exception as e:
    print(e)
