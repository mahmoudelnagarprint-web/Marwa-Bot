#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
"""android_importer_loop.py — Runs android_importer.py on an interval."""

import json
import logging
import os
import signal
import subprocess
import sys
import threading
from pathlib import Path

ROOT_DIR   = Path(__file__).resolve().parent
LOG_PATH   = ROOT_DIR / "android_importer_loop.log"
STOP_EVENT = threading.Event()

INTERVAL_SECONDS = int(os.environ.get("ANDROID_IMPORT_INTERVAL_SECONDS", "5"))


def configure_logging() -> logging.Logger:
    logger = logging.getLogger("android_importer_loop")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    fh = logging.FileHandler(LOG_PATH, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)
    logger.propagate = False
    return logger


def run_once(logger: logging.Logger) -> None:
    cmd = ["py", "-3.11", "android_importer.py", "--once", "--limit", "10"]
    result = subprocess.run(cmd, cwd=ROOT_DIR, capture_output=True,
                            text=True, encoding="utf-8", errors="replace", check=False)
    stdout = (result.stdout or "").strip()
    stderr = (result.stderr or "").strip()

    if result.returncode != 0:
        logger.error("Android importer failed (exit %s)\n%s", result.returncode, stderr)
        return

    try:
        summary = json.loads(stdout)
        total = len(summary.get("results", []))
        if total > 0:
            logger.info("Android importer processed %s row(s).", total)
            logger.info(stdout)
    except Exception:
        if stderr:
            logger.warning("Android importer stderr: %s", stderr)


def request_stop(signum: int, _frame: object) -> None:
    logging.getLogger("android_importer_loop").info("Stop signal %s received.", signum)
    STOP_EVENT.set()


def main() -> int:
    logger = configure_logging()
    signal.signal(signal.SIGINT, request_stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, request_stop)

    logger.info("Android importer loop started. Interval=%s s", INTERVAL_SECONDS)
    while not STOP_EVENT.is_set():
        try:
            run_once(logger)
        except KeyboardInterrupt:
            STOP_EVENT.set()
            break
        except Exception:
            logger.exception("Loop iteration failed.")
        if STOP_EVENT.wait(INTERVAL_SECONDS):
            break

    logger.info("Android importer loop stopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
