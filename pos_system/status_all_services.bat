@echo off
setlocal EnableExtensions
chcp 65001 >nul
title Elnagar POS - All Services Status
cd /d "%~dp0"

echo ============================================================
echo Elnagar POS - All Services Status
echo ============================================================
echo.

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" elnagar_service_manager.py status
) else (
    python elnagar_service_manager.py status
)

echo.
echo ============================================================
echo Firebase Importer Heartbeat:
echo ============================================================
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -c "import io,sys; sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding='utf-8',errors='replace'); from firebase_admin_client import get_db; db=get_db(); hb=db.collection('importer_heartbeats').document('main_loop').get(); print('  Status:', hb.to_dict() if hb.exists else 'Not found')"
) else (
    python -c "import io,sys; sys.stdout=io.TextIOWrapper(sys.stdout.buffer,encoding='utf-8',errors='replace'); from firebase_admin_client import get_db; db=get_db(); hb=db.collection('importer_heartbeats').document('main_loop').get(); print('  Status:', hb.to_dict() if hb.exists else 'Not found')"
)

echo.
echo ============================================================
echo Active Python processes (Elnagar):
echo ============================================================
tasklist /FI "IMAGENAME eq python.exe" /V 2>nul | findstr /I "elnagar backend bot firebase telegram" 2>nul
if errorlevel 1 (
    echo   No active Elnagar Python processes found.
)

echo.
echo ============================================================
echo Port Check:
echo ============================================================
netstat -ano | findstr ":7777 " >nul 2>&1
if %ERRORLEVEL%==0 (
    echo   Port 7777 (Backend):  IN USE
) else (
    echo   Port 7777 (Backend):  FREE
)
netstat -ano | findstr ":7788 " >nul 2>&1
if %ERRORLEVEL%==0 (
    echo   Port 7788 (Local API): IN USE
) else (
    echo   Port 7788 (Local API): FREE
)
netstat -ano | findstr ":8888 " >nul 2>&1
if %ERRORLEVEL%==0 (
    echo   Port 8888 (UI):      IN USE
) else (
    echo   Port 8888 (UI):      FREE
)

echo.
echo ============================================================
pause
