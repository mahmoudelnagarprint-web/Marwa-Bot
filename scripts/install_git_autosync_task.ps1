# Marwa-Bot - install the periodic git auto-sync (owner standing order 2026-10-16)
# "always pull and push from GitHub without asking, periodically"
#
# What it does:
#   1) creates scheduled task MarwaBot_GitSync (every 15 minutes, current user, pythonw = no window)
#   2) fixes laptop-hostile task defaults: without this the task stays "Queued" forever on battery
#      (DisallowStartIfOnBatteries / StopIfGoingOnBatteries)
#   3) installs a Startup-folder entry for one sync at logon (ONLOGON tasks need admin rights)
#
# Usage:  pwsh -File scripts\install_git_autosync_task.ps1
# Remove: schtasks /Delete /TN "MarwaBot_GitSync" /F
#         Remove-Item "$([Environment]::GetFolderPath('Startup'))\MarwaBot_GitSync.vbs"

$ErrorActionPreference = 'Stop'

$repo    = Split-Path -Parent $PSScriptRoot
$pythonw = Join-Path $repo '.venv\Scripts\pythonw.exe'
$script  = Join-Path $repo 'scripts\git_autosync.py'
$vbs     = Join-Path $repo 'scripts\git_autosync_logon.vbs'
$task    = 'MarwaBot_GitSync'

if (-not (Test-Path $pythonw)) { throw "pythonw not found: $pythonw" }
if (-not (Test-Path $script))  { throw "sync script not found: $script" }
if (-not (Test-Path $vbs))     { throw "logon vbs not found: $vbs" }

$action = '"{0}" "{1}"' -f $pythonw, $script

Write-Host "==> creating $task (every 15 minutes)"
schtasks /Create /TN $task /TR $action /SC MINUTE /MO 15 /F | Out-Host
if ($LASTEXITCODE -ne 0) { throw "schtasks create failed: $LASTEXITCODE" }

Write-Host "==> fixing battery/availability settings"
$s = (Get-ScheduledTask -TaskName $task).Settings
$s.DisallowStartIfOnBatteries = $false
$s.StopIfGoingOnBatteries     = $false
$s.StartWhenAvailable         = $true
$s.ExecutionTimeLimit         = 'PT10M'
Set-ScheduledTask -TaskName $task -Settings $s | Out-Null

Write-Host "==> installing logon entry in Startup folder"
$startup = [Environment]::GetFolderPath('Startup')
Copy-Item $vbs (Join-Path $startup 'MarwaBot_GitSync.vbs') -Force
Write-Host "    installed: $(Join-Path $startup 'MarwaBot_GitSync.vbs')"

Write-Host "==> verifying"
(Get-ScheduledTask -TaskName $task).Settings |
    Select-Object DisallowStartIfOnBatteries, StopIfGoingOnBatteries, StartWhenAvailable, ExecutionTimeLimit |
    Format-List | Out-Host
schtasks /Run /TN $task | Out-Host
Start-Sleep -Seconds 40
Get-Content (Join-Path $repo 'logs\git_autosync.log') -Tail 4