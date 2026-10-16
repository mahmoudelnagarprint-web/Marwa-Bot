# Marwa-Bot - install the periodic git auto-sync task (owner standing order 2026-10-16)
# Runs scripts\git_autosync.py every 15 minutes and at logon, as the current user,
# with pythonw.exe (no console window). No elevation required.
#
# Usage:  pwsh -File scripts\install_git_autosync_task.ps1
# Remove: schtasks /Delete /TN "MarwaBot_GitSync" /F
#         schtasks /Delete /TN "MarwaBot_GitSync_Logon" /F

$ErrorActionPreference = 'Stop'

$repo    = Split-Path -Parent $PSScriptRoot
$pythonw = Join-Path $repo '.venv\Scripts\pythonw.exe'
$script  = Join-Path $repo 'scripts\git_autosync.py'

if (-not (Test-Path $pythonw)) { throw "pythonw not found: $pythonw" }
if (-not (Test-Path $script))  { throw "sync script not found: $script" }

$action  = '"{0}" "{1}"' -f $pythonw, $script

Write-Host "==> creating MarwaBot_GitSync (every 15 minutes)"
schtasks /Create /TN "MarwaBot_GitSync" /TR $action /SC MINUTE /MO 15 /F | Out-Host
if ($LASTEXITCODE -ne 0) { throw "schtasks create (minute) failed: $LASTEXITCODE" }

Write-Host "==> creating MarwaBot_GitSync_Logon (at logon)"
schtasks /Create /TN "MarwaBot_GitSync_Logon" /TR $action /SC ONLOGON /F | Out-Host
if ($LASTEXITCODE -ne 0) { throw "schtasks create (logon) failed: $LASTEXITCODE" }

Write-Host "==> verifying"
schtasks /Query /TN "MarwaBot_GitSync" /FO LIST | Select-String 'TaskName|Status|Next Run|Schedule|Task To Run'
schtasks /Query /TN "MarwaBot_GitSync_Logon" /FO LIST | Select-String 'TaskName|Status|Next Run|Schedule|Task To Run'

Write-Host "==> running once now to verify"
schtasks /Run /TN "MarwaBot_GitSync" | Out-Host
Start-Sleep -Seconds 8
Get-Content (Join-Path $repo 'logs\git_autosync.log') -Tail 6