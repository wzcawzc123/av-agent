"""对话页：需求采集、确认、生成进度、文件下载、会话管理。

UI/UX v2：
- Markdown 渲染气泡（QTextBrowser），链接可点击
- 打字机流式：回复先纯文本渐进显示，完成后转 Markdown
- 确认卡片：CONFIRMING 时把回复摘要解析成槽位表格
- 会话管理：项目下拉切换即回放历史消息；「新对话」一键新建
- 场景徽标：识别场景词在气泡顶部显示
- 专家模式 / Agent 模式（Agent 模式走后端工具循环端点）
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Callable, Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from desktop.api import AvApi, ApiError
from desktop.files import OUTPUT_ROOT, download_file, open_in_folder
from desktop.sse import ChatSseWorker, SseWorker
from desktop.worker import ApiCallThread, run_api

import markdown as md

_SCENE_BADGES = [
    ("会议室", "🏢 会议室"), ("圆桌", "🏢 圆桌会议"), ("培训", "🏫 培训教室"),
    ("报告厅", "🎤 报告厅"), ("礼堂", "🎤 礼堂"), ("剧场", "🎭 剧场"), ("多功能厅", "🎬 多功能厅"),
    ("展厅", "🖼️ 展厅"), ("展馆", "🖼️ 展馆"), ("博物馆", "🏛️ 博物馆"),
    ("指挥中心", "🖥️ 指挥中心"), ("监控", "📹 监控室"), ("调度", "📡 调度室"),
    ("医院", "🏥 医院"), ("校园", "🏫 校园"), ("园区", "🏭 园区"), ("厂", "🏭 厂区"),
]

_BUBBLE_STYLE = {
    "user": {"bg": "#4665EA", "fg": "#FFFFFF", "border": "#4665EA"},
    "system": {"bg": "#E0E1F9", "fg": "#171B2C", "border": "#E0E1F9"},
    "warn": {"bg": "#FFD7F0", "fg": "#2D1228", "border": "#FFD7F0"},
    "err": {"bg": "#FFDAD6", "fg": "#410002", "border": "#FFDAD6"},
    "engine": {"bg": "#DEE0FF", "fg": "#00145B", "border": "#DEE0FF"},
    "ok": {"bg": "#DEE0FF", "fg": "#00145B", "border": "#DEE0FF"},
    "agent": {"bg": "#EBE6EF", "fg": "#1B1B1F", "border": "#EBE6EF"},
    "": {"bg": "#EBE6EF", "fg": "#1B1B1F", "border": "#EBE6EF"},
}

_BUBBLE_STYLE_DARK = {
    "user": {"bg": "#B9C4FF", "fg": "#08208F", "border": "#B9C4FF"},
    "system": {"bg": "#43465B", "fg": "#E0E1F9", "border": "#43465B"},
    "warn": {"bg": "#5D3D56", "fg": "#FFD7F0", "border": "#5D3D56"},
    "err": {"bg": "#93000A", "fg": "#FFDAD6", "border": "#93000A"},
    "engine": {"bg": "#2A47C6", "fg": "#DEE0FF", "border": "#2A47C6"},
    "ok": {"bg": "#2A47C6", "fg": "#DEE0FF", "border": "#2A47C6"},
    "agent": {"bg": "#29292F", "fg": "#E4E1E9", "border": "#29292F"},
    "": {"bg": "#29292F", "fg": "#E4E1E9", "border": "#29292F"},
}


def _bubble_palette(style: str) -> dict:
    from desktop.theme import is_dark

    table = _BUBBLE_STYLE_DARK if is_dark() else _BUBBLE_STYLE
    return table.get(style, table[""])


def _scene_badge(text: str) -> str:
    for keyword, badge in _SCENE_BADGES:
        if keyword in text:
            return badge
    return ""


class ChatPage(QWidget):
    """对话工作台。"""

    def __init__(self, api: AvApi):
        super().__init__()
        self.api = api
        self.current_project: Optional[int] = None
        self._threads: list[ApiCallThread] = []
        self._sse: Optional[SseWorker] = None
        self._typing: Optional[QTextBrowser] = None
        self._typing_buf = ""
        self._typing_timer: Optional[QTimer] = None
        self._build_ui()

    # ---------- UI ----------

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(10)

        # 顶部：会话与模式
        top = QHBoxLayout()
        top.addWidget(QLabel("会话"))
        self.project_combo = QComboBox()
        self.project_combo.setMinimumWidth(260)
        self.project_combo.currentIndexChanged.connect(self._on_project_changed)
        top.addWidget(self.project_combo)
        new_btn = QPushButton("＋ 新对话")
        new_btn.setObjectName("outlined")
        new_btn.clicked.connect(self._new_project)
        top.addWidget(new_btn)
        ingest_btn = QPushButton("📥 智能入库")
        ingest_btn.setObjectName("outlined")
        ingest_btn.setToolTip("上传文件（Excel/Word/PDF/文本），LLM 自动识别为产品清单或知识文档并入库")
        ingest_btn.clicked.connect(self._ingest_file)
        top.addWidget(ingest_btn)
        self.ingest_target = QComboBox()
        self.ingest_target.addItem("自动识别", "auto")
        self.ingest_target.addItem("产品库", "products")
        self.ingest_target.addItem("知识库", "knowledge")
        self.ingest_target.setFixedWidth(96)
        top.addWidget(self.ingest_target)
        refresh_btn = QPushButton("刷新")
        refresh_btn.setObjectName("outlined")
        refresh_btn.clicked.connect(self.refresh_projects)
        top.addWidget(refresh_btn)
        top.addSpacing(16)
        top.addWidget(QLabel("模式"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("🧠 专家模式", "expert")
        self.mode_combo.addItem("🤖 Agent 模式", "agent")
        self.mode_combo.setToolTip(
            "专家模式：按售前流程逐项澄清后确认生成；\n"
            "Agent 模式：模型可自主调用产品库/项目/记忆等工具完成需求"
        )
        top.addWidget(self.mode_combo)
        top.addStretch(1)
        self.model_hint = QLabel("")
        self.model_hint.setObjectName("hint")
        top.addWidget(self.model_hint)
        root.addLayout(top)

        # 消息区
        self.msg_scroll = QScrollArea()
        self.msg_scroll.setWidgetResizable(True)
        self.msg_container = QWidget()
        self.msg_layout = QVBoxLayout(self.msg_container)
        self.msg_layout.setContentsMargins(8, 8, 8, 8)
        self.msg_layout.setSpacing(8)
        self.msg_layout.addStretch(1)
        self.msg_scroll.setWidget(self.msg_container)
        root.addWidget(self.msg_scroll, 1)

        # 确认卡片
        self.confirm_card = QFrame()
        self.confirm_card.setVisible(False)
        card = QVBoxLayout(self.confirm_card)
        card.setContentsMargins(12, 10, 12, 10)
        self.confirm_title = QLabel("📋 需求已完整，请确认以下内容后生成：")
        self.confirm_title.setObjectName("title")
        self.confirm_title.setStyleSheet("font-size: 14px;")
        card.addWidget(self.confirm_title)
        self.confirm_table = QTableWidget(0, 2)
        self.confirm_table.setHorizontalHeaderLabels(["项目", "内容"])
        self.confirm_table.horizontalHeader().setStretchLastSection(True)
        self.confirm_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.confirm_table.setMaximumHeight(180)
        card.addWidget(self.confirm_table)
        gen_btn = QPushButton("✅ 确认并生成交付物")
        gen_btn.clicked.connect(self._start_generate)
        card.addWidget(gen_btn)
        root.addWidget(self.confirm_card)

        # 进度条
        self.progress = QProgressBar()
        self.progress.setVisible(False)
        progress_row = QHBoxLayout()
        progress_row.addWidget(self.progress, 1)
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setObjectName("danger")
        self.cancel_btn.setVisible(False)
        self.cancel_btn.clicked.connect(self._cancel_generate)
        progress_row.addWidget(self.cancel_btn)
        root.addLayout(progress_row)

        # 输入区
        bottom = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText(
            "描述你的需求，例如：为一个 300 平米酒店大堂做会议系统方案，预算 20 万（Enter 发送）"
        )
        self.input.returnPressed.connect(self._send)
        bottom.addWidget(self.input, 1)
        self.send_btn = QPushButton("发送 ➤")
        self.send_btn.clicked.connect(self._send)
        bottom.addWidget(self.send_btn)
        root.addLayout(bottom)

        self.refresh_projects()
        self._append_message("system", "你好，我是音视频售前工作流 Agent。描述你的项目需求，我会逐项澄清并生成方案文档。")

    # ---------- 会话管理 ----------

    def on_show(self) -> None:
        self.refresh_projects(keep_selection=True)
        self._refresh_model_hint()

    def refresh_projects(self, keep_selection: bool = False) -> None:
        self._run_api(lambda: self.api.list_projects(), self._on_projects_loaded)

    def _on_projects_loaded(self, projects: list[dict]) -> None:
        current = self.project_combo.currentData()
        self.project_combo.blockSignals(True)
        self.project_combo.clear()
        self.project_combo.addItem("（新对话，自动创建项目）", None)
        for p in projects:
            self.project_combo.addItem(f"#{p['id']} {p['name']}", p["id"])
        idx = self.project_combo.findData(current)
        self.project_combo.setCurrentIndex(max(idx, 0))
        self.project_combo.blockSignals(False)
        self.current_project = self.project_combo.currentData()
        self._refresh_model_hint()

    def _on_project_changed(self, _idx: int) -> None:
        self.current_project = self.project_combo.currentData()
        self._refresh_model_hint()
        self.confirm_card.setVisible(False)
        # 切换会话 → 回放历史消息
        self._clear_messages()
        if self.current_project:
            self._run_api(
                lambda: self.api.project_messages(self.current_project),
                self._on_history_loaded,
            )

    def _on_history_loaded(self, messages: list[dict]) -> None:
        if not messages:
            self._append_message("system", "（该会话暂无消息，开始描述需求吧）")
            return
        for m in messages:
            role = m.get("role", "")
            text = m.get("text", m.get("content", ""))
            if role == "user":
                self._append_message("user", text)
            else:
                self._append_message("agent", text)

    def _clear_messages(self) -> None:
        # 移除 stretch 之前的所有消息行
        while self.msg_layout.count() > 1:
            item = self.msg_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _new_project(self) -> None:
        from PySide6.QtWidgets import QInputDialog

        name, ok = QInputDialog.getText(self, "新建会话", "会话/项目名称：", text="新项目")
        if not ok or not name.strip():
            return
        self._run_api(lambda: self.api.create_project(name.strip()), self._on_project_created)

    # ---------- LLM 智能入库 ----------

    def _ingest_file(self) -> None:
        from PySide6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getOpenFileName(
            self, "选择要入库的文件", "",
            "支持入库 (*.xlsx *.xlsm *.xls *.docx *.pdf *.txt *.md *.csv)",
        )
        if not path:
            return
        self._set_busy(True)
        self._append_message("system", f"📥 正在智能解析 `{os.path.basename(path)}`…")
        target = self.ingest_target.currentData() or "auto"
        self._run_api(
            lambda: self.api.ingest_file(path, target=target),
            self._on_ingested,
        )

    def _on_ingested(self, data: dict) -> None:
        self._set_busy(False)
        if data.get("need_config"):
            self._append_message("warn", data.get("message", "请先配置模型。"))
            return
        if not data.get("ok"):
            self._append_message("err", data.get("message", "入库失败。"))
            return
        message = data.get("message", "")
        title = data.get("title", "")
        summary = data.get("summary", "")
        preview = data.get("preview") or []
        lines = [f"**{message}**"]
        if title:
            lines.append(f"识别标题：{title}")
        if summary:
            lines.append(f"内容摘要：{summary}")
        if preview and isinstance(preview, list):
            lines.append("\n入库预览：")
            for p in preview[:5]:
                if isinstance(p, dict):
                    if data.get("type") == "products":
                        lines.append(f"- {p.get('name')} | {p.get('model')} | {p.get('brand')} | 市场价 {p.get('market_price')}")
                    else:
                        lines.append(f"- {p.get('title')}：{(p.get('excerpt') or '')[:80]}")
        self._append_message("ok", "\n".join(lines))
        # 刷新产品/知识库页数据（on_show 时会自动刷新）

    def _on_project_created(self, proj: dict) -> None:
        self.refresh_projects()
        self._append_message("system", f"已创建会话 #{proj['id']}，可以直接描述需求开始对话。")

    def _refresh_model_hint(self) -> None:
        try:
            cfg = self.api.get_model_config()
            provider = cfg.get("provider") or ""
            model = cfg.get("model") or ""
            if cfg.get("has_api_key"):
                self.model_hint.setText(f"模型：{provider} / {model}")
            else:
                self.model_hint.setText("⚠ 未配置模型，请到「模型提供商」页配置 API Key")
        except Exception:
            self.model_hint.setText("")

    # ---------- 对话 ----------

    def _send(self) -> None:
        text = self.input.text().strip()
        if not text:
            return
        if self._busy():
            return
        self.input.clear()
        self._append_message("user", text)
        self._set_busy(True)
        project_id = self.current_project
        mode = self.mode_combo.currentData()
        if mode == "agent":
            self._start_agent_stream(text, project_id)
        else:
            self._run_api(
                lambda: self.api.chat(text, project_id=project_id),
                self._on_chat_reply,
            )

    # ---------- Agent 模式（SSE 流式） ----------

    def _start_agent_stream(self, text: str, project_id: Optional[int]) -> None:
        self._agent_bubble = self._make_bubble("agent", "")
        row = QHBoxLayout()
        row.addWidget(self._agent_bubble)
        row.addStretch(1)
        self.msg_layout.insertLayout(self.msg_layout.count() - 1, row)
        worker = ChatSseWorker(
            self.api.base_url,
            {"text": text, "project_id": project_id},
            self,
        )
        worker.token.connect(self._on_agent_token)
        worker.tool.connect(self._on_agent_tool)
        worker.done.connect(self._on_agent_done)
        self._chat_sse = worker
        worker.start()

    def _on_agent_token(self, text: str) -> None:
        bubble = getattr(self, "_agent_bubble", None)
        if bubble is not None:
            bubble.insertPlainText(text)
            self._scroll_to_bottom()

    def _on_agent_tool(self, name: str, result: str) -> None:
        bubble = getattr(self, "_agent_bubble", None)
        if bubble is not None:
            bubble.insertPlainText(f"\n\n🔧 正在调用工具 {name}…\n")
            self._scroll_to_bottom()

    def _on_agent_done(self, need_config: bool, reply: str, pid: int) -> None:
        self._set_busy(False)
        bubble = getattr(self, "_agent_bubble", None)
        if bubble is not None:
            bubble.setHtml(_md_html(reply) if reply else "<i>（无回复）</i>")
            self._agent_bubble = None
        if pid:
            self.current_project = pid
            self._sync_project_combo(pid)
        if need_config:
            self._append_message("warn", reply)
            return
        self._scroll_to_bottom()

    def _on_chat_reply(self, reply: dict) -> None:
        self._set_busy(False)
        agent_reply = reply.get("reply", "")
        status = reply.get("status", "")
        pid = reply.get("project_id")
        if pid:
            self.current_project = pid
            self._sync_project_combo(pid)
        if reply.get("need_config"):
            self._append_message("warn", agent_reply)
            return
        if reply.get("engine"):
            self._append_message("engine", agent_reply)
            files = reply.get("files") or []
            if files:
                self._show_engine_files(files, pid)
            return
        self._typewrite(agent_reply)
        # 需求完整 → 确认卡片
        if status == "CONFIRMING":
            self._show_confirm_card(agent_reply)
        else:
            self.confirm_card.setVisible(False)

    def _sync_project_combo(self, pid: int) -> None:
        for i in range(self.project_combo.count()):
            if self.project_combo.itemData(i) == pid:
                self.project_combo.blockSignals(True)
                self.project_combo.setCurrentIndex(i)
                self.project_combo.blockSignals(False)
                return
        self.refresh_projects()

    # ---------- 确认卡片 ----------

    def _show_confirm_card(self, reply: str) -> None:
        rows = self._parse_summary(reply)
        self.confirm_table.setRowCount(len(rows))
        for i, (k, v) in enumerate(rows):
            self.confirm_table.setItem(i, 0, QTableWidgetItem(k))
            self.confirm_table.setItem(i, 1, QTableWidgetItem(v))
        self.confirm_card.setVisible(True)

    @staticmethod
    def _parse_summary(reply: str) -> list[tuple[str, str]]:
        rows: list[tuple[str, str]] = []
        for line in reply.splitlines():
            line = line.strip()
            if not line:
                continue
            line = re.sub(r"^[-*•]\s*", "", line)
            if "：" in line:
                k, v = line.split("：", 1)
                rows.append((k.strip(), v.strip()))
            elif ":" in line:
                k, v = line.split(":", 1)
                rows.append((k.strip(), v.strip()))
        return rows

    # ---------- 生成 ----------

    def _start_generate(self) -> None:
        pid = self.current_project
        if not pid:
            QMessageBox.information(self, "提示", "请先通过对话采集需求（会自动创建项目）。")
            return
        if self._sse and self._sse.isRunning():
            return
        try:
            result = self.api.generate(pid)
        except ApiError as e:
            QMessageBox.warning(self, "生成失败", e.message)
            return
        task_id = result.get("task_id")
        if not task_id:
            QMessageBox.warning(self, "提示", "需求可能未完整，请继续对话补齐。")
            return
        self.confirm_card.setVisible(False)
        self.progress.setVisible(True)
        self.cancel_btn.setVisible(True)
        self.progress.setValue(0)
        self.progress.setFormat("正在生成 0%")
        self._sse = SseWorker(self.api.base_url, task_id, self)
        self._sse.progress.connect(self._on_progress)
        self._sse.done.connect(self._on_generate_done)
        self._sse.start()

    def _cancel_generate(self) -> None:
        """停止等待生成结果（后端任务无法中断，仅取消前端等待）。"""
        if self._sse is not None and self._sse.isRunning():
            self._sse.stop()
            self._sse.wait(2000)
        self.progress.setVisible(False)
        self.cancel_btn.setVisible(False)
        self._append_message("warn", "已取消等待生成结果；任务可能仍在后台执行，可在「项目」页查看产出文件。")

    def _on_progress(self, percent: int, message: str) -> None:
        self.progress.setValue(percent)
        self.progress.setFormat(f"正在生成 {percent}% · {message}")

    def _on_generate_done(self, success: bool, error: str, result_json: str) -> None:
        self.progress.setVisible(False)
        self.cancel_btn.setVisible(False)
        if not success:
            self._append_message("err", f"生成失败：{error}")
            return
        result = json.loads(result_json or "{}")
        files = result.get("files") or {}
        errors = result.get("errors") or {}
        bom = result.get("bom") or []
        lines = ["✅ 交付物生成完成："]
        downloaded = []
        for kind, path in files.items():
            lines.append(f"- {kind}: {os.path.basename(path)}")
            local = self._download_file(path)
            if local:
                downloaded.append(local)
        for kind, msg in errors.items():
            lines.append(f"- {kind} 失败：{msg}")
        if bom:
            lines.append(f"- BOM {len(bom)} 行")
        self._append_message("ok", "\n".join(lines))
        if downloaded:
            self._show_download_bar(downloaded)

    def _download_file(self, server_path: str) -> Optional[str]:
        try:
            return download_file(self.api, server_path, self.current_project)
        except ApiError as e:
            self._append_message("err", f"下载失败：{e.message}")
            return None

    def _show_download_bar(self, files: list[str]) -> None:
        from desktop.theme import scheme, is_dark

        s = scheme(is_dark())
        bar = QFrame()
        bar.setStyleSheet(
            f"background:{s['primaryContainer']};color:{s['onPrimaryContainer']};"
            "border-radius:12px;"
        )
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(12, 6, 12, 6)
        lay.addWidget(QLabel(f"📥 已下载 {len(files)} 个文件到 {OUTPUT_ROOT}"))
        open_btn = QPushButton("打开文件夹")
        open_btn.setObjectName("outlined")
        open_btn.clicked.connect(lambda: open_in_folder(files[0]))
        lay.addWidget(open_btn)
        self.msg_layout.insertWidget(self.msg_layout.count() - 1, bar)

    def _show_engine_files(self, files: list[str], pid: Optional[int]) -> None:
        downloaded = [self._download_file(f) for f in files]
        downloaded = [f for f in downloaded if f]
        if downloaded:
            self._show_download_bar(downloaded)

    # ---------- 消息渲染（Markdown + 打字机） ----------

    def _typewrite(self, text: str) -> None:
        """打字机流式：纯文本渐进，完成后渲染 Markdown。"""
        bubble = self._make_bubble("agent", text[:1])
        self._typing = bubble
        self._typing_buf = text
        step = max(1, len(text) // 60)
        self._typing_pos = 0

        def tick() -> None:
            if self._typing is None:
                return
            self._typing_pos = min(len(self._typing_buf), self._typing_pos + step)
            self._typing.setPlainText(self._typing_buf[: self._typing_pos] + "▍")
            self._scroll_to_bottom()
            if self._typing_pos >= len(self._typing_buf):
                self._typing_timer.stop()
                self._typing.setHtml(_md_html(self._typing_buf))
                self._typing = None
                self._scroll_to_bottom()

        self._typing_timer = QTimer(self)
        self._typing_timer.timeout.connect(tick)
        self._typing_timer.start(16)

    def _append_message(self, style: str, text: str) -> None:
        if style == "user":
            bubble = self._make_bubble("user", text)
            bubble.setAlignment(Qt.AlignRight)
            row = QHBoxLayout()
            row.addStretch(1)
            row.addWidget(bubble)
        else:
            bubble = self._make_bubble(style if style in _BUBBLE_STYLE else "agent", text)
            badge = _scene_badge(text)
            if badge:
                badge_label = QLabel(badge)
                badge_label.setObjectName("hint")
                row = QVBoxLayout()
                row.addWidget(badge_label)
                row.addWidget(bubble)
            else:
                row = QHBoxLayout()
                row.addWidget(bubble)
                row.addStretch(1)
        self.msg_layout.insertLayout(self.msg_layout.count() - 1, row)
        self._scroll_to_bottom()

    def _make_bubble(self, style: str, text: str) -> QTextBrowser:
        palette = _bubble_palette(style)
        browser = QTextBrowser()
        browser.setReadOnly(True)
        browser.setFrameShape(QTextBrowser.NoFrame)
        browser.setMaximumWidth(820)
        browser.setStyleSheet(
            f"QTextBrowser {{ background:{palette['bg']}; color:{palette['fg']};"
            f" border:1px solid {palette['border']}; border-radius:10px; padding:10px 14px; }}"
        )
        browser.setOpenExternalLinks(True)
        browser.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse)
        browser.setPlainText(text)
        browser.document().setDocumentMargin(4)
        return browser

    def _scroll_to_bottom(self) -> None:
        sb = self.msg_scroll.verticalScrollBar()
        sb.setValue(sb.maximum())

    # ---------- 辅助 ----------

    def _busy(self) -> bool:
        return any(t.isRunning() for t in self._threads)

    def _set_busy(self, busy: bool) -> None:
        self.send_btn.setEnabled(not busy)
        self.input.setEnabled(not busy)

    def _run_api(self, fn: Callable[[], Any], ok: Callable[[Any], None]) -> None:
        run_api(self, self._threads, fn, ok, err=self._on_api_error)

    def _on_api_error(self, message: str) -> None:
        self._set_busy(False)
        self._append_message("err", f"出错：{message}")


def _md_html(text: str) -> str:
    """Markdown → HTML（含表格/列表/代码块），链接新窗口打开。"""
    body = md.markdown(text, extensions=["extra", "nl2br"])
    return (
        "<style>"
        "table{border-collapse:collapse;margin:8px 0}td,th{border:1px solid #d9dde3;padding:4px 8px}"
        "code{background:#f0f2f5;padding:1px 4px;border-radius:4px}"
        "pre{background:#f7f8fa;padding:8px;border-radius:6px}"
        "h1,h2,h3{font-size:1.15em}"
        "a{color:#0066ff}"
        "</style>" + body
    )
