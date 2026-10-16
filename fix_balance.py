import sqlite3

conn = sqlite3.connect(r'G:\ai\Naggar Print POS Agent\pos_data.db')
cur = conn.cursor()

print('='*60)
print('CURRENT STATE BEFORE CHANGES')
print('='*60)

print('\n--- CLIENTS BALANCE ---')
cur.execute('SELECT id, name, balance, type FROM clients WHERE id IN (34, 59)')
for row in cur.fetchall():
    print(f'  ID:{row[0]} | {row[1]} | balance={row[2]} | type={row[3]}')

print('\n--- TRANSACTIONS FOR CLIENT 34 (جهاااد) ---')
cur.execute("""
    SELECT id, type, amount, notes, date, category, "user"
    FROM transactions
    WHERE client_id = 34
    ORDER BY date DESC
""")
for row in cur.fetchall():
    print(f'  [{row[0]}] {row[1]} | {row[2]} | {row[3]} | {row[4]} | cat:{row[5]}')

print('\n--- TRANSACTIONS FOR CLIENT 59 (اهداء) ---')
cur.execute("""
    SELECT id, type, amount, notes, date, category, "user"
    FROM transactions
    WHERE client_id = 59
    ORDER BY date DESC
""")
for row in cur.fetchall():
    print(f'  [{row[0]}] {row[1]} | {row[2]} | {row[3]} | {row[4]} | cat:{row[5]}')

print('\n--- OPEN ORDERS (Under Prep / Ready) ---')
cur.execute("""
    SELECT id, client_id, total_amount, status, date
    FROM orders
    WHERE status IN ('Under Preparation', 'Ready')
    ORDER BY date DESC
""")
for row in cur.fetchall():
    print(f'  Order #{row[0]} | ClientID:{row[1]} | {row[2]} | {row[3]} | {row[4]}')

print('\n--- LEDGER SUMMARY (all clients, debt only) ---')
cur.execute("""
    SELECT client_id, SUM(amount) as total_debt, COUNT(*)
    FROM transactions
    WHERE type = 'debt' AND client_id IS NOT NULL
    GROUP BY client_id
    ORDER BY total_debt DESC
    LIMIT 10
""")
for row in cur.fetchall():
    print(f'  ClientID:{row[0]} | total_debt={row[1]} | count={row[2]}')

print()
print('='*60)
print('ANALYSIS')
print('='*60)

# Check what "old cash" means
print('\n--- ALL transactions with notes containing "Remaining" (OLD DEBT) ---')
cur.execute("""
    SELECT id, client_id, type, amount, notes, date
    FROM transactions
    WHERE notes LIKE '%Remaining%'
    ORDER BY date DESC
""")
for row in cur.fetchall():
    print(f'  [{row[0]}] client={row[1]} | {row[2]} | {row[3]} | {row[4]} | {row[5]}')

print()
