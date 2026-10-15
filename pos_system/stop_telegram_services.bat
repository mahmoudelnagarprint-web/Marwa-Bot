@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo Stopping Telegram bot and importer loop...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$targets = Get-CimInstance Win32_Process | Where-Object { $_.Name -in @('py.exe','python.exe','pythonw.exe') -and $_.CommandLine -and (($_.CommandLine -like '*telegram_bot\\bot.py*') -or ($_.CommandLine -like '*telegram_importer_loop.py*')) };" ^
  "if (-not $targets) { Write-Output 'No Telegram services are running.'; exit 0 };" ^
  "$targets | ForEach-Object { try { Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop; Write-Output ('Stopped PID ' + $_.ProcessId) } catch { Write-Output ('Failed to stop PID ' + $_.ProcessId + ': ' + $_.Exception.Message) } }"

if exist "telegram_import_now.flag" del /q "telegram_import_now.flag" >nul 2>&1
exit /b 0
