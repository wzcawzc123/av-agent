"""质感组件：阴影、淡入动效、头像、工具卡片。

PySide6 的 QSS 只能做颜色/圆角，真正的"高级感"来自阴影层次与动效——
QGraphicsDropShadowEffect 提供柔和阴影，QPropertyAnimation 提供过渡动画。
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from desktop.theme import icon_char, icon_font, scheme, is_dark


def bubble_palette(style: str) -> dict:
    """Codex 风格：用户灰泡；AI 无气泡（透明），Markdown 直接铺开。"""
    s = scheme()
    table = {
        "user": {"bg": s["user_bubble"], "fg": s["text"], "border": s["user_bubble"]},
        "system": {"bg": "transparent", "fg": s["text_secondary"], "border": "transparent"},
        "warn": {"bg": s["warn_soft"], "fg": s["warn"], "border": s["warn_soft"]},
        "err": {"bg": s["error_soft"], "fg": s["error"], "border": s["error_soft"]},
        "engine": {"bg": s["accent_soft"], "fg": s["ok"], "border": s["accent_soft"]},
        "ok": {"bg": s["accent_soft"], "fg": s["ok"], "border": s["accent_soft"]},
        "agent": {"bg": "transparent", "fg": s["text"], "border": "transparent"},
        "": {"bg": "transparent", "fg": s["text"], "border": "transparent"},
    }
    return table.get(style, table[""])


def make_md_browser(style: str = "agent", max_width: int = 900) -> QTextBrowser:
    """Markdown 渲染（Codex 风格：无气泡、代码块深底、链接绿色）。"""
    palette = bubble_palette(style)
    s = scheme()
    browser = QTextBrowser()
    browser.setReadOnly(True)
    browser.setFrameShape(QTextBrowser.NoFrame)
    browser.setMaximumWidth(max_width)
    browser.setStyleSheet(
        f"QTextBrowser {{ background:{palette['bg']}; color:{palette['fg']};"
        f" border:none; padding:2px; }}"
    )
    browser.setOpenExternalLinks(True)
    browser.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse)
    browser.document().setDocumentMargin(4)
    return browser


def add_shadow(widget: QWidget, blur: int = 28, dy: int = 5, alpha: int = 36) -> QGraphicsDropShadowEffect:
    """给控件加柔和阴影（浅色 36 透明度，深色自动加深）。"""
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur)
    effect.setOffset(0, dy)
    dark = is_dark()
    effect.setColor(QColor(0, 0, 0, alpha if not dark else alpha * 2))
    widget.setGraphicsEffect(effect)
    return effect


def fade_in(widget: QWidget, duration: int = 220, start_opacity: float = 0.0) -> QPropertyAnimation:
    """淡入动效：widget 从透明渐显。返回动画（需保持引用）。"""
    effect = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effect)
    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(duration)
    anim.setStartValue(start_opacity)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.OutCubic)
    anim.start()
    return anim


def _avatar_pixmap(icon: str, size: int, bg: str, fg: str) -> QPixmap:
    """用 Material Symbols 图标画圆形头像。"""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QColor(bg))
    painter.setPen(Qt.NoPen)
    painter.drawEllipse(0, 0, size, size)
    painter.setPen(QColor(fg))
    font = icon_font(size // 2)
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignCenter, icon_char(icon))
    painter.end()
    return pixmap


def avatar_label(icon: str, size: int = 34, role: str = "agent") -> QLabel:
    """对话头像：Agent 用品牌绿底白图标，用户用灰底灰图标（Codex 风格）。"""
    s = scheme()
    if role == "user":
        bg, fg = s["user_bubble"], s["text_secondary"]
    else:
        bg, fg = s["accent"], s["accent_fg"]
    label = QLabel()
    label.setPixmap(_avatar_pixmap(icon, size, bg, fg))
    label.setFixedSize(size, size)
    return label


class ToolCallCard(QFrame):
    """Agent 工具调用卡片：图标 + 工具名 + 结果摘要，M3 容器色圆角。"""

    def __init__(self, tool_name: str, result: str = "", parent: Optional[QWidget] = None):
        super().__init__(parent)
        s = scheme()
        self.setObjectName("toolCard")
        self.setStyleSheet(
            f"QFrame#toolCard {{ background:{s['raised']}; border:1px solid {s['border']}; border-radius:12px; }}"
        )
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(10)
        icon = QLabel()
        icon.setPixmap(_avatar_pixmap("bolt", 22, s["accent_soft"], s["accent"]))
        lay.addWidget(icon)
        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        name = QLabel(f"调用工具 · {tool_name}")
        name.setStyleSheet(f"font-weight:600;color:{s['text']};font-size:12px;")
        text_col.addWidget(name)
        if result:
            summary = QLabel(result[:120])
            summary.setWordWrap(True)
            summary.setStyleSheet(f"color:{s['text_secondary']};font-size:12px;")
            text_col.addWidget(summary)
        lay.addLayout(text_col, 1)
        lay.addStretch(0)


class MessageBubble(QFrame):
    """对话消息容器：头像 + 名称/时间行 + 正文气泡，支持入场淡入。"""

    def __init__(self, role: str, icon: str, name: str, timestamp: str = "",
                 bubble_style: str = "agent", parent: Optional[QWidget] = None,
                 max_width: int = 820):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._anim: Optional[QPropertyAnimation] = None

        row = QHBoxLayout(self)
        row.setContentsMargins(8, 4, 8, 4)
        row.setSpacing(10)

        avatar = avatar_label(icon, 34, role)
        content = QVBoxLayout()
        content.setSpacing(3)
        content.setContentsMargins(0, 0, 0, 0)

        meta = QHBoxLayout()
        meta.setSpacing(8)
        name_label = QLabel(name)
        name_label.setStyleSheet("font-weight:600;font-size:12px;color:#8a8f98;")
        meta.addWidget(name_label)
        if timestamp:
            time_label = QLabel(timestamp)
            time_label.setStyleSheet("font-size:11px;color:#a6abb3;")
            meta.addWidget(time_label)
        meta.addStretch(1)
        content.addLayout(meta)

        self.browser = make_md_browser(bubble_style, max_width)
        content.addWidget(self.browser)

        if role == "user":
            row.addStretch(1)
            row.addLayout(content)
            row.addWidget(avatar)
        else:
            row.addWidget(avatar)
            row.addLayout(content, 1)
            row.addStretch(0)

    def set_text(self, text: str) -> None:
        self.browser.setPlainText(text)

    def set_html(self, html: str) -> None:
        self.browser.setHtml(html)
