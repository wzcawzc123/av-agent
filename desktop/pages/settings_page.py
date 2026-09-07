"""设置页：更新检查、访问信息。"""

from __future__ import annotations

import os
import socket

from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from desktop.api import AvApi
from desktop.files import open_in_folder
from desktop.theme import apply_theme, load_theme_pref, save_theme_pref
from desktop.worker import ApiCallThread, run_api


def _lan_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


class SettingsPage(QWidget):
    def __init__(self, api: AvApi):
        super().__init__()
        self.api = api
        self._threads: list[ApiCallThread] = []
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(12)

        title = QLabel("设置")
        title.setObjectName("title")
        root.addWidget(title)

        box = QWidget()
        form = QFormLayout(box)

        self.theme_combo = QComboBox()
        self.theme_combo.addItem("跟随系统", None)
        self.theme_combo.addItem("浅色", False)
        self.theme_combo.addItem("深色", True)
        pref = load_theme_pref()
        self.theme_combo.setCurrentIndex(self.theme_combo.findData(pref))
        self.theme_combo.currentIndexChanged.connect(self._on_theme_change)
        form.addRow("主题", self.theme_combo)
        form.addRow("", QLabel(""))

        try:
            health = self.api.health()
            version = health.get("version", "?")
        except Exception:
            version = "?"
        self.version_label = QLabel(version)
        form.addRow("服务版本", self.version_label)

        try:
            from app.config import settings as app_settings

            port = getattr(app_settings, "PORT", 8000)
            token = getattr(app_settings, "ACCESS_TOKEN", "")
        except Exception:
            port, token = 8000, ""
        base = self.api.base_url
        self.url_label = QLabel(base)
        form.addRow("本机访问地址", self.url_label)
        self.lan_label = QLabel(f"http://{_lan_ip()}:{port}")
        form.addRow("局域网访问地址", self.lan_label)
        self.token_label = QLabel(token if token else "（自动生成，见 data/access_token.txt）")
        form.addRow("访问口令", self.token_label)

        output_hint = QLabel("生成文件默认下载到：")
        form.addRow(output_hint, QLabel(os.path.join(os.path.expanduser("~"), "AVAgent 输出")))

        root.addWidget(box)

        ops = QHBoxLayout()
        open_out = QPushButton("打开输出文件夹")
        open_out.clicked.connect(lambda: open_in_folder(
            os.path.join(os.path.expanduser("~"), "AVAgent 输出")))
        ops.addWidget(open_out)
        mem_view = QPushButton("查看记忆")
        mem_view.setObjectName("outlined")
        mem_view.clicked.connect(self._view_memory)
        ops.addWidget(mem_view)
        mem_edit = QPushButton("编辑记忆")
        mem_edit.setObjectName("outlined")
        mem_edit.clicked.connect(self._edit_memory)
        ops.addWidget(mem_edit)
        mem_clear = QPushButton("清空记忆")
        mem_clear.setObjectName("danger")
        mem_clear.clicked.connect(self._clear_memory)
        ops.addWidget(mem_clear)
        check_btn = QPushButton("检查更新")
        check_btn.setObjectName("outlined")
        check_btn.clicked.connect(self._check_update)
        ops.addWidget(check_btn)
        ops.addStretch(1)
        root.addLayout(ops)
        root.addStretch(1)

        about = QLabel(
            "AV Agent 桌面版：音视频售前工作流 Agent。\n"
            "对话采集需求 → 确认 → 生成 Word 方案 / Excel 偏离表 / PPT；支持产品库、模板库、招标改单、模型提供商自定义。"
        )
        about.setObjectName("hint")
        about.setWordWrap(True)
        root.addWidget(about)

    def _on_theme_change(self) -> None:
        from PySide6.QtWidgets import QApplication

        pref = self.theme_combo.currentData()
        save_theme_pref(pref)
        apply_theme(QApplication.instance(), pref)

    # ---------- 全局记忆 ----------

    @staticmethod
    def _memory_file() -> str:
        try:
            from app.config import settings as app_settings

            return os.path.join(app_settings.DATA_DIR, "MEMORY.md")
        except Exception:
            return os.path.join(os.path.expanduser("~"), ".avagent_MEMORY.md")

    def _read_memory(self) -> str:
        path = self._memory_file()
        try:
            if os.path.exists(path):
                with open(path, encoding="utf-8") as f:
                    return f.read().strip()
        except Exception:
            pass
        return ""

    def _view_memory(self) -> None:
        content = self._read_memory() or "（暂无记忆——对话中 Agent 可自动写入客户偏好、常用品牌等）"
        from PySide6.QtWidgets import QMessageBox

        box = QMessageBox(self)
        box.setWindowTitle("跨会话记忆（MEMORY.md）")
        box.setText(content[:6000])
        box.setStandardButtons(QMessageBox.Ok)
        box.exec()

    def _edit_memory(self) -> None:
        from PySide6.QtWidgets import QDialog, QDialogButtonBox, QPlainTextEdit, QVBoxLayout

        dlg = QDialog(self)
        dlg.setWindowTitle("编辑跨会话记忆")
        dlg.resize(560, 420)
        lay = QVBoxLayout(dlg)
        editor = QPlainTextEdit()
        editor.setPlainText(self._read_memory())
        lay.addWidget(editor)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        lay.addWidget(buttons)
        if dlg.exec() != QDialog.Accepted:
            return
        try:
            os.makedirs(os.path.dirname(self._memory_file()), exist_ok=True)
            with open(self._memory_file(), "w", encoding="utf-8") as f:
                f.write(editor.toPlainText().strip())
            QMessageBox.information(self, "完成", "记忆已保存。")
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "保存失败", str(e))

    def _clear_memory(self) -> None:
        if QMessageBox.question(self, "清空记忆", "确定清空全部跨会话记忆吗？") != QMessageBox.Yes:
            return
        try:
            if os.path.exists(self._memory_file()):
                os.remove(self._memory_file())
            QMessageBox.information(self, "完成", "记忆已清空。")
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "清空失败", str(e))

    def _check_update(self) -> None:
        run_api(self, self._threads, self.api.update_check, self._on_update)

    def _on_update(self, data: dict) -> None:
        if data.get("has_update"):
            latest = data.get("latest_version", "")
            notes = (data.get("notes") or "")[:400]
            url = data.get("download_url", "")
            msg = f"发现新版本 {latest}（当前 {data.get('current_version', '')}）"
            if notes:
                msg += f"\n\n更新说明：\n{notes}"
            if url:
                msg += f"\n\n下载：{url}"
            QMessageBox.information(self, "检查更新", msg)
        else:
            QMessageBox.information(
                self, "检查更新",
                f"当前已是最新版本（{data.get('current_version', '')}）。",
            )
