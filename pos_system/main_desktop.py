import eel
import sys
import backend # Initialize backend by importing module
import subprocess
import os
import time

if __name__ == '__main__':
    # --- START FLASK SERVER FOR EXTENSION ---
    # Run app.py in a separate process
    flask_process = None
    try:
        if os.path.exists("app.py"):
            print("Starting Flask API Server for Extension on port 5050...")
            # Use same python executable
            flask_process = subprocess.Popen([sys.executable, "app.py"], cwd=os.getcwd())
            time.sleep(2) # Give it a moment
    except Exception as e:
        print(f"Failed to start Flask Server: {e}")

    # Initialize Eel with web folder
    eel.init('web')

    # Start the app
    anti_sleep_args = [
        '--disable-backgrounding-occluded-windows', 
        '--disable-renderer-backgrounding', 
        '--disable-background-timer-throttling'
    ]
    try:
        # Try Chrome App Mode first (Independent Window)
        eel.start('index.html', size=(1280, 800), port=8000, mode='chrome', cmdline_args=anti_sleep_args)
    except (EnvironmentError, Exception):
        try:
             # Try Edge App Mode
             eel.start('index.html', size=(1280, 800), port=8000, mode='edge', cmdline_args=anti_sleep_args)
        except:
             # Fallback to default browser
             eel.start('index.html', size=(1280, 800), port=8000, mode='default')
    except (SystemExit, MemoryError, KeyboardInterrupt):
        pass
    
    # Cleanup Flask on exit
    if flask_process:
        print("Stopping Flask Server...")
        flask_process.terminate()
        flask_process.wait()
        
    # FORCE KILL SIDEBAR (Ensure it stops with the program)
    try:
        if os.name == 'nt':
            os.system('taskkill /F /IM "python.exe" /FI "WINDOWTITLE eq Elnagar_Sidebar*" >nul 2>&1')
            os.system('taskkill /F /IM "pythonw.exe" /FI "WINDOWTITLE eq Elnagar_Sidebar*" >nul 2>&1')
            # Fallback based on CLI arg if title isn't set yet
            os.system('wmic process where "commandline like \'%desktop_sidebar%\'" call terminate >nul 2>&1')
    except:
        pass
    
    sys.exit(0)
