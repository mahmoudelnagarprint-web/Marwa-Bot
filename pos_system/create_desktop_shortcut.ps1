$targetPath = "$PSScriptRoot\start_elnagar_all_silent.vbs"
$shortcutPath = "$([Environment]::GetFolderPath('Desktop'))\Elnagar POS.lnk"

# Try to use an icon from assets if exists
$iconPath = "$PSScriptRoot\assets\icon.ico"

$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($shortcutPath)
$Shortcut.TargetPath = $targetPath
$Shortcut.WorkingDirectory = $PSScriptRoot
if (Test-Path $iconPath) {
    $Shortcut.IconLocation = $iconPath
}
$Shortcut.Description = "Start Elnagar POS All Services"
$Shortcut.Save()

Write-Host "Shortcut created at $shortcutPath"
