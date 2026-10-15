Set WshShell = WScript.CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")

' Get Current Directory
strDir = FSO.GetParentFolderName(WScript.ScriptFullName)

' Get Startup Folder Path
strStartup = WshShell.SpecialFolders("Startup")

' Create Shortcut in Startup Folder
Set oShellLink = WshShell.CreateShortcut(strStartup & "\Start_Elnagar_Sidebar.lnk")

' Target: start_sidebar_silent.vbs
oShellLink.TargetPath = strDir & "\start_sidebar_silent.vbs"

' Icon
oShellLink.IconLocation = "shell32.dll, 241"

' Description
oShellLink.Description = "Auto-Start Elnagar Sidebar"

' Working Directory
oShellLink.WorkingDirectory = strDir

' Window Style: 0 = Hidden
oShellLink.WindowStyle = 0

' Save
oShellLink.Save

MsgBox "Auto-Start Enabled Successfully! " & vbCrLf & "The sidebar will now open automatically when Windows starts.", 64, "Elnagar Sidebar"
