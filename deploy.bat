@echo off
chcp 65001 >nul
echo =========================================
echo   谁是卧底 - 一键部署脚本 (Windows)
echo =========================================

REM 1. Install Python dependencies
echo.
echo [1/4] 安装 Python 依赖...
cd python
pip install -r requirements.txt
cd ..

REM 2. Build frontend
echo.
echo [2/4] 构建前端...
cd web
call npm install
call npm run build
cd ..

REM 3. Verify
if not exist "python\static\index.html" (
    echo 错误: 前端构建失败，python\static\index.html 不存在
    exit /b 1
)

echo.
echo [3/4] 构建完成，静态文件已输出到 python\static\

REM 4. Start server
echo.
echo [4/4] 启动服务器...
echo   访问地址: http://localhost:8000
echo   按 Ctrl+C 停止
echo.
cd python
uvicorn app.main:app --host 0.0.0.0 --port 8000
