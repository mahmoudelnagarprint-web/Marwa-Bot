import psutil
import os
import signal
import time

def kill_process_on_port(port):
    """Finds and kills any process listening on the specified port."""
    print(f"Checking port {port}...")
    killed = False
    for proc in psutil.process_iter(['pid', 'name', 'connections']):
        try:
            for conn in proc.connections(kind='inet'):
                if conn.laddr.port == port:
                    print(f" - Found process {proc.info['name']} (PID: {proc.info['pid']}) using port {port}. Killing...")
                    try:
                        os.kill(proc.info['pid'], signal.SIGTERM)
                        killed = True
                    except Exception as e:
                        print(f"   Failed to kill {proc.info['pid']}: {e}")
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    
    if not killed:
        print(f" - Port {port} is free.")
    else:
        time.sleep(1) # Wait for cleanup

if __name__ == "__main__":
    print("--- Port Cleanup Tool ---")
    kill_process_on_port(7777) # Flask API
    kill_process_on_port(8888) # Eel / Live Server
    print("--- Cleanup Complete ---")
