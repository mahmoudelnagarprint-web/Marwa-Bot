Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")
strDir = FSO.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = strDir

' Define Quotes function
Function Q(s)
    Q = Chr(34) & s & Chr(34)
End Function

' Start the unified service manager
WshShell.Run Q("py") & " " & Q("-3.11") & " " & Q("elnagar_service_manager.py") & " " & Q("start"), 0, False

Set WshShell = Nothing
