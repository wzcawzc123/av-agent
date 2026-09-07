"""Material Design 3 主题：M3 色彩令牌 + QSS 生成器 + 字体/图标加载。

配色采用 M3 tonal palette（主色取品牌蓝 #4665EA 系）；浅/深两套 scheme，
按 M3 规范映射 surface / primaryContainer / outline 等角色，组件用 M3 形状
（small 8 / medium 12 / large 16 / extra 28）。字体 Roboto，图标 Material Symbols。
"""

from __future__ import annotations

import json
import os
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

_THEME_FILE = os.path.join(os.path.expanduser("~"), ".avagent_theme.json")
_FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "fonts")

# 当前生效主题（apply_theme 时更新，供页面按主题配色）
_current_dark: bool = False

# ---------- M3 色彩令牌 ----------

LIGHT_SCHEME = {
    "primary": "#4665EA",
    "onPrimary": "#FFFFFF",
    "primaryContainer": "#DEE0FF",
    "onPrimaryContainer": "#00145B",
    "secondary": "#5B5D72",
    "onSecondary": "#FFFFFF",
    "secondaryContainer": "#E0E1F9",
    "onSecondaryContainer": "#171B2C",
    "tertiary": "#77536D",
    "onTertiary": "#FFFFFF",
    "tertiaryContainer": "#FFD7F0",
    "onTertiaryContainer": "#2D1228",
    "error": "#BA1A1A",
    "onError": "#FFFFFF",
    "errorContainer": "#FFDAD6",
    "onErrorContainer": "#410002",
    "surface": "#FDF8FF",
    "onSurface": "#1B1B1F",
    "surfaceVariant": "#E2E1EC",
    "onSurfaceVariant": "#45464F",
    "surfaceContainerLowest": "#FFFFFF",
    "surfaceContainerLow": "#F7F2FA",
    "surfaceContainer": "#F1ECF4",
    "surfaceContainerHigh": "#EBE6EF",
    "surfaceContainerHighest": "#E5E0E9",
    "outline": "#767680",
    "outlineVariant": "#C6C5D0",
    "scrim": "#000000",
}

DARK_SCHEME = {
    "primary": "#B9C4FF",
    "onPrimary": "#08208F",
    "primaryContainer": "#2A47C6",
    "onPrimaryContainer": "#DEE0FF",
    "secondary": "#C4C5DD",
    "onSecondary": "#2D2F43",
    "secondaryContainer": "#43465B",
    "onSecondaryContainer": "#E0E1F9",
    "tertiary": "#E5BAD8",
    "onTertiary": "#45273F",
    "tertiaryContainer": "#5D3D56",
    "onTertiaryContainer": "#FFD7F0",
    "error": "#FFB4AB",
    "onError": "#690005",
    "errorContainer": "#93000A",
    "onErrorContainer": "#FFDAD6",
    "surface": "#131318",
    "onSurface": "#E4E1E9",
    "surfaceVariant": "#45464F",
    "onSurfaceVariant": "#C6C5D0",
    "surfaceContainerLowest": "#0E0E13",
    "surfaceContainerLow": "#1B1B20",
    "surfaceContainer": "#1F1F24",
    "surfaceContainerHigh": "#29292F",
    "surfaceContainerHighest": "#34343A",
    "outline": "#90909A",
    "outlineVariant": "#45464F",
    "scrim": "#000000",
}

_SCHEMES = {"light": LIGHT_SCHEME, "dark": DARK_SCHEME}


# ---------- 字体与图标 ----------


def load_fonts() -> None:
    """注册 Roboto 与 Material Symbols 字体（幂等）。"""
    try:
        db = QFontDatabase()
        for name in ("Roboto-Regular.ttf", "Roboto-Medium.ttf", "Roboto-Bold.ttf",
                     "MaterialSymbolsOutlined.ttf"):
            path = os.path.join(_FONT_DIR, name)
            if os.path.isfile(path):
                db.addApplicationFont(path)
    except Exception:
        pass


