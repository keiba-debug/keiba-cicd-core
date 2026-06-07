' vb_refresh_auto_hidden.vbs
' タスクスケジューラ用: ウインドウを表示せずに vb_refresh_auto.bat を実行
'
' 使い方:
'   "C:\KEIBA-CICD\_keiba\keiba-cicd-core\keiba-v2\scripts\vb_refresh_auto_hidden.vbs"

Set fso = CreateObject("Scripting.FileSystemObject")
folder = fso.GetParentFolderName(WScript.ScriptFullName)
batPath = fso.BuildPath(folder, "vb_refresh_auto.bat")

Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = folder

WshShell.Run "cmd /c """ & batPath & """", 0, True
