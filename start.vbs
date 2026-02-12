' AskMe 知识库系统启动脚本（无窗口版）
Option Explicit

Dim WshShell, fso, projectDir, backendDir, frontendDir, venvPython
Dim dockerRunning, result

Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

projectDir = "C:\Data\projects\AskMe"
backendDir = projectDir & "\backend"
frontendDir = projectDir & "\frontend"
venvPython = projectDir & "\venv\Scripts\python.exe"

' 停止现有进程
WshShell.Run "taskkill /f /im python.exe", 0, True
WshShell.Run "taskkill /f /im node.exe", 0, True
WScript.Sleep 2000

' 检查 Docker 容器
dockerRunning = False
result = WshShell.Run("cmd /c docker-compose ps | findstr ""Up""", 0, True)
If result <> 0 Then
    ' 启动 Docker 容器
    WshShell.CurrentDirectory = projectDir
    WshShell.Run "docker-compose up -d", 0, True
    WScript.Sleep 5000
End If

' 启动后端服务（隐藏窗口）
WshShell.CurrentDirectory = backendDir
WshShell.Run "cmd /c """ & venvPython & """ -m uvicorn main:app --host 0.0.0.0 --port 8001""", 0, False
WScript.Sleep 3000

' 启动前端服务（隐藏窗口）
WshShell.CurrentDirectory = frontendDir
WshShell.Run "cmd /c npm run dev", 0, False
WScript.Sleep 3000

' 显示启动成功提示
MsgBox "AskMe 知识库系统已启动！" & vbCrLf & vbCrLf & _
       "前端地址: http://localhost:5173" & vbCrLf & _
       "后端地址: http://localhost:8001", _
       vbInformation, "AskMe 启动成功"

Set WshShell = Nothing
Set fso = Nothing
