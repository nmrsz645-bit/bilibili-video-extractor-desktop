' 无控制台启动桌面程序；调用 Start-Dev.cmd 以便保留统一的环境检查逻辑。
Option Explicit
Dim shell, folder, command
Set shell = CreateObject("WScript.Shell")
folder = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
command = Chr(34) & folder & "\Start-Dev.cmd" & Chr(34)
shell.Run command, 0, False
