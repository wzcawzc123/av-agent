"""AV Agent 打包入口（PyInstaller exe 模式）。

在 Windows 上运行 build_exe.bat 即可产出 dist/AVAgent.exe。
首次启动会在 exe 同级目录生成 data/（数据库、密钥、访问口令持久化）。
"""

import os
import threading
import webbrowser

import uvicorn

from app.config import settings
from app.main import app


def _load_or_create_token() -> str:
    """优先环境变量；否则读取/创建 data/access_token.txt，保证重启后口令不变。"""
    token = os.environ.get("AV_ACCESS_TOKEN")
    if token:
        return token
    token_file = os.path.join(settings.DATA_DIR, "access_token.txt")
    if os.path.exists(token_file):
        with open(token_file, encoding="utf-8") as f:
            token = f.read().strip()
        if token:
            return token
    token = settings.ACCESS_TOKEN
    os.makedirs(settings.DATA_DIR, exist_ok=True)
    with open(token_file, "w", encoding="utf-8") as f:
        f.write(token)
    return token


def _open_browser():
    host = "127.0.0.1"
    port = settings.PORT
    threading.Timer(1.5, lambda: webbrowser.open(f"http://{host}:{port}")).start()


def main():
    settings.ensure_dirs()
    token = _load_or_create_token()
    settings.ACCESS_TOKEN = token
    print("=" * 52)
    from app.version import VERSION
    print("  AV Agent v%s 已启动" % VERSION)
    print(f"  本机访问:  http://127.0.0.1:{settings.PORT}")
    print(f"  手机访问:  http://<电脑局域网IP>:{settings.PORT}")
    print(f"  访问口令:  {token}")
    print("  关闭窗口或按 Ctrl+C 停止服务")
    print("=" * 52)
    _open_browser()
    uvicorn.run(app, host=settings.HOST, port=settings.PORT, log_level="info")


if __name__ == "__main__":
    main()
