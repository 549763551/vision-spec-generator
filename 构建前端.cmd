@echo off
chcp 65001 >nul
cd /d "%~dp0ui"
if not exist node_modules (
  echo 首次运行，正在安装依赖...
  call npm install
)
call npm run build
echo.
echo 构建完成，产物在 ui\dist
pause
