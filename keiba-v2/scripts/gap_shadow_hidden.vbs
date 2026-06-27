' Hidden launcher for gap_shadow_auto.bat (Session 175 / paper shadow sleeve)
' Runs the bat with window hidden (0) so the 5-min log task does not steal
' foreground focus while you use the PC. Arg = mode (log / settle / report).
Set sh = CreateObject("WScript.Shell")
mode = "log"
If WScript.Arguments.Count > 0 Then mode = WScript.Arguments(0)
bat = "C:\KEIBA-CICD\_keiba\keiba-cicd-core\keiba-v2\scripts\gap_shadow_auto.bat"
sh.Run "cmd /c """"" & bat & """ " & mode & """", 0, False
