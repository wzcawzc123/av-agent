"""知识库页：文档登记、列表、删除。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from desktop.api import AvApi
from desktop.worker import ApiCallThread, run_api

COLUMNS = ["ID", "标题", "类型", "文件路径", "摘要"]


class KnowledgeDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("登记知识文档")
        self.setMinimumWidth(460)
        form = QFormLayout(self)
        self.title = QLineEdit()
        form.addRow("标题 *", self.title)
        self.doc_type = QLineEdit()
        self.doc_type.setPlaceholderText("如：产品资料 / 案例 / 规范")
        form.addRow("类型", self.doc_type)
        self.path = QLineEdit()
        self.path.setPlaceholderText("文件路径（可选，仅作展示）")
        form.addRow("文件路径", self.path)
        self.excerpt = QTextEdit()
        self.excerpt.setPlaceholderText("摘要 / 内容要点（检索会按此匹配）")
        self.excerpt.setFixedHeight(120)
        form.addRow("摘要", self.excerpt)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)


class KnowledgePage(QWidget):
    def __init__(self, api: AvApi):
        super().__init__()
        self.api = api
        self._threads: list[ApiCallThread] = []
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(10)

        title = QLabel("知识库")
        title.setObjectName("title")
        root.addWidget(title)

        hint = QLabel("登记公司产品资料/案例等文档，对话时关键词检索自动注入，辅助需求澄清与方案生成。")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        root.addWidget(hint)

        bar = QHBoxLayout()
        add_btn = QPushButton("登记文档")
        add_btn.clicked.connect(self._add)
        bar.addWidget(add_btn)
        refresh_btn = QPushButton("刷新")
        refresh_btn.setObjectName("outlined")
        refresh_btn.clicked.connect(self.on_show)
        bar.addWidget(refresh_btn)
        bar.addStretch(1)
        root.addLayout(bar)

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        root.addWidget(self.table, 1)

        btns = QHBoxLayout()
        del_btn = QPushButton("删除选中文档")
        del_btn.setObjectName("danger")
        del_btn.clicked.connect(self._delete)
        btns.addWidget(del_btn)
        btns.addStretch(1)
        root.addLayout(btns)

    def on_show(self) -> None:
        run_api(self, self._threads, self.api.list_knowledge, self._load)

    def _load(self, data: dict) -> None:
        docs = data.get("documents", [])
        self.table.setRowCount(len(docs))
        for i, d in enumerate(docs):
            vals = [
                d.get("id", ""), d.get("title", ""), d.get("doc_type", ""),
                d.get("file_path", ""), d.get("excerpt", ""),
            ]
            for j, v in enumerate(vals):
                item = QTableWidgetItem("" if v is None else str(v))
                if j == 0:
                    item.setData(Qt.UserRole, d.get("id"))
                self.table.setItem(i, j, item)

    def _add(self) -> None:
        dlg = KnowledgeDialog(self)
        if dlg.exec() != QDialog.Accepted:
            return
        title = dlg.title.text().strip()
        if not title:
            QMessageBox.warning(self, "提示", "标题不能为空。")
            return
        run_api(
            self, self._threads,
            lambda: self.api.register_knowledge(
                title=title,
                doc_type=dlg.doc_type.text().strip(),
                file_path=dlg.path.text().strip(),
                excerpt=dlg.excerpt.toPlainText().strip(),
            ),
            lambda _r: (QMessageBox.information(self, "完成", "文档已登记。"), self.on_show()),
        )

    def _delete(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        doc_id = self.table.item(row, 0).data(Qt.UserRole)
        if QMessageBox.question(self, "删除", "确定删除该文档吗？") != QMessageBox.Yes:
            return
        run_api(self, self._threads, lambda: self.api.delete_knowledge(doc_id), lambda _r: self.on_show())
