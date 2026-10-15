import os
import subprocess
import sys
import time
from pathlib import Path

import psutil


BASE_DIR = Path(__file__).resolve().parent
PYTHON_CMD = str(BASE_DIR / ".venv" / "Scripts" / "python.exe") if (BASE_DIR / ".venv" / "Scripts" / "python.exe").exists() else sys.executable or "python"


def stop_matching_processes(script_names):
    lowered = {name.lower() for name in script_names}
    for proc in psutil.process_iter(["pid", "cmdline"]):
        try:
            cmdline = proc.info.get("cmdline") or []
            joined = " ".join(cmdline).lower()
            if any(name in joined for name in lowered):
                proc.terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    time.sleep(2)

    for proc in psutil.process_iter(["pid", "cmdline"]):
        try:
            cmdline = proc.info.get("cmdline") or []
            joined = " ".join(cmdline).lower()
            if any(name in joined for name in lowered):
                proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue


def main():
    subprocess.run([PYTHON_CMD, "elnagar_service_manager.py", "stop"], cwd=BASE_DIR, check=False)
    stop_matching_processes({"laser_ops.py", "ui\\laser_ops.py", "ui/laser_ops.py"})
    time.sleep(2)
    subprocess.run([PYTHON_CMD, "elnagar_service_manager.py", "start"], cwd=BASE_DIR, check=False)
    time.sleep(3)
    subprocess.Popen([PYTHON_CMD, "laser_ops.py"], cwd=BASE_DIR)
    print("Elnagar POS restarted. Laser Ops window launched.")


if __name__ == "__main__":
    main()
