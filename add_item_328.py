import sqlite3

try:
    conn = sqlite3.connect(r'G:\ai\Elnagar POS\pos_data.db')
    c = conn.cursor()
    c.execute('INSERT INTO order_items (order_id, product_id, product_name, qty, price, total) VALUES (?, ?, ?, ?, ?, ?)', 
              (328, 6, "طارة خشب", 1, 70.0, 70.0))
    c.execute('UPDATE orders SET total_amount = total_amount + 70.0 WHERE id = 328')
    conn.commit()
    print('Done')
except Exception as e:
    print(e)
