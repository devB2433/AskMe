@echo off
chcp 65001 >nul
echo ==========================================
echo       AskMe 知识库系统启动脚本
echo ==========================================
echo.

REM 设置工作目录
set "PROJECT_DIR=C:\Data\projects\AskMe"
set "BACKEND_DIR=%PROJECT_DIR%\backend"
set "FRONTEND_DIR=%PROJECT_DIR%\frontend"
set "VENV_PYTHON=%PROJECT_DIR%\venv\Scripts\python.exe"

echo [1/4] 停止现有进程...
taskkill /f /im python.exe 2>nul
taskkill /f /im node.exe 2>nul
timeout /t 2 /nobreak >nul
echo      完成
echo.

echo [2/4] 检查 Docker 容器...
cd /d "%PROJECT_DIR%"
docker-compose ps | findstr "Up" >nul
if errorlevel 1 (
    echo      启动 Docker 容器...
    docker-compose up -d
    timeout /t 5 /nobreak >nul
) else (
    echo      Docker 容器已运行
)
echo.

echo [3/4] 启动后端服务...
cd /d "%BACKEND_DIR%"
start "AskMe Backend" cmd /k "%VENV_PYTHON% -m uvicorn main:app --host 0.0.0.0 --port 8001"
echo      后端启动中，请等待...
timeout /t 3 /nobreak >nul
echo.

echo [4/4] 启动前端服务...
cd /d "%FRONTEND_DIR%"
start "AskMe Frontend" cmd /k "npm run dev"
echo      前端启动中，请等待...
timeout /t 3 /nobreak >nul
echo.

echo ==========================================
echo       所有服务已启动
echo ==========================================
echo.
echo 前端地址: http://localhost:5173
echo 后端地址: http://localhost:8001
echo.
echo 按任意键关闭此窗口（服务将继续运行）...
pause >nul
