' bettype_auto_hidden.vbs
' Task Scheduler: run bettype_auto.bat live without showing a DOS window
'
' Usage (task action):
'   C:\KEIBA-CICD\_keiba\keiba-cicd-core\keiba-v2\scripts\bettype_auto_hidden.vbs

Set fso = CreateObject("Scripting.FileSystemObject")
folder = fso.GetParentFolderName(WScript.ScriptFullName)
batPath = fso.BuildPath(folder, "bettype_auto.bat")

Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = folder

' Arg 0=hidden, True=wait for completion (same as direct .bat from Task Scheduler)
WshShell.Run "cmd /c """ & batPath & """ live", 0, True
