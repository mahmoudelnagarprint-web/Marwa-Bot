from __future__ import annotations

import json
import logging
import signal
import subprocess
import sys
import threading
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent
LOG_PATH = ROOT_DIR / "telegram_importer_loop.log"
STOP_EVENT = threading.Event()


def configure_logging() -> logging.Logger:
    logger = logging.getLogger("telegram_importer_loop")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    file_handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    logger.propagate = False
    return logger


def load_runtime_settings() -> tuple[int, Path]:
    telegram_dir = ROOT_DIR / "telegram_bot"
    if str(telegram_dir) not in sys.path:
        sys.path.insert(0, str(telegram_dir))

    from config import load_settings

    settings = load_settings()
    return settings.telegram_import_interval_seconds, settings.telegram_import_flag_path


def build_import_command() -> list[str]:
    return [
        "py",
        "-3.11",
        "telegram_importer.py",
        "--once",
        "--limit",
        "10",
    ]


def request_stop(signum: int, _frame: object) -> None:
    logger = logging.getLogger("telegram_importer_loop")
    logger.info("Stop signal received: %s", signum)
    STOP_EVENT.set()


def consume_trigger_flag(flag_path: Path) -> bool:
    if not flag_path.exists():
        return False
    try:
        flag_path.unlink()
        return True
    except Exception:
        logging.getLogger("telegram_importer_loop").exception("Failed to clear trigger flag: %s", flag_path)
        return True


def parse_summary(stdout_text: str) -> dict:
    stdout_text = (stdout_text or "").strip()
    if not stdout_text:
        return {}
    try:
        return json.loads(stdout_text)
    except Exception:
        return {}


def run_once(logger: logging.Logger) -> dict:
    command = build_import_command()
    result = subprocess.run(
        command,
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    stdout_text = (result.stdout or "").strip()
    stderr_text = (result.stderr or "").strip()
    summary = parse_summary(stdout_text)

    if result.returncode != 0:
        logger.error("Importer failed with exit code %s", result.returncode)
        if stdout_text:
            logger.error("Importer stdout:\n%s", stdout_text)
        if stderr_text:
            logger.error("Importer stderr:\n%s", stderr_text)
        return {
            "success": False,
            "returncode": result.returncode,
            "summary": summary,
            "stderr": stderr_text,
            "stdout": stdout_text,
        }

    processed = len(summary.get("results", [])) if isinstance(summary, dict) else 0
    selected = int(summary.get("selected_pending_rows", 0)) if isinstance(summary, dict) else 0

    if processed > 0 or selected > 0:
        logger.info("Importer processed %s pending row(s).", processed or selected)
        if stdout_text:
            logger.info("Importer summary:\n%s", stdout_text)
    elif stderr_text:
        logger.warning("Importer stderr:\n%s", stderr_text)

    return {
        "success": True,
        "returncode": 0,
        "summary": summary,
        "stderr": stderr_text,
        "stdout": stdout_text,
    }


def main() -> int:
    logger = configure_logging()
    signal.signal(signal.SIGINT, request_stop)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, request_stop)

    interval_seconds, flag_path = load_runtime_settings()
    logger.info("Telegram importer loop started. Interval=%s seconds | flag=%s", interval_seconds, flag_path)

    while not STOP_EVENT.is_set():
        try:
            triggered = consume_trigger_flag(flag_path)
            if triggered:
                logger.info("Import trigger flag detected. Running importer immediately.")
            run_once(logger)
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received. Stopping loop.")
            STOP_EVENT.set()
            break
        except Exception:
            logger.exception("Importer loop iteration failed unexpectedly.")

        if STOP_EVENT.wait(interval_seconds):
            break

    logger.info("Telegram importer loop stopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
