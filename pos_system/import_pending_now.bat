@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo import-now>"telegram_import_now.flag"
echo Trigger flag created: %cd%\telegram_import_now.flag
exit /b 0
