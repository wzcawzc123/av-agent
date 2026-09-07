@echo off
chcp 65001 >nul
title AV Agent 一键打包
echo ==========================================
echo   AV Agent 一键打包脚本（Windows）
echo ==========================================
echo.

echo [1/4] 安装依赖...
pip install -r requirements.txt || goto :error
pip install pyinstaller || goto :error

echo.
echo [2/4] 开始打包（约需 3-8 分钟，PySide6 体积较大）...
pyinstaller --clean --noconfirm av-agent.spec || goto :error

echo.
echo [3/4] 打包完成！
echo ------------------------------------------
echo   输出文件：dist\AVAgent.exe
echo   使用方法：把 AVAgent.exe 发给用户，双击运行，
echo   弹出原生桌面窗口（对话工作台 + 产品库/模板库/
echo   提供商/招标/知识库）；服务保持运行，手机可经
echo   局域网访问同一实例。
echo ------------------------------------------
pause
exit /b 0

:error
echo.
echo 打包失败，请检查上方错误信息后重试。
pause
exit /b 1
