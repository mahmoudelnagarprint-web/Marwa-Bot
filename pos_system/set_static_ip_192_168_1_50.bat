@echo off
:: Check for administrator permissions
fsutil dirty query %systemdrive% >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting administrative privileges to configure network adapter...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

title Elnagar POS - Fix Static Local IP (192.168.1.50)
color 0B
cls
echo ================================================================
echo          Elnagar POS - Set Static Local Server IP
echo          تثبيت عنوان الآي بي الداخلي لسيرفر المحل
echo ================================================================
echo.
echo  Checking active network adapters...
echo.

:: We will target 'Ethernet' and 'Wi-Fi'
set "ADAPTER=Ethernet"

:: Check if Ethernet adapter exists
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
echo  Configuring local IP statically to 192.168.1.50...
echo.

:: Configure Static IP, Subnet and Gateway
netsh interface ipv4 set address name="%ADAPTER%" static 192.168.1.50 255.255.255.0 192.168.1.1

:: Configure DNS
netsh interface ipv4 set dns name="%ADAPTER%" static 8.8.8.8
netsh interface ipv4 add dns name="%ADAPTER%" 1.1.1.1 index=2

echo ================================================================
echo   SUCCESS! تم تثبيت الآي بي الداخلي بنجاح
echo.
echo   - Fixed Server IP: 192.168.1.50
echo   - Local Gateway  : 192.168.1.1
echo   - Fast Google DNS: 8.8.8.8
echo.
echo   You can now permanently use: 192.168.1.50:7788 inside your app!
echo   يمكنك الآن استخدام هذا الآي بي للأبد في تطبيق الموبايل دون تغيير!
echo ================================================================
echo.
if /I not "%~1"=="SILENT" pause
