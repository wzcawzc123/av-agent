"""Codex 同款 UI 主题：近黑灰阶 + ChatGPT 品牌绿点缀，沉浸式对话优先。

配色与结构复刻 OpenAI Codex 桌面端/ChatGPT 深色界面的视觉语言：
背景 #0D0D0D 系灰阶层级、无彩色噪音、accent 只用 #10A37F（品牌绿）。
浅色主题保留为次要方案（ChatGPT 浅色灰白系）。
字体 Roboto（UI）+ 系统等宽（代码块）。图标 Material Symbols。
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

_current_dark: bool = True  # Codex 风格以深色为默认

# ---------- MIUIX 官方色板(compose-miuix-ui/miuix 0.9.4 源码 Colors.kt) ----------

DARK_SCHEME = {
    "bg": "#242424",            # background
    "surface": "#000000",       # surface（深色）
    "raised": "#242424",        # surfaceContainer
    "hover": "#2D2D2D",         # surfaceContainerHighest
    "active": "#2D2D2D",
    "border": "#404040",        # outline
    "border_strong": "#505050",
    "text": "#F2F2F2",          # onSurface
    "text_secondary": "#99C7F1",
    "text_muted": "#959595",
    "accent": "#277AF7",        # primary
    "accent_hover": "#338FE4",  # primaryContainer
    "accent_fg": "#FFFFFF",
    "accent_soft": "#253E64",   # 低饱和蓝底
    "code_bg": "#000000",
    "user_bubble": "#242424",
    "error": "#F12522",
    "error_soft": "#2E0603",
    "warn": "#E94634",
    "warn_soft": "#2E0603",
    "ok": "#99C7F1",
    "ok_soft": "#253E64",
    "scrollbar": "#404040",
    "divider": "#393939",       # dividerLine
}

LIGHT_SCHEME = {
    "bg": "#F7F7F7",            # background / surface（浅灰 MIUI 底）
    "surface": "#FFFFFF",       # 卡片白
    "raised": "#F7F7F7",
    "hover": "#E8E8E8",         # surfaceContainerHighest
    "active": "#E8E8E8",
    "border": "#D9D9D9",        # outline
    "border_strong": "#B2B2B2",
    "text": "#000000",          # onSurface
    "text_secondary": "#8C93B0",# onBackgroundVariant
    "text_muted": "#959595",
    "accent": "#3482FF",        # primary
    "accent_hover": "#5D9BFF",  # primaryContainer
    "accent_fg": "#FFFFFF",
    "accent_soft": "#EAF2FF",   # tertiaryContainer
    "code_bg": "#F7F7F7",
    "user_bubble": "#FFFFFF",
    "error": "#E94634",
    "error_soft": "#FDF6F4",
    "warn": "#E94634",
    "warn_soft": "#FDF6F4",
    "ok": "#3482FF",
    "ok_soft": "#EAF2FF",
    "scrollbar": "#D9D9D9",
    "divider": "#E0E0E0",       # dividerLine
}

_SCHEMES = {"dark": DARK_SCHEME, "light": LIGHT_SCHEME}


# ---------- 字体与图标 ----------


def load_fonts() -> None:
    try:
        db = QFontDatabase()
        for name in ("Roboto-Regular.ttf", "Roboto-Medium.ttf", "Roboto-Bold.ttf",
                     "MaterialSymbolsOutlined.ttf"):
            path = os.path.join(_FONT_DIR, name)
            if os.path.isfile(path):
                db.addApplicationFont(path)
    except Exception:
        pass


def scheme(dark: Optional[bool] = None) -> dict:
    dark = _current_dark if dark is None else dark
    return DARK_SCHEME if dark else LIGHT_SCHEME


def is_dark() -> bool:
    return _current_dark


# Material Symbols 码位（继承 Material Icons 经典码位）
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
    "mic": 0xE029, "stop": 0xE047, "keyboard": 0xE312, "file_present": 0xEA0E,
}


def icon_char(name: str) -> str:
    cp = _ICON_CODEPOINTS.get(name)
    return chr(cp) if cp is not None else ""


def icon_font(size: int = 20) -> QFont:
    font = QFont("Material Symbols Outlined", size)
    try:
        font.setWeight(QFont.Weight.Normal)
    except TypeError:
        font.setWeight(400)
    return font


# ---------- QSS ----------


def build_qss(s: dict) -> str:
    return f"""
QMainWindow, QWidget {{ background: {s['bg']}; color: {s['text']}; font-family: 'Roboto'; font-size: 13px; }}
QLabel#brand {{ font-family: 'Roboto'; font-weight: 700; font-size: 14px; color: {s['text']}; padding: 18px 18px 6px 18px; }}
QLabel#title {{ font-size: 15px; font-weight: 600; color: {s['text']}; }}
QLabel#subtitle {{ font-size: 12px; font-weight: 500; color: {s['text_secondary']}; }}
QLabel#hint {{ color: {s['text_muted']}; }}
QLabel#err {{ color: {s['error']}; }}
QLabel#ok {{ color: {s['ok']}; }}

