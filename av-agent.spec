# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置：python pyinstaller --clean --noconfirm av-agent.spec"""
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

hiddenimports = (
    collect_submodules("uvicorn")
    + collect_submodules("sqlalchemy")
    + collect_submodules("httpx")
    + collect_submodules("h11")
    + collect_submodules("httpcore")
    + collect_submodules("openpyxl")
    + collect_submodules("docx")
    + collect_submodules("pptx")
    + collect_submodules("cryptography")
    # 桌面模式（PyWebView + 托盘）
    + collect_submodules("webview")
    + collect_submodules("pystray")
    + collect_submodules("PIL")
    + collect_submodules("clr_loader")
)

datas = (
    [("static", "static")]
    # pywebview 的 Windows 后端需要 WebView2Loader 等原生资源
    + collect_data_files("webview")
    + collect_data_files("clr_loader")
)

a = Analysis(
    ["exe_entry.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="AVAgent",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
