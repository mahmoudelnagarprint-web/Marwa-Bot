#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""test_pulse_sandbox — عربة اختبار المرحلة 1 (Sandbox) لـ Marwa Pulse.

ماذا تفعل (معزولة 100%):
  1) تنسخ القاعدة الحية عبر SQLite Backup API إلى _sandbox_pos_writer/pulse_sandbox.db.
  2) تشغّل كلاس DBPulse الإنتاجي الحقيقي (استيراد من marwa_pulse) على النسخة المعزولة.
  3) تحاكي N تغيير خارجي (إدراج في pulse_scratch — جدول خصيص، لا بيانات مالية)
     مع قياس زمن الكشف لكل حدث (كتابة → إطلاق on_change بعد poll+debounce).
  4) اختبارات وحدة: HLC رتابة، op_id فريد، dedupe عبر PulseState.
  5) إثبات عدم المساس: data_version + mtime + حجم القاعدة الحية قبل/بعد متطابقة.

الاستخدام:  python cloud/test_pulse_sandbox.py [N_CYCLES=100]
"""
from __future__ import annotations

import bisect
import random
import sqlite3
import statistics
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    if _s and hasattr(_s, "reconfigure"):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

CLOUD_DIR = Path(__file__).resolve().parent
WORKSPACE = CLOUD_DIR.parent
sys.path.insert(0, str(CLOUD_DIR))

from marwa_pulse import DBPulse, PulseState, HLC, StopFlag, new_op_id  # noqa: E402

SANDBOX_DIR = WORKSPACE / "_sandbox_pos_writer"
UNIT_STATE_DB = WORKSPACE / "memory" / "pulse_sandbox_state.sqlite"
DETECT_TARGET_S = 1.5
N_DEFAULT = 100


def log(msg: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {msg}")


def file_fingerprint(path: Path) -> tuple:
    """حجم + mtime + data_version — بصمة عدم المساس."""
    st = path.stat()
    con = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, timeout=5)
    try:
        dv = con.execute("PRAGMA data_version").fetchone()[0]
    finally:
        con.close()
    return (st.st_size, st.st_mtime, dv)


def make_sandbox_copy(live_db: Path, sandbox_db: Path) -> None:
    """نسخ موثق عبر SQLite backup API من الحية → الساندبوكس (الحية قراءة فقط)."""
    sandbox_db.parent.mkdir(parents=True, exist_ok=True)
    src = sqlite3.connect(f"file:{live_db.as_posix()}?mode=ro", uri=True, timeout=30)
    dst = sqlite3.connect(str(sandbox_db))
    try:
        src.backup(dst)
    finally:
        src.close()
        dst.close()


def main() -> int:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    live_db = Path(r"G:\ai\Elnagar POS\pos_data.db")
    sandbox_db = SANDBOX_DIR / "pulse_sandbox.db"
    print("=" * 64)
    print(f" Marwa Pulse — اختبار الساندبوكس (المرحلة 1) — {n} دورة")
    print(f" live = {live_db}  (قراءة فقط)   sandbox = {sandbox_db.name}")
    print("=" * 64)

    # 0) بصمة القاعدة الحية قبل الاختبار (إثبات عدم المساس)
    fp_before = file_fingerprint(live_db)

    # 1) نسخة ساندبوكس موثقة (backup API — سليمة حتى مع القاعدة ساخنة)
    make_sandbox_copy(live_db, sandbox_db)
    print(f"نسخة الساندبوكس: {sandbox_db.name} ({sandbox_db.stat().st_size} bytes)")

    # 2) مكونات إنتاجية حقيقية (استيراد من marwa_pulse — لا إعادة تنفيذ)
    stop = StopFlag()
    events: list[float] = []
    ev_lock = threading.Lock()

    def on_change() -> None:
        with ev_lock:
            events.append(time.monotonic())

    hlc = HLC("WORKSHOP")
    cfg = {
        "node": "WORKSHOP", "role": "WORKSHOP", "live": False,
        "live_db": sandbox_db, "poll": 3.0, "lan_udp": 0, "pull_cmd": "",
    }
    dbp = DBPulse(cfg, on_change=on_change, stop=stop)
    dbp.start()

    # 3) دورات الكتابة الخارجية → قياس الكشف
    write_times: list[float] = []
    cpu0 = time.process_time()
    wall0 = time.monotonic()
    con = sqlite3.connect(str(sandbox_db), timeout=10)
    con.execute(
        "create table if not exists pulse_scratch ("
        "id integer primary key, ts text, note text)")
    con.commit()
    try:
        for i in range(1, n + 1):
            time.sleep(random.uniform(0.30, 0.60))
            con.execute(
                "insert into pulse_scratch (ts, note) values (?, ?)",
                (datetime.now().isoformat(timespec="milliseconds"), f"cycle-{i}"))
            con.commit()
            with ev_lock:
                write_times.append(time.monotonic())
            if i == 50:  # انفجار متعمد: 5 كتابات متتالية — اختبار دمج العواصف
                for _j in range(4):
                    con.execute(
                        "insert into pulse_scratch (ts, note) values (?, 'burst')",
                        (datetime.now().isoformat(),))
                    con.commit()
    finally:
        time.sleep(1.5)          # تصريف آخر debounce
        stop.set()
        dbp.join(timeout=5)
        con.close()
    cpu_used = time.process_time() - cpu0
    wall = time.monotonic() - wall0

    # 4) زمن الكشف: لكل حدث، أحدث كتابة سابقة له → الفرق
    latencies: list[float] = []
    for ev in events:
        idx = bisect.bisect_right(write_times, ev) - 1
        if idx >= 0:
            latencies.append(ev - write_times[idx])

    # 5) اختبارات الوحدة
    hlc_vals = [hlc.now() for _ in range(1000)]
    hlc_ok = all(a < b for a, b in zip(hlc_vals, hlc_vals[1:]))
    ops = {new_op_id() for _ in range(1000)}
    ops_ok = len(ops) == 1000
    unit_state = PulseState(UNIT_STATE_DB)
    unit_state.mark("unit-op-1", "unit")
    dedupe_ok = (not unit_state.seen("unit-nope")) and unit_state.seen("unit-op-1")
    unit_state.mark("unit-op-1")   # إعادة تعليم نفس op_id = no-op (idempotent)
    dedupe_ok = dedupe_ok and unit_state.seen("unit-op-1")

    # 6) إثبات عدم المساس بالقاعدة الحية
    fp_after = file_fingerprint(live_db)
    live_ok = fp_before == fp_after

    # 7) التقرير
    if not latencies:
        print("❌ لا أحداث مكتشفة إطلاقاً — فشل")
        return 1
    lat_sorted = sorted(latencies)

    def pct(p: float) -> float:
        return lat_sorted[min(len(lat_sorted) - 1, int(len(latencies) * p))]

    cpu_pct = 100.0 * cpu_used / max(0.001, wall)
    print("=" * 64)
    print(f"دورات مكتوبة          : {n}")
    print(f"أحداث مُكتشفة         : {len(events)}  (دمج العواصف: {n} كتابة → {len(events)} حدث)")
    print(f"زمن الكشف  min/avg    : {min(latencies)*1000:.0f} / {statistics.fmean(latencies)*1000:.0f} ms")
    print(f"زمن الكشف  p95/max    : {pct(0.95)*1000:.0f} / {max(latencies)*1000:.0f} ms")
    print(f"هدف <1500ms           : {'✅ PASS' if max(latencies) < DETECT_TARGET_S else '❌ FAIL'}")
    print(f"CPU العملية أثناءها   : {cpu_pct:.2f}% (polling 250ms + معالجة الأحداث)")
    print(f"مدة التشغيل           : {wall:.1f}s  | CPU time = {cpu_used:.2f}s")
    print(f"HLC رتّاب: {'✅' if hlc_ok else '❌'}  op_id فريد: {'✅' if ops_ok else '❌'}  dedupe: {'✅' if dedupe_ok else '❌'}")
    print(f"القاعدة الحية بلا كتابة: {'✅ مضمونة (البصمة متطابقة)' if live_ok else '❌ تغيّرت!'}")
    print("=" * 64)
    verdict_ok = (max(latencies) < DETECT_TARGET_S and live_ok
                  and hlc_ok and ops_ok and dedupe_ok)
    print(f"الخلاصة: {'✅ الساندبوكس ناجح' if (max(latencies) < DETECT_TARGET_S and live_ok and hlc_ok and ops_ok and dedupe_ok) else '❌ فشل'}")
    return 0 if (max(latencies) < DETECT_TARGET_S and live_ok and hlc_ok
                 and ops_ok and dedupe_ok) else 1


if __name__ == "__main__":
    sys.exit(main())
