import sqlite3
try:
    conn = sqlite3.connect(r'G:\ai\Elnagar POS\pos_data.db')
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table'")
    print(c.fetchall())
except Exception as e:
    print(e)
