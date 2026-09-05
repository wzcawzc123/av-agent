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
rem desktop deps now via requirements.txt (win32 markers)

echo.
echo [2/4] 开始打包（约需 2-5 分钟）...
pyinstaller --clean --noconfirm av-agent.spec || goto :error

echo.
echo [3/4] 打包完成！
echo ------------------------------------------
echo   输出文件：dist\AVAgent.exe
echo   使用方法：把 AVAgent.exe 发给用户，双击运行，
echo   弹出原生窗口；关闭窗口最小化到托盘（服务保持
echo   运行，手机可继续经局域网访问）。
echo ------------------------------------------
pause
exit /b 0

:error
echo.
echo 打包失败，请检查上方错误信息后重试。
echo 提示：若提示缺少 WebView2Loader.dll，请确认已
echo 安装 WebView2 Runtime（Win10/11 一般自带）。
pause
exit /b 1
