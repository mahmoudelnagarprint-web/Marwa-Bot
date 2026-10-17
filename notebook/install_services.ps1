# Marwa-Bot - install the Smart Notebook services (owner standing order 2026-10-16)
#   1) MarwaBot_Notebook        : web UI  (http://127.0.0.1:8100 + LAN)  - long running
#   2) MarwaBot_NotebookBridge  : telegram receive + reminders loop    - long running
#
# Both run every 5 minutes as a keep-alive: if already running the new copy
# exits immediately (single-instance checks), if dead the tick restarts it.
# ExecutionTimeLimit = PT0S (unlimited) so the daemons are never killed.
#
# IMPORTANT: tasks launch with CWD = System32, so we call the SCRIPT FILES by
# absolute path (both scripts bootstrap their own sys.path) - never use -m here.
#
# Usage:   pwsh -File notebook\install_services.ps1
# Remove:  schtasks /Delete /TN "MarwaBot_Notebook" /F
#          schtasks /Delete /TN "MarwaBot_NotebookBridge" /F

$ErrorActionPreference = 'Stop'

$repo    = Split-Path -Parent $PSScriptRoot
$pythonw = Join-Path $repo '.venv\Scripts\pythonw.exe'
if (-not (Test-Path $pythonw)) { throw "pythonw not found: $pythonw" }

$tasks = @(
  @{ Name = 'MarwaBot_Notebook';       Script = Join-Path $repo 'notebook\app.py';              Extra = '--port 8100' },
  @{ Name = 'MarwaBot_NotebookBridge'; Script = Join-Path $repo 'notebook\telegram_bridge.py';  Extra = '--watch' },
  @{ Name = 'MarwaBot_NotebookMorning'; Script = Join-Path $repo 'notebook\automation.py';     Extra = '--morning' },
  @{ Name = 'MarwaBot_NotebookEvening'; Script = Join-Path $repo 'notebook\automation.py';     Extra = '--evening' },
  @{ Name = 'MarwaBot_NotebookCycle';  Script = Join-Path $repo 'notebook\automation.py';     Extra = '--cycle' }
)

foreach ($t in $tasks) {
  if (-not (Test-Path $t.Script)) { throw "script not found: $($t.Script)" }
  $action = '"{0}" "{1}" {2}' -f $pythonw, $t.Script, $t.Extra
  Write-Host "==> creating $($t.Name)"
  Write-Host "    action: $action"
  schtasks /Create /TN $t.Name /TR $action /SC MINUTE /MO 5 /F | Out-Host
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

Start-Sleep -Seconds 12
Write-Host "==> app health"
try { (Invoke-WebRequest 'http://127.0.0.1:8100/health' -UseBasicParsing -TimeoutSec 8).Content } catch { "app not up: $_" }
Write-Host "==> processes"
Get-CimInstance Win32_Process -Filter "Name='pythonw.exe'" | Select-Object ProcessId, CommandLine | Format-List