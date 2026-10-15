Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")

' Get Current Directory
strDir = FSO.GetParentFolderName(WScript.ScriptFullName)

' Command to run Python script silently
' Using pythonw.exe prevents the console window
strCmd = "pythonw """ & strDir & "\desktop_sidebar.py"""

' Run
WshShell.Run strCmd, 0, False
