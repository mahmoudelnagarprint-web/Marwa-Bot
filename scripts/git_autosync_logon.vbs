' Marwa-Bot - run one git auto-sync at logon (hidden), owner standing order 2026-10-16.
' Source of truth: scripts\git_autosync_logon.vbs
' Installed copy lives in the user Startup folder (no admin needed).
Set sh = CreateObject("WScript.Shell")
sh.Run """G:\Marwa-Bot\.venv\Scripts\pythonw.exe"" ""G:\Marwa-Bot\scripts\git_autosync.py""", 0, False