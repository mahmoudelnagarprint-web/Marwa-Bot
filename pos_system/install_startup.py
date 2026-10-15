import os
import sys

def create_startup_bat():
    """
    Creates a .bat file in the Windows Startup folder to launch the app.
    Robust and dependency-free.
    """
    try:
        # 1. Paths
        startup_folder = os.path.join(os.getenv('APPDATA'), r'Microsoft\Windows\Start Menu\Programs\Startup')
        bat_path = os.path.join(startup_folder, "Elnagar_POS_Start.bat")
        
        python_exe = sys.executable
        pythonw_exe = python_exe.replace("python.exe", "pythonw.exe")
        if not os.path.exists(pythonw_exe): 
            pythonw_exe = python_exe
            
        script_path = os.path.abspath("backend.py")
        working_dir = os.path.dirname(script_path)
        
        # 2. Bat Content
        # "start" command ensures it runs and the bat window closes
        # /d sets working directory
        bat_content = f'@echo off\nstart "" /d "{working_dir}" "{pythonw_exe}" "{script_path}"'
        
        # 3. Write File
        with open(bat_path, "w") as f:
            f.write(bat_content)
            
        print(f"SUCCESS: Added to Startup via Batch File!")
        print(f"Location: {bat_path}")
        print(f"Content: {bat_content}")
        
    except Exception as e:
        print(f"ERROR creating startup entry: {e}")

if __name__ == "__main__":
    create_startup_bat()