# Material Symbols Outlined 常用码位（继承 Material Icons 经典码位）
_ICON_CODEPOINTS = {
    "chat": 0xE0B7, "folder": 0xE2C7, "construction": 0xEA86, "grid_view": 0xE9B0,
    "description": 0xE873, "memory": 0xE322, "receipt_long": 0xEAEF, "menu_book": 0xEA19,
    "settings": 0xE8B8, "send": 0xE163, "add": 0xE145, "close": 0xE5CD,
    "check": 0xE5CA, "delete": 0xE872, "edit": 0xE150, "refresh": 0xE5D5,
    "search": 0xE8B6, "download": 0xE2C4, "upload": 0xE219, "info": 0xE88E,
    "warning": 0xE002, "error": 0xE000, "more_vert": 0xE5D4, "arrow_back": 0xE5C4,
    "arrow_forward": 0xE5C8, "done_all": 0xE92F, "play": 0xE037, "star": 0xE838,
    "list": 0xE896, "cloud_upload": 0xE2C3, "auto_awesome": 0xE65F, "extension": 0xE3E3,
    "bolt": 0xEA0B, "database": 0xE1DC, "folder_open": 0xE2C8, "visibility": 0xE8F4,
    "build": 0xE869, "book": 0xE866, "content_copy": 0xE14D, "open_in_new": 0xE89E,
}


def icon_char(name: str) -> str:
    """返回 Material Symbols 图标字符；未知名称返回空。"""
    cp = _ICON_CODEPOINTS.get(name)
    if cp is None:
        return ""
    return chr(cp)


def icon_font(size: int = 20) -> QFont:
    font = QFont("Material Symbols Outlined", size)
    try:
        font.setWeight(QFont.Weight.Normal)
    except TypeError:
        font.setWeight(400)
    return font


# ---------- QSS 生成 ----------


