import sqlite3
import sys
import shutil
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

DB = r'G:\ai\Naggar Print POS Agent\_sandbox_pos_writer\pos_data.db'
BACKUP = DB + '.bak_' + datetime.now().strftime('%Y%m%d_%H%M%S')
shutil.copy2(DB, BACKUP)
print('Backup:', BACKUP)

conn = sqlite3.connect(DB)
cur = conn.cursor()

# Step 1: Zero client balances
cur.execute('UPDATE clients SET balance = 0 WHERE id IN (34, 59)')
print(f'Balances zeroed: {cur.rowcount} rows')

# Step 2: Delete old delivered-order remaining debts for these clients
cur.execute("DELETE FROM transactions WHERE client_id IN (34, 59) AND notes LIKE 'Order % - Remaining'")
print(f'Deleted Remaining debts for 34 & 59: {cur.rowcount} rows')

# Step 3: Delete old general balance for اهداء
cur.execute("DELETE FROM transactions WHERE client_id = 59 AND notes = 'رصيد قديم'")
print(f'Deleted رصيد قديم for 59: {cur.rowcount} rows')

# Step 4: Delete ALL Remaining entries from ALL old delivered orders
cur.execute("DELETE FROM transactions WHERE notes LIKE 'Order % - Remaining'")
print(f'Deleted ALL Remaining entries: {cur.rowcount} rows')

conn.commit()

# Verify
print()
print('=== VERIFICATION ===')
cur.execute('SELECT id, name, balance FROM clients WHERE id IN (34, 59)')
print('Client balances:')
for r in cur.fetchall():
    print(f'  {r}')

cur.execute('SELECT COUNT(*) FROM transactions WHERE notes LIKE "%Remaining%"')
print(f'Remaining entries remaining: {cur.fetchone()[0]}')

# Show remaining transactions for these clients
print()
print('Transactions for جهاااد (34) after:')
cur.execute("SELECT id, type, amount, notes, date FROM transactions WHERE client_id = 34 ORDER BY date DESC LIMIT 5")
for r in cur.fetchall():
    print(f'  {r}')

print()
print('Transactions for اهداء (59) after:')
cur.execute("SELECT id, type, amount, notes, date FROM transactions WHERE client_id = 59 ORDER BY date DESC LIMIT 5")
for r in cur.fetchall():
    print(f'  {r}')

conn.close()
print()
print('DONE! Now re-open the POS program to load updated data.')
