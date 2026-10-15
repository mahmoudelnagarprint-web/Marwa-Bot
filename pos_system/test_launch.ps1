# Test Launch
$baseDir = "g:\ai\Elnagar POS"
$python = "$baseDir\.venv\Scripts\python.exe"
$outLog = "$baseDir\test_out.log"
$errLog = "$baseDir\test_err.log"

Remove-Item $outLog -ErrorAction SilentlyContinue
Remove-Item $errLog -ErrorAction SilentlyContinue

Write-Host "Launching with Start-Process..."
Start-Process -FilePath $python -ArgumentList "mobile_local_api_server.py" -WorkingDirectory $baseDir -RedirectStandardOutput $outLog -RedirectStandardError $errLog -NoNewWindow

Start-Sleep -Seconds 3

Write-Host "Checking if process is running..."
Get-Process python -ErrorAction SilentlyContinue | Select-Object Id, ProcessName

Write-Host "Stdout content:"
if (Test-Path $outLog) { Get-Content $outLog } else { "No stdout file" }

Write-Host "Stderr content:"
if (Test-Path $errLog) { Get-Content $errLog } else { "No stderr file" }
