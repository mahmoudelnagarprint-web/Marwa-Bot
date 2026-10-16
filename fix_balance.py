import sqlite3
import sys
import shutil
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

DB_PATH = r'G:\ai\Naggar Print POS Agent\pos_data.db'

# Backup first
backup_path = f'{DB_PATH}.bak_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
shutil.copy2(DB_PATH, backup_path)
print(f'Backup created: {backup_path}')

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

print('\n' + '='*60)
print('STEP 1: ZERO CLIENT BALANCES')
print('='*60)

# Zero جهاااد (client 34)
cur.execute('UPDATE clients SET balance = 0 WHERE id = 34')
print(f'  Client 34 (جهاااد): balance set to 0  -- rows affected: {cur.rowcount}')

# Zero اهداء (client 59)
cur.execute('UPDATE clients SET balance = 0 WHERE id = 59')
print(f'  Client 59 (اهداء): balance set to 0  -- rows affected: {cur.rowcount}')

print('\n' + '='*60)
print('STEP 2: DELETE OLD "Remaining" DEBT ENTRIES (delivered orders)')
print('='*60)

# Delete ALL "Order #NNN - Remaining" entries that are from old delivered orders
# We identify these by notes pattern
cur.execute("""
    DELETE FROM transactions
    WHERE notes LIKE 'Order #% - Remaining'
""")
remaining_deleted = cur.rowcount
print(f'  Deleted "Order #NNN - Remaining" entries: {remaining_deleted}')

print('\n' + '='*60)
print('STEP 3: DELETE OLD GENERAL DEBT (رصيد قديم) for these clients')
print('='*60)

# Delete "رصيد قديم" for client 59
cur.execute("""
    DELETE FROM transactions
    WHERE client_id = 59 AND notes = 'رصيد قديم'
""")
old_debt_deleted = cur.rowcount
print(f'  Deleted old balance entries for اهداء: {old_debt_deleted}')

conn.commit()
print('\n*** COMMITED ***')

# Verify new state
print('\n' + '='*60)
print('VERIFICATION - NEW STATE')
print('='*60)

print('\n--- CLIENT BALANCES AFTER ---')
cur.execute('SELECT id, name, balance, type FROM clients WHERE id IN (34, 59)')
for row in cur.fetchall():
    print(f'  ID:{row[0]} | {row[1]} | balance={row[2]}')

print('\n--- REMAINING "Remaining" debt entries (should be none) ---')
cur.execute("SELECT COUNT(*) FROM transactions WHERE notes LIKE '%Remaining%'")
count = cur.fetchone()[0]
print(f'  Count: {count}')

print('\n--- TRANSACTIONS FOR CLIENT 34 AFTER ---')
cur.execute("SELECT id, type, amount, notes, date FROM transactions WHERE client_id = 34 ORDER BY date DESC LIMIT 10")
for row in cur.fetchall():
    print(f'  [{row[0]}] {row[1]} | {row[2]} | {row[3]} | {row[4]}')

print('\n--- TRANSACTIONS FOR CLIENT 59 AFTER ---')
cur.execute("SELECT id, type, amount, notes, date FROM transactions WHERE client_id = 59 ORDER BY date DESC LIMIT 10")
for row in cur.fetchall():
    print(f'  [{row[0]}] {row[1]} | {row[2]} | {row[3]} | {row[4]}')

print('\n--- TOP 10 CLIENT DEBT BALANCES (should be recalculated) ---')
cur.execute("""
    SELECT c.id, c.name, c.balance,
           (SELECT SUM(t.amount) FROM transactions t WHERE t.client_id = c.id AND t.type = 'debt') as sum_debt,
           (SELECT SUM(t.amount) FROM transactions t WHERE t.client_id = c.id AND t.type IN ('Income','Payment')) as sum_paid
    FROM clients c
    WHERE c.balance != 0
    ORDER BY c.balance DESC
    LIMIT 10
""")
for row in cur.fetchall():
    print(f'  ID:{row[0]} | {row[1]} | balance={row[2]} | sum_debt={row[3]} | sum_paid={row[4]}')

conn.close()
print('\nDone.')
