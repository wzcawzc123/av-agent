"""AV Agent 打包入口（PyInstaller exe 模式，PySide6 原生桌面版）。

启动 FastAPI 服务（后台线程）+ PySide6 原生桌面窗口。
首次启动会在 exe 同级目录生成 data\\（数据库、密钥、访问口令持久化）。
"""

import sys


def main():
    try:
        from desktop.main import main as desktop_main
    except ImportError as e:
        print("!! 桌面依赖缺失（PySide6）：", e)
        print("   请先执行 pip install -r requirements.txt 后重试。")
        sys.exit(1)
    desktop_main()


if __name__ == "__main__":
    main()