/* 侧栏（Codex 窄任务栏） */
QListWidget#navList {{
    background: {s['surface']}; border: none; border-right: 1px solid {s['border']};
    font-size: 13px; outline: 0; padding-top: 4px;
}}
QListWidget#navList::item {{
    height: 36px; padding-left: 14px; border-radius: 20px; margin: 2px 10px;
    color: {s['text_secondary']};
}}
QListWidget#navList::item:hover {{ background: {s['hover']}; color: {s['text']}; }}
QListWidget#navList::item:selected {{ background: {s['active']}; color: {s['text']}; font-weight: 500; }}

/* 按钮（Codex 式：绿主操作 / 灰次要） */
QPushButton {{
    background: {s['accent']}; color: {s['accent_fg']}; border: none; border-radius: 21px;
    padding: 7px 16px; font-family: 'Roboto'; font-weight: 500; font-size: 13px;
}}
QPushButton:hover {{ background: {s['accent_hover']}; }}
QPushButton:pressed {{ background: {s['accent']}; }}
QPushButton:disabled {{ background: {s['active']}; color: {s['text_muted']}; }}
QPushButton#outlined {{
    background: transparent; color: {s['text']}; border: 1px solid {s['border_strong']}; border-radius: 21px;
}}
QPushButton#outlined:hover {{ background: {s['hover']}; }}
QPushButton#outlined:pressed {{ background: {s['active']}; }}
QPushButton#text {{ background: transparent; color: {s['text_secondary']}; border: none; border-radius: 21px; }}
QPushButton#text:hover {{ background: {s['hover']}; color: {s['text']}; }}
QPushButton#danger {{ background: transparent; color: {s['error']}; border: 1px solid {s['border_strong']}; border-radius: 21px; }}
QPushButton#danger:hover {{ background: {s['error_soft']}; }}

/* 输入（Codex 式圆角输入框） */
QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    background: {s['raised']}; border: 1px solid {s['border']}; border-radius: 14px;
    padding: 8px 12px; selection-background-color: {s['accent_soft']};
    selection-color: {s['text']}; font-family: 'Roboto'; font-size: 13px;
}}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QComboBox:focus {{
    border: 1px solid {s['accent']}; background: {s['raised']};
}}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox QAbstractItemView {{
    background: {s['surface']}; color: {s['text']};
    border: 1px solid {s['border']}; border-radius: 14px; selection-background-color: {s['active']};
}}

/* 表格 */
QTableWidget {{
    background: {s['surface']}; border: 1px solid {s['border']}; border-radius: 20px;
    gridline-color: {s['border']}; selection-background-color: {s['active']};
    selection-color: {s['text']}; font-family: 'Roboto';
}}
QHeaderView::section {{
    background: {s['raised']}; border: none; border-bottom: 1px solid {s['border']};
    padding: 8px 10px; font-weight: 500; color: {s['text_secondary']};
}}
QTableCornerButton::section {{ background: {s['raised']}; border: none; }}

/* Tab */
QTabWidget::pane {{ border: none; background: transparent; }}
QTabBar::tab {{
    padding: 8px 14px; background: transparent; color: {s['text_secondary']};
    font-weight: 500; border-bottom: 2px solid transparent;
}}
QTabBar::tab:selected {{ color: {s['text']}; border-bottom: 2px solid {s['accent']}; }}
QTabBar::tab:hover {{ color: {s['text']}; }}

/* 滚动区 / 对话框 / 进度 */
QScrollArea {{ border: none; background: transparent; }}
QMessageBox, QDialog {{ background: {s['surface']}; }}
QMessageBox QLabel, QDialog QLabel {{ color: {s['text']}; }}
QProgressBar {{
    border: none; border-radius: 8px; background: {s['raised']};
    text-align: center; color: {s['text_secondary']}; height: 6px;
}}
QProgressBar::chunk {{ background: {s['accent']}; border-radius: 8px; }}
QStatusBar {{ background: {s['surface']}; border-top: 1px solid {s['border']}; color: {s['text_muted']}; }}
QTextBrowser {{
    background: transparent; border: none; padding: 2px; color: {s['text']}; font-family: 'Roboto';
}}
QSplitter::handle {{ background: {s['border']}; }}
QScrollBar:vertical {{ background: transparent; width: 8px; }}
QScrollBar::handle:vertical {{ background: {s['scrollbar']}; border-radius: 4px; min-height: 30px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 8px; }}
QScrollBar::handle:horizontal {{ background: {s['scrollbar']}; border-radius: 4px; min-width: 30px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
"""


def apply_theme(app: QApplication, dark: Optional[bool] = None) -> bool:
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
        return True


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
