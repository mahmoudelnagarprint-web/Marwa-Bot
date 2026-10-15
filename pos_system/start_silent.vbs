Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")
strDir = FSO.GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = strDir

Function Q(s)
    Q = Chr(34) & s & Chr(34)
End Function

' Ensure directories exist
If Not FSO.FolderExists(strDir & "\runtime") Then
    FSO.CreateFolder strDir & "\runtime"
End If
If Not FSO.FolderExists(strDir & "\runtime_logs") Then
    FSO.CreateFolder strDir & "\runtime_logs"
End If

' ============================================================
' STEP 0: Network Setup (Static IP + Firewall Rules)
' Requires admin. Works silently via Task Scheduler (HIGHEST).
' Fails gracefully when run without admin privileges.
' ============================================================

' Set Static IP (192.168.1.50) - try Ethernet, fallback to Wi-Fi
WshShell.Run "cmd /c netsh interface ipv4 set address name=""Ethernet"" static 192.168.1.50 255.255.255.0 192.168.1.1 >nul 2>&1 || netsh interface ipv4 set address name=""Wi-Fi"" static 192.168.1.50 255.255.255.0 192.168.1.1 >nul 2>&1", 0, True
WshShell.Run "cmd /c netsh interface ipv4 set dns name=""Ethernet"" static 8.8.8.8 >nul 2>&1 & netsh interface ipv4 add dns name=""Ethernet"" 1.1.1.1 index=2 >nul 2>&1", 0, True

' Firewall Rules
WshShell.Run "cmd /c netsh advfirewall firewall delete rule name=""Elnagar POS Local API"" >nul 2>&1 & netsh advfirewall firewall add rule name=""Elnagar POS Local API"" dir=in action=allow protocol=TCP localport=7788 >nul 2>&1", 0, True
WshShell.Run "cmd /c netsh advfirewall firewall delete rule name=""Elnagar POS Backend"" >nul 2>&1 & netsh advfirewall firewall add rule name=""Elnagar POS Backend"" dir=in action=allow protocol=TCP localport=7777 >nul 2>&1", 0, True
WshShell.Run "cmd /c netsh advfirewall firewall delete rule name=""Elnagar POS UI"" >nul 2>&1 & netsh advfirewall firewall add rule name=""Elnagar POS UI"" dir=in action=allow protocol=TCP localport=8888 >nul 2>&1", 0, True

' ============================================================
' STEP 1: CLEANUP - Kill Old Processes
' ============================================================
Dim pidFiles
pidFiles = Array("runtime\local_mobile_api.pid", "runtime\telegram_bot.pid", "runtime\firebase_importer.pid", "runtime\backend.pid")
For Each pf In pidFiles
    If FSO.FileExists(strDir & "\" & pf) Then
        FSO.DeleteFile strDir & "\" & pf, True
    End If
Next
WshShell.Run "cmd /c " & Q(strDir & "\stop_app.bat") & " silent", 0, True

' Wait for ports to be freed
WScript.Sleep 3000

' ============================================================
' STEP 2: Firebase Mirror (one-time sync, blocking)
' ============================================================
Dim strPython
strPython = "pythonw"
If FSO.FileExists(strDir & "\.venv\Scripts\pythonw.exe") Then
    strPython = strDir & "\.venv\Scripts\pythonw.exe"
End If

If FSO.FileExists(strDir & "\firebase_mirror_from_pos.py") Then
    WshShell.Run Q(strPython) & " " & Q(strDir & "\firebase_mirror_from_pos.py") & " --once", 0, True
End If

' ============================================================
' STEP 3: Start ALL Services via Service Manager
' ============================================================
If FSO.FileExists(strDir & "\elnagar_service_manager.py") Then
    WshShell.Run Q(strPython) & " " & Q(strDir & "\elnagar_service_manager.py") & " start", 0, True
End If

Set WshShell = Nothing
