import sys
import os

# Prevent crashes under pythonw.exe where stdout/stderr are None
if sys.stdout is None:
    try:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    except Exception:
        pass
if sys.stderr is None:
    try:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")
    except Exception:
        pass
import subprocess
import time
import json
from pathlib import Path
import psutil

# Configuration
BASE_DIR = Path(__file__).resolve().parent
RUNTIME_DIR = BASE_DIR / "runtime"
LOGS_DIR = BASE_DIR / "runtime_logs"

# Detect Python Executable - use pythonw for silent operation
VENV_PYTHON_REL = Path(".venv/Scripts/python.exe")
VENV_PYTHONW_REL = Path(".venv/Scripts/pythonw.exe")
VENV_PYTHON_ABS = BASE_DIR / ".venv" / "Scripts" / "python.exe"
VENV_PYTHONW_ABS = BASE_DIR / ".venv" / "Scripts" / "pythonw.exe"

# Use pythonw.exe for silent (no console window) execution
# Fall back to python.exe if pythonw.exe not found
if VENV_PYTHONW_ABS.exists():
    PYTHON_CMD = str(VENV_PYTHONW_REL)
elif VENV_PYTHON_ABS.exists():
    PYTHON_CMD = str(VENV_PYTHON_REL)
else:
    PYTHON_CMD = "pythonw"

SERVICES = {
    "backend": {
        "command": [PYTHON_CMD, "backend.py"],
        "cwd": BASE_DIR,
        "log_file": LOGS_DIR / "backend.log",
        "pid_file": RUNTIME_DIR / "backend.pid",
        "port_to_check": 7777 # Optional check
    },
    "telegram_bot": {
        "command": [PYTHON_CMD, "telegram_bot/bot.py"],
        "cwd": BASE_DIR,
        "log_file": LOGS_DIR / "telegram_bot.log",
        "pid_file": RUNTIME_DIR / "telegram_bot.pid"
    },
    "local_mobile_api": {
        "command": [PYTHON_CMD, "mobile_local_api_server.py"],
        "cwd": BASE_DIR,
        "log_file": LOGS_DIR / "local_mobile_api.log",
        "pid_file": RUNTIME_DIR / "local_mobile_api.pid"
    },
    "firebase_importer": {
        "command": [PYTHON_CMD, "firebase_importer_loop.py"],
        "cwd": BASE_DIR,
        "log_file": LOGS_DIR / "firebase_importer.log",
        "pid_file": RUNTIME_DIR / "firebase_importer.pid"
    }
}

def setup_dirs():
    RUNTIME_DIR.mkdir(exist_ok=True)
    LOGS_DIR.mkdir(exist_ok=True)

def is_process_running(pid):
    try:
        if pid <= 0: return False
        proc = psutil.Process(pid)
        return proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:
        return False
    except Exception:
        return False

def get_pid(service_name):
    pid_file = SERVICES[service_name]["pid_file"]
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
            if is_process_running(pid):
                return pid
        except ValueError:
            pass
    return None

def kill_process_tree(pid):
    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
        for child in children:
            child.terminate()
        _, alive = psutil.wait_procs(children, timeout=3)
        for child in alive:
            child.kill()
        parent.terminate()
        parent.wait(3)
    except psutil.NoSuchProcess:
        pass
    except Exception as e:
        print(f"Error killing process {pid}: {e}")

def stop_service(service_name):
    pid = get_pid(service_name)
    if pid:
        print(f"Stopping {service_name} (PID: {pid})...")
        kill_process_tree(pid)
        SERVICES[service_name]["pid_file"].unlink(missing_ok=True)
        print(f"{service_name} stopped.")
    else:
        print(f"{service_name} is not running.")

def stop_all():
    for name in SERVICES.keys():
        stop_service(name)
    # Fallback to kill old python processes if necessary, but we avoid blind kills here
    # We'll just rely on PID files to be safe.

def start_service(service_name):
    if get_pid(service_name):
        print(f"{service_name} is already running.")
        return

    config = SERVICES[service_name]
    print(f"Starting {service_name}...")
    
    with open(config["log_file"], "a") as log:
        import os
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONPATH"] = str(config["cwd"])
        
        creation_flags = 0
        startupinfo = None
        if sys.platform == "win32":
            # Use CREATE_NO_WINDOW to prevent any console from appearing
            creation_flags = 0x08000000  # CREATE_NO_WINDOW
            # Also use STARTUPINFO to hide any window
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0  # SW_HIDE
        
        proc = subprocess.Popen(
            config["command"],
            cwd=config["cwd"],
            stdout=log,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            creationflags=creation_flags,
            startupinfo=startupinfo,
            env=env
        )
        
    config["pid_file"].write_text(str(proc.pid))
    print(f"{service_name} started with PID {proc.pid}.")

def start_all():
    setup_dirs()
    for name in SERVICES.keys():
        start_service(name)

def restart_all():
    print("Restarting all services...")
    stop_all()
    time.sleep(2)
    start_all()

def status_all():
    print(f"{'='*40}")
    print("Elnagar POS Services Status")
    print(f"{'='*40}")
    
    for name in SERVICES.keys():
        pid = get_pid(name)
        status_str = f"RUNNING (PID: {pid})" if pid else "STOPPED"
        print(f"{name.ljust(20)}: {status_str}")
        
        # Print last 3 lines of logs if stopped or running
        log_file = SERVICES[name]["log_file"]
        if log_file.exists():
            try:
                with open(log_file, "r", encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()
                    if lines:
                        print(f"  --- Last Log Lines ---")
                        for line in lines[-3:]:
                            print(f"  {line.strip()}")
                        print("")
            except Exception as e:
                print(f"  Could not read log: {e}")
    print(f"{'='*40}")

def open_logs():
    if sys.platform == "win32":
        os.startfile(LOGS_DIR)
    print(f"Opened logs directory: {LOGS_DIR}")

def healthcheck():
    import urllib.request
    print("Running Healthcheck...")
    status_all()
    # Check if port 7777 and 8888 are responding
    backend_ok = False
    try:
        code = urllib.request.urlopen("http://127.0.0.1:7777/api/get_categories", timeout=2).getcode()
        if code == 200: backend_ok = True
    except: pass
    
    ui_ok = False
    try:
        code = urllib.request.urlopen("http://127.0.0.1:8888/", timeout=2).getcode()
        if code == 200: ui_ok = True
    except: pass
    
    print(f"Backend API (7777) Responding: {backend_ok}")
    print(f"UI Server   (8888) Responding: {ui_ok}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python elnagar_service_manager.py [start|stop|restart|status|logs|healthcheck]")
        sys.exit(1)
        
    action = sys.argv[1].lower()
    setup_dirs()
    
    with open(LOGS_DIR / "service_manager.log", "a", encoding="utf-8") as sm_log:
        sm_log.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Action: {action}\n")

    if action == "start":
        start_all()
    elif action == "stop":
        stop_all()
    elif action == "restart":
        restart_all()
    elif action == "status":
        status_all()
    elif action == "logs":
        open_logs()
    elif action == "healthcheck":
        healthcheck()
    else:
        print("Unknown action.")
