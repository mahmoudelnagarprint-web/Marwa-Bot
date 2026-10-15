@echo off
title Elnagar POS - Repairing System...
cd /d "%~dp0"

echo ==========================================
echo 🔧 Repairing Elnagar POS Environment...
echo ==========================================

:: 1. Check if .venv exists, if not create it
if not exist ".venv" (
    echo [INFO] Creating virtual environment...
    python -m venv .venv
)

:: 2. Install Dependencies
echo [INFO] Installing libraries (This may take a minute)...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt

echo.
echo ==========================================
echo ✅ Repair Complete!
echo ==========================================
echo You can now try running 'run_app.bat' again.
echo.
pause
