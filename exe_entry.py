"""AV Agent 打包入口（PyInstaller exe 模式，PyWebView + 系统托盘）。

在 Windows 上运行 build_exe.bat 即可产出 dist\\AVAgent.exe：
- 启动 FastAPI 服务（后台线程），手机可经局域网访问；
- 弹出 PyWebView 原生窗口加载本机界面；
- 关闭窗口时最小化到系统托盘，服务保持运行；
- 托盘菜单：显示主界面 / 浏览器打开 / 退出程序。

首次启动会在 exe 同级目录生成 data\\（数据库、密钥、访问口令持久化）。
"""

import os
import socket
import sys
import threading

import uvicorn

from app.config import settings
from app.main import app


# ---------- 纯逻辑（可单测） ----------

def resolve_app_base() -> str:
    """PyInstaller 解包目录（_MEIPASS）或源码根目录。"""
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return meipass
    return os.path.dirname(os.path.abspath(__file__))


def ensure_resource_path(*parts: str) -> str:
    """定位打包后的资源文件（如 static/）。"""
    return os.path.join(resolve_app_base(), *parts)


def _port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.2)
        return s.connect_ex(("127.0.0.1", port)) != 0


def pick_free_port(preferred: int) -> int:
    """端口被占用时自动 +1 避让（最多 50 次）。"""
    for offset in range(50):
        port = preferred + offset
        if _port_is_free(port):
            return port
    return preferred + 50


def build_local_url(host: str, port: int) -> str:
    return f"http://{host}:{port}"


def _load_or_create_token() -> str:
    """优先环境变量；否则读取/创建 data\\access_token.txt，保证重启后口令不变。"""
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


# ---------- 桌面壳（仅 Windows 打包时使用） ----------

def _run_server(stop_event: threading.Event) -> None:
    config = uvicorn.Config(app, host=settings.HOST, port=settings.PORT, log_level="info")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not stop_event.wait(0.5):
        pass
    server.should_exit = True
    thread.join(timeout=5)


def _make_tray_image():
    """用 PIL 生成一个简单的 AV 图标（避免额外打包 .ico 文件）。"""
    from PIL import Image, ImageDraw

    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([4, 4, 60, 60], radius=14, fill=(0, 122, 255, 255))
    d.text((16, 14), "AV", fill=(255, 255, 255, 255))
    return img


def main():
    settings.ensure_dirs()
    token = _load_or_create_token()
    settings.ACCESS_TOKEN = token

    settings.PORT = pick_free_port(settings.PORT)
    host, port = "127.0.0.1", settings.PORT
    url = build_local_url(host, port)

    from app.version import VERSION

    stop_event = threading.Event()
    threading.Thread(target=_run_server, args=(stop_event,), daemon=True).start()

    print("=" * 52)
    print("  AV Agent v%s 已启动（桌面模式）" % VERSION)
    print(f"  本机访问:  {url}")
    print(f"  手机访问:  http://<电脑局域网IP>:{port}")
    print(f"  访问口令:  {token}")
    print("  关闭窗口最小化到托盘，服务保持运行")
    print("=" * 52)

    # PyWebView / pystray 懒加载：开发环境（Linux/macOS 源码运行）不依赖
    try:
        import webview

        import pystray
    except ImportError:
        print("未安装桌面依赖（pywebview/pystray），退回浏览器模式。")
        import webbrowser

        threading.Timer(1.5, lambda: webbrowser.open(url)).start()
        try:
            while not stop_event.wait(1):
                pass
        except KeyboardInterrupt:
            pass
        stop_event.set()
        return

    exit_flag = threading.Event()
    hidden_flag = threading.Event()

    def on_closing():
        # 关闭窗口 → 隐藏到托盘，不退出（除非已走托盘「退出程序」）
        if exit_flag.is_set():
            return
        hidden_flag.set()
        try:
            import webview as _w

            if _w.windows:
                _w.windows[0].hide()
        except Exception:
            pass

    def show_window():
        hidden_flag.clear()
        try:
            import webview as _w

            if _w.windows:
                _w.windows[0].show()
                _w.windows[0].restore()
        except Exception:
            pass

    def quit_app():
        exit_flag.set()
        stop_event.set()
        try:
            import webview as _w

            if _w.windows:
                _w.windows[0].destroy()
        except Exception:
            pass

    menu = pystray.Menu(
        pystray.MenuItem("显示主界面", lambda icon, item: show_window(), default=True),
        pystray.MenuItem("在浏览器打开", lambda icon, item: os.startfile(url)),
        pystray.MenuItem("退出程序", lambda icon, item: quit_app()),
    )
    icon = pystray.Icon("AVAgent", _make_tray_image(), "AV Agent", menu)

    def _run_tray():
        try:
            icon.run()
        except Exception as e:  # 托盘失败不应阻断主程序
            print("托盘启动失败：", e)
            exit_flag.set()
            stop_event.set()

    threading.Thread(target=_run_tray, daemon=True).start()

    window = webview.create_window(
        "AV Agent",
        url,
        width=1180,
        height=820,
        min_size=(960, 640),
        text_select=True,
    )
    window.events.closing += on_closing
    webview.start(debug=False)
    # 关窗后保持托盘常驻，直到托盘「退出程序」
    while not exit_flag.wait(0.5):
        pass
    stop_event.set()


if __name__ == "__main__":
    main()
