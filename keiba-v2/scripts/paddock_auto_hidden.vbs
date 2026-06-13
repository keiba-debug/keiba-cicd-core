' paddock_auto_hidden.vbs
' Task Scheduler wrapper: run paddock_auto.bat without a visible window

Set fso = CreateObject("Scripting.FileSystemObject")
folder = fso.GetParentFolderName(WScript.ScriptFullName)
batPath = fso.BuildPath(folder, "paddock_auto.bat")

Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = folder

WshShell.Run "cmd /c """ & batPath & """", 0, True
