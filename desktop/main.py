"""AV Agent 桌面版入口：启动 FastAPI 后端（线程）+ Qt 主窗口。

运行：python -m desktop.main
打包：Windows 下用 build_exe.bat（PyInstaller 入口仍为 exe_entry.py）。
"""

from __future__ import annotations

import os
import socket
import sys
import threading
import time

from app.config import settings

# ---------- 服务启动（与 exe_entry.py 保持同一套逻辑） ----------


def _port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.2)
        return s.connect_ex(("127.0.0.1", port)) != 0


def pick_free_port(preferred: int) -> int:
    for offset in range(50):
        port = preferred + offset
        if _port_is_free(port):
            return port
    return preferred + 50


def _load_or_create_token() -> str:
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


def start_server(stop_event: threading.Event) -> None:
    import uvicorn

    from app.main import app

    config = uvicorn.Config(app, host="127.0.0.1", port=settings.PORT, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not stop_event.wait(0.5):
        pass
    server.should_exit = True
    thread.join(timeout=5)


def wait_until_ready(base_url: str, timeout: float = 20.0) -> bool:
    import httpx

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = httpx.get(f"{base_url}/api/health", timeout=1.0)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.3)
    return False


# ---------- 桌面入口 ----------

def main() -> None:
    settings.ensure_dirs()
    settings.ACCESS_TOKEN = _load_or_create_token()
    settings.PORT = pick_free_port(settings.PORT)
    base_url = f"http://127.0.0.1:{settings.PORT}"

    from PySide6.QtWidgets import QApplication

    from desktop.api import AvApi
    from desktop.main_window import MainWindow
    from desktop.theme import apply_theme, load_theme_pref
    print("=" * 52)
    print("  AV Agent 桌面版正在启动…")
    print(f"  本机服务:  {base_url}")
    print(f"  局域网:    http://<电脑局域网IP>:{settings.PORT}（手机浏览器可访问）")
    print("=" * 52)

    stop_event = threading.Event()
    threading.Thread(target=start_server, args=(stop_event,), daemon=True).start()
    if not wait_until_ready(base_url):
        print("!! 服务启动超时，请检查端口占用或日志。")
        stop_event.set()

    app = QApplication(sys.argv)
    app.setApplicationName("AV Agent")
    apply_theme(app, load_theme_pref())

    from app.version import VERSION

    api = AvApi(base_url=base_url)
    window = MainWindow(api, app_version=VERSION)

    # 系统托盘：关窗最小化，服务常驻
    from desktop.tray import TrayController, hide_on_close

    quit_flag = {"done": False}

    def _show_window():
        window.showNormal()
        window.raise_()
        window.activateWindow()

    def _quit_app():
        quit_flag["done"] = True
        stop_event.set()
        app.quit()

    tray = TrayController(window_show=_show_window, window_quit=_quit_app)
    tray_ok = tray.install()
    if tray_ok:
        hide_on_close(window, tray)
        print("  托盘已启用：关闭窗口将最小化到托盘（服务保持运行）")
    else:
        print("  （当前环境无系统托盘，关闭窗口即退出）")
    window.show()

    rc = app.exec()
    if not quit_flag["done"]:
        stop_event.set()
    api.close()
    sys.exit(rc)


if __name__ == "__main__":
    main()
