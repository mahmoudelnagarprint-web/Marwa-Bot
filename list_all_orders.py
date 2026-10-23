import sqlite3
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

conn = sqlite3.connect(r'G:\ai\Elnagar POS\pos_data.db')
c = conn.cursor()
c.execute('''
    SELECT o.id, c.name, o.status, o.total_amount, o.date
    FROM orders o
    JOIN clients c ON o.client_id = c.id
    ORDER BY o.id
''')
rows = c.fetchall()
print(f"عدد الطلبات: {len(rows)}")
print("-" * 60)
for row in rows:
    oid, cname, status, total, date = row
    print(f"طلب #{oid} | العميل: {cname} | الحالة: {status} | الإجمالي: {total} | التاريخ: {date}")
print("-" * 60)
