# Marwa-Bot - install the weekly backup task (Sunday 06:00) - fixed after the 2026-10-16 move
#
# The old task pointed at G:\ai\... which no longer exists (last good backup: 2026-10-11).
# This recreates NaggarPOS_WeeklyBackup with repo-relative paths, then runs it once
# immediately so the first good backup from the new location is verified on screen.
#
# Run this on EVERY node that keeps local data:
#     pwsh -File scripts\install_backup_task.ps1
#
# Remove: schtasks /Delete /TN "NaggarPOS_WeeklyBackup" /F

$ErrorActionPreference = 'Stop'

$repo    = Split-Path -Parent $PSScriptRoot
$pythonw = Join-Path $repo '.venv\Scripts\pythonw.exe'
$script  = Join-Path $repo 'scripts\backup_pos.py'
if (-not (Test-Path $pythonw)) { throw "pythonw not found: $pythonw" }
if (-not (Test-Path $script))  { throw "backup script not found: $script" }

$action = '"{0}" "{1}"' -f $pythonw, $script

Write-Host "==> creating NaggarPOS_WeeklyBackup (Sunday 06:00)"
schtasks /Create /TN "NaggarPOS_WeeklyBackup" /TR $action /SC WEEKLY /D SUN /ST 06:00 /F | Out-Host
if ($LASTEXITCODE -ne 0) { throw "create failed" }

Write-Host "==> fixing settings (battery + catch-up)"
$s = (Get-ScheduledTask -TaskName 'NaggarPOS_WeeklyBackup').Settings
$s.DisallowStartIfOnBatteries = $false
$s.StopIfGoingOnBatteries     = $false
$s.StartWhenAvailable         = $true
$s.ExecutionTimeLimit         = 'PT30M'
Set-ScheduledTask -TaskName 'NaggarPOS_WeeklyBackup' -Settings $s | Out-Null

Write-Host "==> running one backup NOW to verify"
schtasks /Run /TN "NaggarPOS_WeeklyBackup" | Out-Host
Start-Sleep -Seconds 25

Write-Host "==> backup log tail"
Get-Content (Join-Path $repo 'scripts\backup.log') -Tail 4 -ErrorAction SilentlyContinue
Write-Host "==> backup_status.json"
Get-Content (Join-Path $repo 'memory\backup_status.json') -ErrorAction SilentlyContinue
Write-Host "==> backup folder"
Get-ChildItem (Join-Path $repo 'backup') -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending | Select-Object -First 6 Name, Length | Format-Table -AutoSize