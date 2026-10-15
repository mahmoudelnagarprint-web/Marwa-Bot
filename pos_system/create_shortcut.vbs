
        Set oWS = WScript.CreateObject("WScript.Shell")
        sLinkFile = "C:\Users\MASSAYA\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup\Elnagar POS.lnk"
        Set oLink = oWS.CreateShortcut(sLinkFile)
        oLink.TargetPath = "C:\Python314\pythonw.exe"
        oLink.Arguments = ""G:\ai\Elnagar POS\backend.py""
        oLink.WorkingDirectory = "G:\ai\Elnagar POS"
        oLink.Description = "Elnagar POS System"
        oLink.IconLocation = "C:\Python314\python.exe, 0"
        oLink.Save
        