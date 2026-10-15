@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul
title Elnagar POS - Stop All Services
cd /d "%~dp0"

echo.
echo ============================================================
echo   Elnagar POS - Stopping All Services
echo ============================================================
echo.

REM --- Detect Python ---
set "PYTHON=python"
if exist ".venv\Scripts\python.exe" set "PYTHON=%~dp0.venv\Scripts\python.exe"

REM --- Method 1: Use service manager to stop cleanly ---
echo   [1/3] Stopping via Service Manager...
if exist "elnagar_service_manager.py" (
    "%PYTHON%" elnagar_service_manager.py stop 2>nul
)

REM --- Method 2: Kill by PID files ---
echo   [2/3] Cleaning up PID files...
for %%S in (local_mobile_api telegram_bot firebase_importer backend) do (
    if exist "runtime\%%S.pid" (
        set /p OLD_PID=<"runtime\%%S.pid"
        taskkill /F /PID !OLD_PID! >nul 2>&1
        del "runtime\%%S.pid" >nul 2>&1
    )
)

REM --- Method 2b: Kill orphan processes by command line (fix 2026-10-12: old
REM     boots left duplicate telegram bots (Conflict), firebase importers and
REM     sidebars running because PID files only knew the newest PID) ---
echo   [2b/3] Killing leftover orphan processes...
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='pythonw.exe' OR Name='python.exe'\" | Where-Object { $_.CommandLine -and ($_.CommandLine -match 'Elnagar POS|backend\.py|telegram_bot|firebase_importer_loop\.py|mobile_local_api_server\.py|desktop_sidebar\.py') } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >nul 2>&1

REM --- Method 3: Kill by port (final safety net) ---
echo   [3/3] Freeing ports...
call :kill_port 7777
call :kill_port 7788
call :kill_port 8888

REM Clean sidebar lock
if exist "%TEMP%\elnagar_sidebar.lock" del "%TEMP%\elnagar_sidebar.lock" >nul 2>&1

echo.
echo   [OK] All Elnagar POS services stopped.
echo.
if /i not "%~1"=="silent" pause
goto :eof

:kill_port
set "PORT=%1"
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":%PORT% " ^| findstr "LISTENING"') do (
    if not "%%a"=="0" (
        taskkill /F /PID %%a >nul 2>&1
    )
)
goto :eof
