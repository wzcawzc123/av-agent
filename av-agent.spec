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
    + collect_submodules("pdfplumber")
    # 桌面模式（PySide6 原生界面）
    + collect_submodules("desktop")
)

datas = [("static", "static"), ("desktop/assets/fonts", "desktop/assets/fonts")]

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
