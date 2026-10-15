@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo === Elnagar POS Service Status ===
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$checks = @(" ^
  "  @{ Name = 'Backend'; Pattern = '*backend.py*' }," ^
  "  @{ Name = 'Telegram Bot'; Pattern = '*telegram_bot\\bot.py*' }," ^
  "  @{ Name = 'Telegram Importer Loop'; Pattern = '*telegram_importer_loop.py*' }" ^
  ");" ^
  "foreach ($check in $checks) {" ^
  "  $proc = Get-CimInstance Win32_Process | Where-Object { $_.Name -in @('py.exe','python.exe','pythonw.exe','wscript.exe') -and $_.CommandLine -and $_.CommandLine -like $check.Pattern } | Select-Object -First 1;" ^
  "  if ($proc) { Write-Output ($check.Name + ': RUNNING | PID=' + $proc.ProcessId) } else { Write-Output ($check.Name + ': STOPPED') }" ^
  "}"

if exist "telegram_import_now.flag" (
    echo Import flag: PRESENT
) else (
    echo Import flag: not present
)
exit /b 0
