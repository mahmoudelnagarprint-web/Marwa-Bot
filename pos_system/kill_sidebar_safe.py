import os
import subprocess
import time

def kill_sidebar():
    print("Searching for sidebar process...")
    try:
        # Get list of processes with command lines
        # wmic process get processid,commandline /format:csv
        
        cmd = 'wmic process get processid,commandline /format:csv'
        output = subprocess.check_output(cmd, shell=True).decode('utf-8', errors='ignore')
        
        lines = output.splitlines()
        killed = False
        for line in lines:
            if 'desktop_sidebar' in line and 'python' in line:
                parts = line.split(',')
                if len(parts) >= 2:
                    # PID is usually at the end or near it depending on format, CSV includes Node,CommandLine,ProcessId
                    # Node,CommandLine,ProcessId
                    # MYPC,"python desktop_sidebar.py",1234
                    
                    # Robust CSV parsing is hard with just split, but let's try to grab PID from end
                    pid_str = parts[-1].strip()
                    if pid_str.isdigit():
                        pid = int(pid_str)
                        if pid != os.getpid():
                            print(f"killing PID {pid} : {line.strip()[:50]}...")
                            os.system(f"taskkill /F /PID {pid}")
                            killed = True
                            
        if not killed:
            print("No sidebar process found running.")
        else:
            print("Sidebar process terminated.")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    kill_sidebar()
