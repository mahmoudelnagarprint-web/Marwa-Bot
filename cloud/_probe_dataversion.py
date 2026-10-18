# -*- coding: utf-8 -*-
"""probe dataversion: هل يتغير PRAGMA data_version عبر اتصالات ro متجددة؟"""
import sqlite3
import time
from pathlib import Path

db = Path(r"G:\ai\Naggar Print POS Agent\_sandbox_pos_writer\pulse_sandbox.db")
w = sqlite3.connect(str(db), timeout=10)
w.execute("create table if not exists scratch2 (id integer primary key, n text)")
w.commit()

# (A) قارئ جديد كل مرة
for i in range(3):
    v_before = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True).execute(
        "PRAGMA data_version").fetchone()[0]
    con_w.execute("insert into scratch2 (n) values (?)", (f"w{i}",)) if (con_w := sqlite3.connect(str(db), timeout=10)) else None
    con_w.execute("insert into scratch2 (n) values (?)", (f"w{i}",))
    con_w.commit()
    time.sleep(0.3)
    v2 = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True).execute(
        "PRAGMA data_version").fetchone()[0]
    print(f"write#{i}: fresh-ro data_version = {v2}")

# (B) قارئ دائم (اتصال واحد يبقى مفتوحاً)
ro = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
base = ro.execute("PRAGMA data_version").fetchone()[0]
for i in range(3):
    con_w2 = sqlite3.connect(str(db), timeout=10)
    con_w.execute("insert into scratch2 (n) values ('p')")
    con_w.commit()
    time.sleep(0.3)
    now_v = ro.execute("PRAGMA data_version").fetchone()[0]
    print(f"persistent-reader after write: data_version = {now_v} (base {base})")
    base = now_v
con_w.close()
print("done")
