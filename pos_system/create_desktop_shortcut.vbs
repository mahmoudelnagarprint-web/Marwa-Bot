Set WshShell = WScript.CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")

' Get Current Directory (where THIS script lives)
strDir = FSO.GetParentFolderName(WScript.ScriptFullName)

' Get Desktop Path
strDesktop = WshShell.SpecialFolders("Desktop")

' Create Shortcut Object
Set oShellLink = WshShell.CreateShortcut(strDesktop & "\Ramadan ERP.lnk")

' Target: start_silent.vbs (runs everything silently without any CMD windows)
oShellLink.TargetPath = strDir & "\start_silent.vbs"

' Icon: Use a nice icon (cloud/globe = 241)
oShellLink.IconLocation = "shell32.dll, 241"

' Description
oShellLink.Description = "Start Ramadan ERP (Silent Mode)"

' Working Directory
oShellLink.WorkingDirectory = strDir

' Window Style: 0 = Hidden (no window pops up at all)
oShellLink.WindowStyle = 0

' Save it
oShellLink.Save

MsgBox "Desktop Shortcut Created Successfully! " & vbCrLf & "You can now launch the ERP from your desktop.", 64, "Ramadan ERP"
