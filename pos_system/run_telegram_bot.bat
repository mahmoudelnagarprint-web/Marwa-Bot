@echo off
setlocal EnableExtensions
title Elnagar Telegram Bot
cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -Command "if (Get-CimInstance Win32_Process | Where-Object { $_.Name -in @('py.exe','python.exe','pythonw.exe') -and $_.CommandLine -and $_.CommandLine -like '*telegram_bot\\bot.py*' }) { exit 0 } else { exit 1 }"
if %errorlevel%==0 (
    echo Telegram Bot is already running.
    exit /b 0
)

py -3.11 telegram_bot\bot.py
set "EXIT_CODE=%errorlevel%"
echo Telegram Bot exited with code %EXIT_CODE%.
exit /b %EXIT_CODE%
