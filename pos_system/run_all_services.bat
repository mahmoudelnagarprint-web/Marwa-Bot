@echo off
setlocal EnableExtensions
cd /d "%~dp0"
:: Alias for run_app.bat
call "%~dp0run_app.bat"
exit /b %errorlevel%
