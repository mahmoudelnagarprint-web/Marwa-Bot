@echo off
setlocal EnableExtensions
title Elnagar Telegram Importer Loop
cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -Command "if (Get-CimInstance Win32_Process | Where-Object { $_.Name -in @('py.exe','python.exe','pythonw.exe') -and $_.CommandLine -and $_.CommandLine -like '*telegram_importer_loop.py*' }) { exit 0 } else { exit 1 }"
if %errorlevel%==0 (
    echo Telegram importer loop is already running.
    exit /b 0
)

py -3.11 telegram_importer_loop.py
set "EXIT_CODE=%errorlevel%"
echo Telegram importer loop exited with code %EXIT_CODE%.
exit /b %EXIT_CODE%
