Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")

' Get paths
scriptDir = FSO.GetParentFolderName(WScript.ScriptFullName)
desktopPath = WshShell.SpecialFolders("Desktop")
shortcutPath = desktopPath & "\FinAI.lnk"

' Create shortcut
Set shortcut = WshShell.CreateShortcut(shortcutPath)
shortcut.TargetPath = scriptDir & "\venv2\Scripts\pythonw.exe"
shortcut.Arguments = "desktop_app.py"
shortcut.WorkingDirectory = scriptDir
shortcut.Description = "FinAI - Financial Intelligence OS"
shortcut.WindowStyle = 7  ' Minimized
shortcut.Save

MsgBox "Desktop shortcut 'FinAI' created successfully!" & vbCrLf & vbCrLf & "You can now launch FinAI from your desktop.", vbInformation, "FinAI Setup"
