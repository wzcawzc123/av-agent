"""主窗口：左侧导航 + 右侧页面堆栈。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from desktop.api import AvApi
from desktop.pages.chat_page import ChatPage
from desktop.pages.knowledge_page import KnowledgePage
from desktop.pages.products_page import ProductsPage
from desktop.pages.projects_page import ProjectsPage
from desktop.pages.providers_page import ProvidersPage
from desktop.pages.settings_page import SettingsPage
from desktop.pages.templates_page import TemplatesPage
from desktop.pages.tender_page import TenderPage
from desktop.pages.tools_page import ToolsPage
from desktop.theme import icon_char, icon_font

NAV_ITEMS = [
    ("chat", "对话", "chat"),
    ("folder", "项目", "projects"),
    ("construction", "工具箱", "tools"),
    ("grid_view", "产品库", "products"),
    ("description", "模板库", "templates"),
    ("memory", "模型提供商", "providers"),
    ("receipt_long", "招标改单", "tender"),
    ("menu_book", "知识库", "knowledge"),
    ("settings", "设置", "settings"),
]


class MainWindow(QMainWindow):
    def __init__(self, api: AvApi, app_version: str = ""):
        super().__init__()
        self.api = api
        self.setWindowTitle(f"AV Agent 桌面版 {app_version}".rstrip())
        self.resize(1280, 840)
        self.setMinimumSize(1024, 680)

        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # 左侧导航（Codex 窄任务栏）
        self.nav = QListWidget()
        self.nav.setObjectName("navList")
        self.nav.setFixedWidth(176)
        for icon, label, key in NAV_ITEMS:
            item = QListWidgetItem(f"{icon_char(icon)}   {label}")
            item.setData(Qt.UserRole, key)
            item.setFont(icon_font(13))
            self.nav.addItem(item)
        brand = QLabel("AV Agent")
        brand.setObjectName("brand")
        nav_col = QVBoxLayout()
        nav_col.setContentsMargins(0, 0, 0, 0)
        nav_col.setSpacing(0)
        nav_col.addWidget(brand)
        nav_col.addWidget(self.nav, 1)
        nav_box = QWidget()
        nav_box.setObjectName("pageRoot")
        nav_box.setLayout(nav_col)
        nav_box.setFixedWidth(176)
        root.addWidget(nav_box)

        # 右侧页面堆栈
        self.stack = QStackedWidget()
        self.pages: dict[str, QWidget] = {}
        self._build_pages()
        root.addWidget(self.stack, 1)

        self.setCentralWidget(central)
        self.nav.currentRowChanged.connect(self._on_nav_changed)
        self.nav.setCurrentRow(0)

        self.statusBar().showMessage("服务运行中 · 本机访问免口令")

    def _build_pages(self) -> None:
        self.pages["chat"] = ChatPage(self.api)
        self.pages["projects"] = ProjectsPage(self.api)
        self.pages["tools"] = ToolsPage(self.api)
        self.pages["products"] = ProductsPage(self.api)
        self.pages["templates"] = TemplatesPage(self.api)
        self.pages["providers"] = ProvidersPage(self.api)
        self.pages["tender"] = TenderPage(self.api)
        self.pages["knowledge"] = KnowledgePage(self.api)
        self.pages["settings"] = SettingsPage(self.api)
        for _icon, _label, key in NAV_ITEMS:
            self.stack.addWidget(self.pages[key])

    def _on_nav_changed(self, row: int) -> None:
        if 0 <= row < len(NAV_ITEMS):
            key = NAV_ITEMS[row][2]
            page = self.pages[key]
            self.stack.setCurrentWidget(page)
            from desktop.anim import fade_in

            fade_in(page, duration=160)
            refresh = getattr(page, "on_show", None)
            if refresh:
                refresh()
