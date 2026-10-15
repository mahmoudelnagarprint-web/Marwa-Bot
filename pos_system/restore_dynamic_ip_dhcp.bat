@echo off
:: Check for administrator permissions
fsutil dirty query %systemdrive% >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting administrative privileges to restore network adapter...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

title Elnagar POS - Restore Automatic DHCP IP
color 0E
cls
echo ================================================================
echo          Elnagar POS - Restore Dynamic IP (DHCP)
echo          إعادة تشغيل المزامنة التلقائية والآي بي التلقائي
echo ================================================================
echo.
echo  Checking active network adapters...
echo.

set "ADAPTER=Ethernet"

netsh interface show interface name="%ADAPTER%" >nul 2>&1
if %errorlevel% neq 0 (
    set "ADAPTER=Wi-Fi"
)

:: Double check if neither exists
netsh interface show interface name="%ADAPTER%" >nul 2>&1
if %errorlevel% neq 0 (
    echo  [!] Error: Active adapter 'Ethernet' or 'Wi-Fi' not found.
    echo  [!] خطأ: لم يتم العثور على بطاقة الشبكة النشطة.
    pause
    exit /b
)

echo  Found network interface: "%ADAPTER%"
echo  Restoring to automatic dynamic IP configuration (DHCP)...
echo.

:: Reset IP and DNS to DHCP
netsh interface ipv4 set address name="%ADAPTER%" source=dhcp
netsh interface ipv4 set dns name="%ADAPTER%" source=dhcp

echo ================================================================
echo   SUCCESS! تم إعادة التهيئة التلقائية (DHCP) بنجاح
echo.
echo   - Network interface "%ADAPTER%" is now set to Automatic.
echo   - Your router will assign the IP dynamically.
echo ================================================================
echo.
pause
