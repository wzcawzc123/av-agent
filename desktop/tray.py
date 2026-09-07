"""系统托盘：关窗最小化到托盘，服务保持运行；托盘菜单控制窗口与退出。

关闭主窗口不退出程序（隐藏到托盘），避免用户误关导致后台服务中断；
托盘菜单提供「显示主界面 / 在浏览器打开 / 退出程序」。
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon


def _make_icon() -> QIcon:
    """用 QPainter 画一个简易 AV 图标（避免外带资源文件）。"""
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QColor("#0066ff"))
    painter.setPen(Qt.NoPen)
    painter.drawRoundedRect(4, 4, 56, 56, 14, 14)
    painter.setPen(QColor("#ffffff"))
    font = painter.font()
    font.setPixelSize(22)
    font.setBold(True)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignCenter, "AV")
    painter.end()
    return QIcon(pixmap)


class TrayController:
    """持有托盘图标；window_show / window_quit 由外部注入。"""

    def __init__(self, window_show, window_quit):
        self._window_show = window_show
        self._window_quit = window_quit
        self.tray: QSystemTrayIcon | None = None
        self.quit_requested = False

    def install(self, tooltip: str = "AV Agent 桌面版") -> bool:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return False
        menu = QMenu()
        show_action = QAction("显示主界面", menu)
        show_action.triggered.connect(self._window_show)
        menu.addAction(show_action)
        open_web = QAction("在浏览器打开", menu)
        open_web.triggered.connect(self._open_in_browser)
        menu.addAction(open_web)
        menu.addSeparator()
        quit_action = QAction("退出程序", menu)
        quit_action.triggered.connect(self._request_quit)
        menu.addAction(quit_action)

        tray = QSystemTrayIcon(_make_icon())
        tray.setToolTip(tooltip)
        tray.setContextMenu(menu)
        tray.activated.connect(self._on_activated)
        tray.show()
        self.tray = tray
        return True

    def _on_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.Trigger:
            self._window_show()

    def _open_in_browser(self) -> None:
        try:
            from app.config import settings

            import webbrowser

            webbrowser.open(f"http://127.0.0.1:{settings.PORT}")
        except Exception:
            pass

    def _request_quit(self) -> None:
        self.quit_requested = True
        self._window_quit()

    def notify(self, title: str, message: str) -> None:
        if self.tray is not None:
            self.tray.showMessage(title, message, QSystemTrayIcon.Information, 3000)


def hide_on_close(window, tray: TrayController) -> None:
    """主窗口 closeEvent：非退出请求时隐藏到托盘。"""
    original = window.closeEvent

    def handler(event):
        if tray.quit_requested:
            original(event) if original else event.accept()
            return
        event.ignore()
        window.hide()
        tray.notify("AV Agent 仍在运行", "已最小化到托盘，服务保持运行。右键托盘图标可退出。")

    window.closeEvent = handler
