' Runs a .cmd file with no window and returns its exit code:  wscript.exe //B //Nologo run_hidden.vbs "C:\path\to\task.cmd"
' Same pattern the other NBA tasks already use, kept inside this project so it does not depend on another project's folder.
Set sh = CreateObject("WScript.Shell")
If WScript.Arguments.Count < 1 Then WScript.Quit 2
WScript.Quit sh.Run("cmd /c """ & WScript.Arguments(0) & """", 0, True)
