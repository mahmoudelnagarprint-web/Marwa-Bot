$wshell = New-Object -ComObject WScript.Shell
$desktop = [Environment]::GetFolderPath("Desktop")
$shortcut = $wshell.CreateShortcut("$desktop\Elnagar POS.lnk")
$shortcut.TargetPath = "g:\ai\Elnagar POS\run_app.bat"
$shortcut.WorkingDirectory = "g:\ai\Elnagar POS"
$shortcut.Description = "Run Elnagar POS Services"
$shortcut.Save()
