@echo off
setlocal EnableExtensions
chcp 65001 >nul
title Elnagar POS - Restart All Services
cd /d "%~dp0"

echo.
echo  ╔══════════════════════════════════════════════════════════╗
echo  ║         Elnagar POS - Restarting All Services           ║
echo  ╚══════════════════════════════════════════════════════════╝
echo.

:: Stop everything first
echo  [1/2] Stopping all services...
call "%~dp0stop_app.bat" <nul

echo.
echo  [2/2] Starting all services...
timeout /t 3 /noq >nul
call "%~dp0run_app.bat"
