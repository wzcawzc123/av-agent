"""模板库页：列表、上传、删除。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from desktop.api import AvApi
from desktop.worker import ApiCallThread, run_api

COLUMNS = ["ID", "名称", "类型", "面积", "场景", "描述"]


class TemplatesPage(QWidget):
    def __init__(self, api: AvApi):
        super().__init__()
        self.api = api
        self._threads: list[ApiCallThread] = []
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(10)

        title = QLabel("模板库")
        title.setObjectName("title")
        root.addWidget(title)

        bar = QHBoxLayout()
        upload_btn = QPushButton("上传模板文件")
        upload_btn.clicked.connect(self._upload)
        bar.addWidget(upload_btn)
        ingest_cfg_btn = QPushButton("📐 上传配置模板")
        ingest_cfg_btn.setObjectName("outlined")
        ingest_cfg_btn.setToolTip(
            "上传 100/150/200 平… 会议室配置表（Excel/Word/PDF），LLM 自动解析面积/场景/系统/设备行入库，"
            "生成方案时按面积+场景自动匹配"
        )
        ingest_cfg_btn.clicked.connect(self._ingest_config)
        bar.addWidget(ingest_cfg_btn)
        bar.addWidget(QLabel("匹配测试"))
        self.match_scene = QLineEdit()
        self.match_scene.setPlaceholderText("场景，如：会议室")
        self.match_scene.setFixedWidth(120)
        bar.addWidget(self.match_scene)
        self.match_brand = QLineEdit()
        self.match_brand.setPlaceholderText("品牌，如：MAXHUB")
        self.match_brand.setFixedWidth(120)
        bar.addWidget(self.match_brand)
        match_btn = QPushButton("测试匹配")
        match_btn.setObjectName("outlined")
        match_btn.clicked.connect(self._match_test)
        bar.addWidget(match_btn)
        refresh_btn = QPushButton("刷新")
        refresh_btn.setObjectName("outlined")
        refresh_btn.clicked.connect(self.on_show)
        bar.addWidget(refresh_btn)
        hint = QLabel("支持：文字方案 docx / PPT 母版 pptx / 常规配置 Excel")
        hint.setObjectName("hint")
        bar.addWidget(hint)
        bar.addStretch(1)
        root.addLayout(bar)

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        root.addWidget(self.table, 1)

        btns = QHBoxLayout()
        del_btn = QPushButton("删除选中模板")
        del_btn.setObjectName("danger")
        del_btn.clicked.connect(self._delete)
        btns.addWidget(del_btn)
        btns.addStretch(1)
        root.addLayout(btns)

    def on_show(self) -> None:
        run_api(self, self._threads, self.api.list_templates, self._load)

    def _load(self, templates: list[dict]) -> None:
        self.table.setRowCount(len(templates))
        for i, t in enumerate(templates):
            vals = [
                t.get("id", ""), t.get("name", ""), t.get("type", ""),
                t.get("area", ""), t.get("scene", ""), t.get("description", ""),
            ]
            for j, v in enumerate(vals):
                item = QTableWidgetItem("" if v is None else str(v))
                if j == 0:
                    item.setData(Qt.UserRole, t.get("id"))
                self.table.setItem(i, j, item)

    def _match_test(self) -> None:
        scene = self.match_scene.text().strip()
        brand = self.match_brand.text().strip()
        run_api(
            self, self._threads,
            lambda: self.api.templates_doc_match(scene=scene, brand=brand),
            self._on_match,
        )

    def _on_match(self, data: dict) -> None:
        tid = data.get("template_id")
        if tid is None:
            QMessageBox.information(self, "匹配结果", "未匹配到 doc/ppt 模板（将使用默认模板）。")
            return
        QMessageBox.information(
            self, "匹配结果",
            f"匹配到模板 #{tid}\n类型：{data.get('type', '')}\n路径：{data.get('file_path', '')}",
        )

    def _ingest_config(self) -> None:
        from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QSpinBox

        dlg = QDialog(self)
        dlg.setWindowTitle("上传配置模板（LLM 智能解析）")
        dlg.setMinimumWidth(420)
        form = QFormLayout(dlg)
        path_edit = QLineEdit()
        path_edit.setReadOnly(True)
        browse = QPushButton("选择文件…")
        browse.setObjectName("outlined")

        def pick():
            p, _ = QFileDialog.getOpenFileName(
                dlg, "选择配置表", "", "配置表 (*.xlsx *.xlsm *.xls *.docx *.pdf *.txt *.md)")
            if p:
                path_edit.setText(p)

        browse.clicked.connect(pick)
        row = QHBoxLayout()
        row.addWidget(path_edit, 1)
        row.addWidget(browse)
        form.addRow("配置文件", row)
        name_edit = QLineEdit()
        name_edit.setPlaceholderText("如：100㎡会议室常规配置（可留空自动命名）")
        form.addRow("模板名称", name_edit)
        area_spin = QSpinBox()
        area_spin.setRange(0, 100000)
        area_spin.setSuffix(" ㎡")
        area_spin.setSpecialValueText("自动识别")
        form.addRow("面积", area_spin)
        scene_edit = QLineEdit()
        scene_edit.setPlaceholderText("如：会议室（可留空自动识别）")
        form.addRow("场景", scene_edit)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        form.addRow(buttons)
        if dlg.exec() != QDialog.Accepted or not path_edit.text():
            return
        run_api(
            self, self._threads,
            lambda: self.api.templates_ingest(
                path_edit.text(), name=name_edit.text().strip(),
                area=area_spin.value(), scene=scene_edit.text().strip()),
            self._on_ingested,
        )

    def _on_ingested(self, data: dict) -> None:
        if data.get("need_config"):
            QMessageBox.warning(self, "提示", data.get("message", "请先配置模型。"))
            return
        if not data.get("ok"):
            QMessageBox.warning(self, "解析失败", data.get("message", "未知错误"))
            return
        QMessageBox.information(self, "完成", data.get("message", "已入库"))
        self.on_show()

    def _upload(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "选择模板文件", "",
            "模板文件 (*.docx *.pptx *.xls *.xlsx)",
        )
        if not path:
            return
        run_api(
            self, self._threads,
            lambda: self.api.upload_template(path),
            lambda r: (QMessageBox.information(self, "完成", f"模板已上传：{r}"), self.on_show()),
        )

    def _delete(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        tid = self.table.item(row, 0).data(Qt.UserRole)
        if QMessageBox.question(self, "删除", "确定删除该模板吗？") != QMessageBox.Yes:
            return
        run_api(self, self._threads, lambda: self.api.delete_template(tid), lambda _r: self.on_show())
