# Create Scheduled Task for Elnagar POS Auto Start
$baseDir = "g:\ai\Elnagar POS"
$vbsPath = "$baseDir\start_silent.vbs"

Write-Host "Creating Scheduled Task..."

# Delete old task if exists
schtasks /delete /tn "ElnagarPOS_AutoStart" /f 2>$null

# Register the new task
$action = New-ScheduledTaskAction -Execute "wscript.exe" -Argument "`"$vbsPath`"" -WorkingDirectory $baseDir
$trigger = New-ScheduledTaskTrigger -AtLogon
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -RunLevel Highest -LogonType Interactive
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 0)
$task = New-ScheduledTask -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description "Elnagar POS: Auto-start all services with admin privileges"

Register-ScheduledTask -TaskName "ElnagarPOS_AutoStart" -InputObject $task -Force

Write-Host "Verifying task..."
schtasks /query /tn "ElnagarPOS_AutoStart"
