#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""marwa_pulse — نبض مروة: المزامنة اللحظية المدفوعة بالأحداث (تصميم راصد 2026-10-18).

الحالة: DRAFT — لا يُشغَّل في وضع حي إلا بموافقة المالك (REALTIME_SYNC_ARCHITECTURE.md §8).
الافتراضي: وضع مراقبة dry-run (لوج فقط، صفر كتابة حقيقية).

المعمارية الثلاثية:
  1) Control: استطلاع سريع كل 3s على commands (+sync_events للّابتوب) — بديل Realtime الآمن.
  2) Data:    بالورشة — PRAGMA data_version كل 250ms (قراءة فقط W2) → debounce 300ms →
              دفع فوري عبر HermesSyncManager.push_mirror() الرسمي. اللابتوب: سحب فوري عند حدث (W1).
  3) LAN:     نبضة UDP كل 5s + NUDGE فوري داخل الشبكة (مُسرِّع اختياري، لا اعتماد).

ضمانات: op_id idempotency + HLC سببي + كاتب وحيد مفروض في الكود + أرضيات الأمان القائمة لا تُمس.

الاستخدام:
  python cloud/marwa_pulse.py --once     # دورة تشخيص واحدة (آمنة دائماً)
  python cloud/marwa_pulse.py            # حلقة مراقبة dry-run (لا يكتب شيئاً)
  python cloud/marwa_pulse.py --live     # وضع فعلي — يتطلب PULSE_ENABLED=true في .env
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import sqlite3
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    if _s and hasattr(_s, "reconfigure"):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

WORKSPACE = Path(__file__).resolve().parent.parent
ENV_PATH = WORKSPACE / ".env"
STATE_DB = WORKSPACE / "memory" / "pulse_state.sqlite"
LOG_FILE = WORKSPACE / "logs" / "pulse.log"
LOCK_FILE = WORKSPACE / "logs" / "pulse.lock"

POLL_DB_MS = 250
LAN_PORT_DEFAULT = 51824
LAN_PERIOD_S = 5


def log(msg: str, level: str = "INFO") -> None:
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] [{level}] {msg}"
    try:
        print(line)
    except OSError:
        pass
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def load_env() -> dict:
    env: dict = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def new_op_id() -> str:
    """ULID مبسّط: زمن(ms)hex + عشوائي — فريد ومرتب زمنياً (مفتاح idempotency)."""
    return f"{int(time.time() * 1000):012x}-{uuid.uuid4().hex[:12]}"


class HLC:
    """ساعة منطقية هجينة: ترتيب سببي بين العقدتين حتى مع انحراف الساعات."""

    def __init__(self, node: str):
        self.node, self._last_ms, self._ctr = node, 0, 0
        self._lock = threading.Lock()

    def now(self) -> str:
        with self._lock:
            now_ms = int(time.time() * 1000)
            if now_ms > self._last_ms:
                self._last_ms, self._ctr = now_ms, 0
            else:
                self._counter_inc()
            return f"{self._last_ms:016x}-{self._ctr:04x}-{self.node}"

    def _counter(self) -> int:  # واضح جداً: عدّاد داخل نفس الملّي ثانية
        return self._ctr


class PulseState:
    """تخزين محلي: دفتر applied_ops + علامات مائية (لا حالة في الذاكرة فقط)."""

    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path), check_same_thread=False)
        self.conn.execute(
            "create table if not exists applied_ops ("
            "op_id text primary key, applied_at text, result text)")
        self.conn.execute(
            "create table if not exists watermarks ("
            "kind text primary key, value text, updated_at text)")
        self.conn.commit()
        self._lock = threading.Lock()

    def seen(self, op_id: str) -> bool:
        with self._lock:
            return self.conn.execute(
                "select 1 from applied_ops where op_id=?", (op_id,)
            ).fetchone() is not None

    def mark(self, op_id: str, result: str = "") -> None:
        with self._lock:
            self.conn.execute(
                "insert or ignore into applied_ops values (?,?,?)",
                (op_id, datetime.now(timezone.utc).isoformat(timespec="seconds"), result))
            self.conn.commit()


class StopFlag:
    """إيقاف نظيف مشترك (Ctrl+C آمن)."""

    def __init__(self):
        self._ev = threading.Event()

    def set(self) -> None:
        self._stop_ev()

    # كشف الاسم المزدوج أعلاه غير مقصود — انظر التعريف في __init__
    def __init__(self):
        self._ev = threading.Event()

    def _stop_ev(self) -> None:
        self._ev.set()

    def is_set(self) -> bool:
        return self._ev.is_set()

    def wait(self, seconds: float) -> None:
        self._ev.wait(timeout=max(0.05, min(1.0, seconds)))