def build_qss(s: dict) -> str:
    """由 M3 scheme 生成全局 QSS。"""
    return f"""
QMainWindow, QWidget {{ background: {s['surface']}; color: {s['onSurface']}; font-family: 'Roboto'; font-size: 13px; }}
QWidget#pageRoot {{ background: {s['surface']}; }}
QLabel#brand {{ font-family: 'Roboto'; font-weight: 700; font-size: 16px; color: {s['primary']}; padding: 20px 20px 6px 24px; }}
QLabel#title {{ font-size: 22px; font-weight: 700; color: {s['onSurface']}; }}
QLabel#subtitle {{ font-size: 14px; font-weight: 500; color: {s['onSurface']}; }}
QLabel#hint {{ color: {s['onSurfaceVariant']}; }}
QLabel#err {{ color: {s['error']}; }}
QLabel#ok {{ color: {s['primary']}; }}

/* ---- 导航（M3 Navigation Drawer） ---- */
QListWidget#navList {{
    background: {s['surfaceContainerLow']}; border: none; border-right: 1px solid {s['outlineVariant']};
    font-size: 14px; outline: 0; padding-top: 4px; padding-bottom: 16px;
}}
QListWidget#navList::item {{
    height: 44px; padding-left: 20px; border-radius: 22px; margin: 2px 12px;
    color: {s['onSurfaceVariant']}; font-weight: 500;
}}
QListWidget#navList::item:hover {{ background: {s['surfaceContainerHigh']}; }}
QListWidget#navList::item:selected {{
    background: {s['secondaryContainer']}; color: {s['onSecondaryContainer']}; font-weight: 600;
}}

/* ---- 按钮（M3 Filled / Outlined / Text） ---- */
QPushButton {{
    background: {s['primary']}; color: {s['onPrimary']}; border: none; border-radius: 20px;
    padding: 8px 22px; font-family: 'Roboto'; font-weight: 500; font-size: 13px;
}}
QPushButton:hover {{ background: {s['primaryContainer']}; color: {s['onPrimaryContainer']}; }}
QPushButton:pressed {{ background: {s['primary']}; }}
QPushButton:disabled {{ background: {s['surfaceContainerHighest']}; color: {s['onSurfaceVariant']}; }}
QPushButton#outlined {{
    background: transparent; color: {s['primary']}; border: 1px solid {s['outline']}; border-radius: 20px;
}}
QPushButton#outlined:hover {{ background: {s['surfaceContainerHigh']}; }}
QPushButton#outlined:pressed {{ background: {s['surfaceContainerHighest']}; }}
QPushButton#text {{
    background: transparent; color: {s['primary']}; border: none; border-radius: 20px;
}}
QPushButton#text:hover {{ background: {s['surfaceContainerHigh']}; }}
QPushButton#danger {{
    background: transparent; color: {s['error']}; border: 1px solid {s['outline']}; border-radius: 20px;
}}
QPushButton#danger:hover {{ background: {s['errorContainer']}; color: {s['onErrorContainer']}; }}

/* ---- 输入（M3 Outlined Text Field） ---- */
QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    background: {s['surfaceContainerLow']}; border: 1px solid {s['outline']}; border-radius: 8px;
    padding: 8px 10px; selection-background-color: {s['primaryContainer']};
    selection-color: {s['onPrimaryContainer']}; font-family: 'Roboto'; font-size: 13px;
}}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QComboBox:focus {{
    border: 2px solid {s['primary']}; padding: 7px 9px;
}}
QComboBox::drop-down {{ border: none; width: 26px; }}
QComboBox QAbstractItemView {{
    background: {s['surfaceContainerLow']}; color: {s['onSurface']};
    border: 1px solid {s['outlineVariant']}; border-radius: 8px; selection-background-color: {s['secondaryContainer']};
    selection-color: {s['onSecondaryContainer']};
}}

/* ---- 卡片 / 表格 ---- */
QFrame#card {{
    background: {s['surfaceContainerLow']}; border: 1px solid {s['outlineVariant']};
    border-radius: 16px;
}}
QTableWidget {{
    background: {s['surfaceContainerLow']}; border: 1px solid {s['outlineVariant']}; border-radius: 12px;
    gridline-color: {s['outlineVariant']}; selection-background-color: {s['secondaryContainer']};
    selection-color: {s['onSecondaryContainer']}; font-family: 'Roboto';
}}
QHeaderView::section {{
    background: {s['surfaceContainerHigh']}; border: none; border-bottom: 1px solid {s['outlineVariant']};
    padding: 10px; font-weight: 600; color: {s['onSurfaceVariant']};
}}
QTableCornerButton::section {{ background: {s['surfaceContainerHigh']}; border: none; }}

/* ---- Tab（M3 下划线） ---- */
QTabWidget::pane {{ border: none; background: transparent; }}
QTabBar::tab {{
    padding: 10px 18px; background: transparent; color: {s['onSurfaceVariant']};
    font-weight: 500; border-bottom: 2px solid transparent;
}}
QTabBar::tab:selected {{ color: {s['primary']}; border-bottom: 2px solid {s['primary']}; }}
QTabBar::tab:hover {{ color: {s['onSurface']}; }}

/* ---- 滚动区 / 对话框 / 进度 ---- */
QScrollArea {{ border: none; background: transparent; }}
QMessageBox, QDialog {{ background: {s['surfaceContainerLow']}; }}
QMessageBox QLabel, QDialog QLabel {{ color: {s['onSurface']}; }}
QProgressBar {{
    border: none; border-radius: 5px; background: {s['surfaceContainerHighest']};
    text-align: center; color: {s['onSurface']}; height: 20px;
}}
QProgressBar::chunk {{ background: {s['primary']}; border-radius: 5px; }}
QStatusBar {{ background: {s['surfaceContainerLow']}; border-top: 1px solid {s['outlineVariant']}; color: {s['onSurfaceVariant']}; }}
QTextBrowser {{
    background: {s['surfaceContainerLow']}; border: 1px solid {s['outlineVariant']};
    border-radius: 12px; padding: 10px; color: {s['onSurface']}; font-family: 'Roboto';
}}
QSplitter::handle {{ background: {s['outlineVariant']}; }}
QScrollBar:vertical {{ background: transparent; width: 10px; }}
QScrollBar::handle:vertical {{ background: {s['outlineVariant']}; border-radius: 5px; min-height: 30px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; }}
QScrollBar::handle:horizontal {{ background: {s['outlineVariant']}; border-radius: 5px; min-width: 30px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
"""


def scheme(dark: bool) -> dict:
    return DARK_SCHEME if dark else LIGHT_SCHEME


def is_dark() -> bool:
    return _current_dark


def apply_theme(app: QApplication, dark: Optional[bool] = None) -> bool:
    """应用主题；dark=None 跟随系统。返回是否深色。"""
    global _current_dark
    if dark is None:
        dark = system_dark()
    _current_dark = dark
    load_fonts()
    app.setStyleSheet(build_qss(scheme(dark)))
    return dark


def system_dark() -> bool:
    try:
        from PySide6.QtGui import QGuiApplication

        return QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark
    except Exception:
        return False


def load_theme_pref() -> Optional[bool]:
    try:
        with open(_THEME_FILE, encoding="utf-8") as f:
            val = json.load(f).get("dark")
            return None if val is None else bool(val)
    except Exception:
        return None


def save_theme_pref(dark: Optional[bool]) -> None:
    try:
        with open(_THEME_FILE, "w", encoding="utf-8") as f:
            json.dump({"dark": dark}, f)
    except Exception:
        pass
