@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" elnagar_service_manager.py restart
) else (
    python elnagar_service_manager.py restart
)
