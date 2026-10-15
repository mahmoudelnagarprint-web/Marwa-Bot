@echo off
:: Check for administrator permissions
fsutil dirty query %systemdrive% >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting administrative privileges...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

setlocal EnableExtensions
cd /d "%~dp0"

REM ============================================================
REM   Elnagar POS - Full Launch (All Services)
REM   يشغل البرنامج بجميع خدماته:
REM   - Static IP Setup (192.168.1.50)
REM   - Firewall Rules (ports 7777, 7788, 8888)
REM   - Local Mobile API Server (port 7788)
REM   - Telegram Bot
REM   - Firebase Importer
REM   - Desktop UI Backend (port 7777 + 8888)
REM ============================================================

echo [INFO] Configuring Static IP for Mobile App Sync...
call "%~dp0set_static_ip_192_168_1_50.bat" SILENT

if exist "start_silent.vbs" (
    echo [INFO] Starting all servers silently...
    start "" wscript.exe "start_silent.vbs"
) else (
    echo [ERROR] start_silent.vbs not found!
    pause
)
exit
