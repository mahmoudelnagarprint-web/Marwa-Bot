# Marwa-Bot v2 - install the Unified Command Center services on THIS node (standing order)
#   1) MarwaBot_NotebookV2  : web UI (:8110) + HA + (bot+proactive if leader) - keep-alive every 5 min
#   2) MarwaBot_SyncV2      : fallback tick every 5 min (outbox dedupe يمنع التكرار - آمن للتكرار)
# Keep-alive pattern from v1: every 5 min the tick restarts if dead; duplication is caught (port+lease).
#
# 2026-10-20: من الليد — استبدل schtasks /Create /TR (بيتكسر على مسافات «Naggar Print» في quoting)
# بـ Register-ScheduledTask native. ثبت بالاختبار: LastResult=0 + حارس النسخة الواحدة بيكتب
# «المنفذ 8110 مشغول — نسخة v2 شغّالة … خروج صادق» في لوج العقدة لما المهمة تضرب والعقدة قايمة.
#
# Usage:  powershell -ExecutionPolicy Bypass -File install_services.ps1
# Remove: Unregister-ScheduledTask -TaskName MarwaBot_NotebookV2 -Confirm:$false  (و MarwaBot_SyncV2)

$ErrorActionPreference = 'Stop'

$env:PYTHONUTF8 = '1'
$repo = (Resolve-Path $PSScriptRoot).Path

# pythonw مفضّل: python venv محلي للمشروع، ثم جذري  G:\Marwa-Bot\.venv
if (Test-Path (Join-Path $repo '.venv\Scripts\pythonw.exe')) { $pyx = Join-Path $repo '.venv\Scripts\pythonw.exe' }
elseif (Test-Path 'G:\Marwa-Bot\.venv\Scripts\pythonw.exe') { $pyx = 'G:\Marwa-Bot\.venv\Scripts\pythonw.exe' }
else { $pyx = 'pythonw' }

$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
  -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero)

$tasks = @(
  @{ Name = 'MarwaBot_NotebookV2'; Script = Join-Path $repo 'scripts\start_node.py';  Extra = '--port 8110' },
  @{ Name = 'MarwaBot_SyncV2';     Script = Join-Path $repo 'scripts\health_sync.py'; Extra = '--check --once-cron' }
)

foreach ($t in $tasks) {
  if (-not (Test-Path $t.Script)) { throw "script not found: $($t.Script)" }

  # المسار بين اقتباس مزدوج + الباقي raw — Register-ScheduledTask يمرر الـArguments كما هي بلا escaping hell
  $arg = '"{0}" {1}' -f $t.Script, $t.Extra
  $action = New-ScheduledTaskAction -Execute $pyx -Argument $arg
  $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(2) -RepetitionInterval (New-TimeSpan -Minutes 5)

  Write-Host "==> registering $($t.Name)"
  Register-ScheduledTask -TaskName $t.Name -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null

  Write-Host "==> starting $($t.Name) now"
  Start-ScheduledTask -TaskName $t.Name
}

Start-Sleep -Seconds 14
Write-Host "==> task state"
Get-ScheduledTask -TaskName 'MarwaBot_NotebookV2','MarwaBot_SyncV2' | ForEach-Object {
  $i = $_ | Get-ScheduledTaskInfo
  "{0}: state={1} LastResult={2} LastRun={3}" -f $_.TaskName, $_.State, $i.LastTaskResult, $i.LastRunTime
}
Write-Host "==> app health"
try { (Invoke-WebRequest 'http://127.0.0.1:8110/health' -UseBasicParsing -TimeoutSec 8).Content } catch { "app not up: $_" }
Write-Host "==> running pythonw processes"
Get-CimInstance Win32_Process -Filter "Name='pythonw.exe'" | Select-Object ProcessId, CommandLine | Format-List
Write-Host "==> done. To stop: Unregister-ScheduledTask -TaskName MarwaBot_NotebookV2 -Confirm:`$false  (and MarwaBot_SyncV2)"
