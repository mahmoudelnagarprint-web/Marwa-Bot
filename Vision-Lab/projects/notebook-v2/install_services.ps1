# Marwa-Bot v2 - install the Unified Command Center services on THIS node (standing order)
#   1) MarwaBot_NotebookV2  : web UI (:8110) + HA + (bot+proactive if leader) - keep-alive every 5 min
#   2) MarwaBot_SyncV2      : fallback tick every 5 min (outbox dedupe يمنع التكرار - آمن للتكرار)
# Keep-alive pattern from v1: every 5 min the tick restarts if dead; duplication is caught (port+lease).
#
# Usage:  powershell -ExecutionPolicy Process -File install_services.ps1
# Remove: schtasks /Delete /TN "MarwaBot_NotebookV2" /F  |  /TN "MarwaBot_SyncV2"

$ErrorActionPreference = 'Stop'

$env:PYTHONUTF8 = '1'
$repo = (Resolve-Path $PSScriptRoot).Path

# pythonw مفضّل: python venv محلي للمشروع، ثم جذري  G:\Marwa-Bot\.venv
if (Test-Path (Join-Path $repo '.venv\Scripts\pythonw.exe')) { $pyx = Join-Path $repo '.venv\Scripts\pythonw.exe' }
elseif (Test-Path 'G:\Marwa-Bot\.venv\Scripts\pythonw.exe') { $pyx = 'G:\Marwa-Bot\.venv\Scripts\pythonw.exe' }
else { $pyx = 'pythonw' }

$tasks = @(
  @{ Name = 'MarwaBot_NotebookV2'; Script = Join-Path $repo 'scripts\start_node.py';  Extra = '--port 8110' },
  @{ Name = 'MarwaBot_SyncV2';     Script = Join-Path $repo 'scripts\health_sync.py'; Extra = '--check --once-cron' }
)

foreach ($t in $tasks) {
  if (-not (Test-Path $t.Script)) { throw "script not found: $($t.Script)" }

  $action = '"{0}" "{1}" {2}' -f $pyx, $t.Script, $t.Extra
  Write-Host "==> creating $($t.Name)"
  schtasks /Create /TN $t.Name /TR "`"$action`"" /SC MINUTE /MO 5 /F | Out-Host
  if ($LASTEXITCODE -ne 0) { throw "create failed: $($t.Name)" }

  Write-Host "==> fixing settings (battery + unlimited time)"
  $s = (Get-ScheduledTask -TaskName $t.Name).Settings
  $s.DisallowStartIfOnBatteries = $false
  $s.StopIfGoingOnBatteries     = $false
  $s.StartWhenAvailable         = $true
  $s.ExecutionTimeLimit         = 'PT0S'
  Set-ScheduledTask -TaskName $t.Name -Settings $s | Out-Null

  Write-Host "==> starting $($t.Name) now"
  schtasks /Run /TN $t.Name | Out-Host
}

Start-Sleep -Seconds 14
Write-Host "==> app health"
try { (Invoke-WebRequest 'http://127.0.0.1:8110/health' -UseBasicParsing -TimeoutSec 8).Content } catch { "app not up: $_" }
Write-Host "==> running pythonw processes"
Get-CimInstance Win32_Process -Filter "Name='pythonw.exe'" | Select-Object ProcessId, CommandLine | Format-List
Write-Host "==> done. To stop: schtasks /Delete /TN MarwaBot_NotebookV2 /F  (and MarwaBot_SyncV2)"
