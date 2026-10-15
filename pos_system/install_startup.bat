@echo off
:: ============================================================
:: Check for administrator permissions (REQUIRED)
:: ============================================================
fsutil dirty query %systemdrive% >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting administrative privileges...
    powershell -Command "Start-Process cmd.exe -ArgumentList '/c \"%~f0\"' -Verb RunAs"
    exit /b
)

setlocal EnableExtensions
chcp 65001 >nul
title Elnagar POS - Full System Setup + Auto Startup
cd /d "%~dp0"

echo.
echo  ================================================================
echo     Elnagar POS - Full System Setup + Auto Startup Installer
echo     اعداد كامل للنظام + تشغيل تلقائي عند فتح الويندوز
echo  ================================================================
echo.

set "VBS_TARGET=%~dp0start_silent.vbs"
set "PYTHON=python"
if exist ".venv\Scripts\python.exe" set "PYTHON=%~dp0.venv\Scripts\python.exe"

if not exist "%VBS_TARGET%" (
    echo   [ERROR] start_silent.vbs not found!
    pause
    exit /b 1
)

:: ============================================================
:: STEP 1: Set Static IP (192.168.1.50)
:: ============================================================
echo   [1/4] Setting Static IP to 192.168.1.50...
echo.

set "ADAPTER=Ethernet"
netsh interface show interface name="%ADAPTER%" >nul 2>&1
if %errorlevel% neq 0 (
    set "ADAPTER=Wi-Fi"
)

netsh interface ipv4 set address name="%ADAPTER%" static 192.168.1.50 255.255.255.0 192.168.1.1
netsh interface ipv4 set dns name="%ADAPTER%" static 8.8.8.8
netsh interface ipv4 add dns name="%ADAPTER%" 1.1.1.1 index=2

echo   [OK] Static IP 192.168.1.50 configured!
echo   [OK] DNS: 8.8.8.8 + 1.1.1.1
echo.

:: ============================================================
:: STEP 2: Add Firewall Rules
:: ============================================================
echo   [2/4] Adding Firewall Rules...

netsh advfirewall firewall delete rule name="Elnagar POS Local API" >nul 2>&1
netsh advfirewall firewall add rule name="Elnagar POS Local API" dir=in action=allow protocol=TCP localport=7788 >nul 2>&1
echo   [OK] Port 7788 (Mobile API) opened

netsh advfirewall firewall delete rule name="Elnagar POS Backend" >nul 2>&1
netsh advfirewall firewall add rule name="Elnagar POS Backend" dir=in action=allow protocol=TCP localport=7777 >nul 2>&1
echo   [OK] Port 7777 (Backend) opened

netsh advfirewall firewall delete rule name="Elnagar POS UI" >nul 2>&1
netsh advfirewall firewall add rule name="Elnagar POS UI" dir=in action=allow protocol=TCP localport=8888 >nul 2>&1
echo   [OK] Port 8888 (UI) opened
echo.

:: ============================================================
:: STEP 3: Remove old Startup shortcut (if exists)
:: ============================================================
set "STARTUP_FOLDER=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "OLD_SHORTCUT=%STARTUP_FOLDER%\Elnagar_POS_Silent_Startup.lnk"
if exist "%OLD_SHORTCUT%" (
    del "%OLD_SHORTCUT%" >nul 2>&1
    echo   [OK] Removed old startup shortcut
)

:: ============================================================
:: STEP 4: Create Task Scheduler Task (runs as ADMIN at logon)
:: ============================================================
echo   [3/4] Creating Windows Scheduled Task for auto-start...

schtasks /delete /tn "ElnagarPOS_AutoStart" /f >nul 2>&1

:: Use PowerShell for reliable task creation with proper quoting
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$action = New-ScheduledTaskAction -Execute 'wscript.exe' -Argument ('\"' + '%VBS_TARGET%' + '\"') -WorkingDirectory '%~dp0'; " ^
  "$trigger = New-ScheduledTaskTrigger -AtLogon; " ^
  "$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -RunLevel Highest -LogonType Interactive; " ^
  "$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 0); " ^
  "$task = New-ScheduledTask -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description 'Elnagar POS: Auto-start all services with admin privileges'; " ^
  "Register-ScheduledTask -TaskName 'ElnagarPOS_AutoStart' -InputObject $task -Force"

if %errorlevel%==0 (
    echo   [OK] Auto-start task created successfully!
    echo   [OK] Task Name: ElnagarPOS_AutoStart
) else (
    echo   [!] Task Scheduler failed. Creating Startup folder shortcut instead...
    powershell -Command "$wshell = New-Object -ComObject WScript.Shell; $sc = $wshell.CreateShortcut('%OLD_SHORTCUT%'); $sc.TargetPath = '%VBS_TARGET%'; $sc.WorkingDirectory = '%~dp0'; $sc.Description = 'Elnagar POS Auto Start'; $sc.Save()"
    if exist "%OLD_SHORTCUT%" (
        echo   [OK] Startup shortcut created as fallback
    )
)
echo.

:: ============================================================
:: STEP 5: Start all services NOW
:: ============================================================
echo   [4/4] Starting all Elnagar POS services now...

call "%~dp0stop_app.bat" silent >nul 2>&1
timeout /t 2 /noq >nul
start "" wscript.exe "%VBS_TARGET%"

echo.
echo  ================================================================
echo     SETUP COMPLETE! - تم الاعداد بنجاح
echo  ================================================================
echo.
echo   [OK] Static IP:   192.168.1.50
echo   [OK] Firewall:    Ports 7777, 7788, 8888 opened
echo   [OK] Auto-Start:  Enabled at Windows boot (with admin)
echo   [OK] Services:    Starting now...
echo.
echo   Mobile App:   http://192.168.1.50:7788
echo   Backend API:  http://192.168.1.50:7777
echo   Desktop UI:   http://localhost:8888
echo.
echo   البرنامج سيعمل تلقائيا مع كل تشغيل للويندوز
echo   بصلاحيات المسؤول وبدون اي نوافذ منبثقة
echo  ================================================================
echo.
pause
