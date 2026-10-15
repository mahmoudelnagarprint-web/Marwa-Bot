Set WshShell = WScript.CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")

' Get Current Directory of this script
strDir = FSO.GetParentFolderName(WScript.ScriptFullName)

' Get Desktop Path
strDesktop = WshShell.SpecialFolders("Desktop")

' Create Shortcut Object
Set oShellLink = WshShell.CreateShortcut(strDesktop & "\Elnagar POS.lnk")

' Target: run_app.bat in the current folder
oShellLink.TargetPath = strDir & "\run_app.bat"

' Icon: Use a generic folder or app icon from shell32
' Icon #4 in shell32.dll is usually a Folder, #3 is a generic app doc.
' Let's use #16 (Computer) or #241 (Internet/Cloud style) if available. 
' Safer: shell32.dll, 241
oShellLink.IconLocation = "shell32.dll, 241"

' Description
oShellLink.Description = "Start Elnagar POS Application"

' Working Directory (Important for relative paths)
oShellLink.WorkingDirectory = strDir

' Save it
oShellLink.Save

MsgBox "✅ Shortcut created on Desktop! You can now drag it to your Taskbar.", 64, "Elnagar POS"
