@echo off
chcp 65001 >nul
title AV Agent 一键打包
echo ==========================================
echo   AV Agent 一键打包脚本（Windows）
echo ==========================================
echo.

echo [1/3] 安装依赖...
pip install -r requirements.txt || goto :error
pip install pyinstaller || goto :error

echo.
echo [2/3] 开始打包（约需 2-5 分钟）...
pyinstaller --clean --noconfirm av-agent.spec || goto :error

echo.
echo [3/3] 打包完成！
echo ------------------------------------------
echo   输出文件：dist\AVAgent.exe
echo   使用方法：把 AVAgent.exe 发给用户，双击运行，
echo   浏览器会自动打开；首次运行生成 data 目录。
echo ------------------------------------------
pause
exit /b 0

:error
echo.
echo 打包失败，请检查上方错误信息后重试。
pause
exit /b 1
