"""招标改单页：上传解析、快照、行编辑、确认转 BOM。"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from desktop.api import AvApi
from desktop.files import download_many, open_in_folder
from desktop.worker import ApiCallThread, run_api

COLUMNS = ["名称", "品牌", "型号", "数量", "状态", "匹配型号", "得分", "备注"]


class TenderPage(QWidget):
    def __init__(self, api: AvApi):
        super().__init__()
        self.api = api
        self._threads: list[ApiCallThread] = []
        self._current_project: Optional[int] = None
        self._snapshots: list[str] = []
        self._rows: list[dict] = []
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(10)

        title = QLabel("招标改单")
        title.setObjectName("title")
        root.addWidget(title)

        bar = QHBoxLayout()
        bar.addWidget(QLabel("项目"))
        self.project_combo = QComboBox()
        self.project_combo.setMinimumWidth(260)
        self.project_combo.currentIndexChanged.connect(self._on_project_changed)
        bar.addWidget(self.project_combo)
        upload_btn = QPushButton("上传招标文件")
        upload_btn.clicked.connect(self._upload)
        bar.addWidget(upload_btn)
        bar.addWidget(QLabel("快照"))
        self.snapshot_combo = QComboBox()
        self.snapshot_combo.setMinimumWidth(180)
        self.snapshot_combo.currentIndexChanged.connect(self._on_snapshot_changed)
        bar.addWidget(self.snapshot_combo)
        refresh_btn = QPushButton("刷新")
        refresh_btn.setObjectName("outlined")
        refresh_btn.clicked.connect(self._refresh_snapshots)
        bar.addWidget(refresh_btn)
        bar.addStretch(1)
        root.addLayout(bar)

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        root.addWidget(self.table, 1)

        ops = QHBoxLayout()
        edit_btn = QPushButton("编辑选中行（品牌/型号/备注）")
        edit_btn.setObjectName("outlined")
        edit_btn.clicked.connect(self._edit_row)
        ops.addWidget(edit_btn)
        confirm_btn = QPushButton("确认改单 → 生成方案清单")
        confirm_btn.clicked.connect(self._confirm)
        ops.addWidget(confirm_btn)
        ops.addStretch(1)
        root.addLayout(ops)

    # ---------- 数据 ----------

    def on_show(self) -> None:
        run_api(self, self._threads, self.api.list_projects, self._load_projects)

    def _load_projects(self, projects: list[dict]) -> None:
        current = self._current_project
        self.project_combo.blockSignals(True)
        self.project_combo.clear()
        self.project_combo.addItem("（上传时自动创建招标项目）", None)
        for p in projects:
            self.project_combo.addItem(f"#{p['id']} {p['name']}", p["id"])
        if current is not None:
            idx = self.project_combo.findData(current)
            self.project_combo.setCurrentIndex(max(idx, 0))
        self.project_combo.blockSignals(False)
        self._on_project_changed()

    def _on_project_changed(self, _idx: int = 0) -> None:
        self._current_project = self.project_combo.currentData()
        self._refresh_snapshots()

    def _refresh_snapshots(self) -> None:
        pid = self._current_project
        self.snapshot_combo.clear()
        if not pid:
            return
        run_api(self, self._threads, lambda: self.api.tender_snapshots(pid), self._load_snapshots)

    def _load_snapshots(self, data: dict) -> None:
        snaps = data.get("snapshots", [])
        self._snapshots = [s["snapshot"] for s in snaps]
        self.snapshot_combo.blockSignals(True)
        self.snapshot_combo.clear()
        for s in snaps:
            self.snapshot_combo.addItem(f"{s['snapshot']}（{s['rows']} 行）", s["snapshot"])
        self.snapshot_combo.blockSignals(False)
        if self._snapshots:
            self.snapshot_combo.setCurrentIndex(0)

    def _on_snapshot_changed(self, _idx: int = 0) -> None:
        pid = self._current_project
        snap = self.snapshot_combo.currentData()
        if not pid or not snap:
            self.table.setRowCount(0)
            return
        run_api(self, self._threads, lambda: self.api.tender_snapshot(pid, snap), self._load_rows)

    def _load_rows(self, data: dict) -> None:
        self._rows = data.get("rows", [])
        self.table.setRowCount(len(self._rows))
        status_names = {
            "matched": "已匹配", "partial": "部分匹配", "no_match": "未匹配",
            "merged": "已合并", "extra": "额外项", "new": "新品",
        }
        for i, r in enumerate(self._rows):
            status_name = status_names.get(r.get("status", ""), r.get("status", ""))
            vals = [
                r.get("name", ""), r.get("brand", ""), r.get("model", ""),
                r.get("qty", ""), status_name,
                r.get("matched_model", ""), r.get("score", ""), r.get("remark", ""),
            ]
            status_color = {
                "matched": "#00a854", "merged": "#00a854", "new": "#00a854",
                "partial": "#d48806", "extra": "#d48806", "no_match": "#d93025",
            }.get(r.get("status", ""), "#86909c")
            for j, v in enumerate(vals):
                item = QTableWidgetItem("" if v is None else str(v))
                if j == 0:
                    item.setData(Qt.UserRole, r.get("source_idx", 0))
                if j == 4:  # 状态列着色
                    item.setForeground(Qt.GlobalColor.darkGreen if status_color == "#00a854"
                                       else Qt.GlobalColor.darkYellow if status_color == "#d48806"
                                       else Qt.GlobalColor.darkRed if status_color == "#d93025"
                                       else Qt.GlobalColor.darkGray)
                self.table.setItem(i, j, item)

    # ---------- 操作 ----------

    def _upload(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "选择招标文件", "", "招标文件 (*.xlsx *.xlsm *.docx *.pdf)",
        )
        if not path:
            return
        pid = self._current_project or 0
        run_api(
            self, self._threads,
            lambda: self.api.upload_tender(path, project_id=pid),
            self._on_uploaded,
        )

    def _on_uploaded(self, data: dict) -> None:
        self._current_project = data.get("project_id")
        # 刷新项目下拉选中
        if self.project_combo.findData(self._current_project) < 0:
            run_api(self, self._threads, self.api.list_projects, self._load_projects)
        merged = data.get("merged", 0)
        items = data.get("items", [])
        msg = f"解析完成：{len(items)} 行"
        if merged:
            msg += f"，合并 {merged} 行"
        QMessageBox.information(self, "完成", msg)
        self._refresh_snapshots()

    def _selected_row(self) -> Optional[tuple[dict, int]]:
        row = self.table.currentRow()
        if row < 0 or row >= len(self._rows):
            return None
        return self._rows[row], self._rows[row].get("source_idx", 0)

    def _edit_row(self) -> None:
        sel = self._selected_row()
        if not sel:
            QMessageBox.information(self, "提示", "请先选中一行。")
            return
        row, source_idx = sel
        brand, ok1 = QInputDialog.getText(self, "编辑行", "品牌：", text=row.get("brand", ""))
        if not ok1:
            return
        model, ok2 = QInputDialog.getText(self, "编辑行", "型号：", text=row.get("model", ""))
        if not ok2:
            return
        remark, ok3 = QInputDialog.getText(self, "编辑行", "备注：", text=row.get("remark", ""))
        if not ok3:
            return
        pid = self._current_project
        if not pid:
            return
        run_api(
            self, self._threads,
            lambda: self.api.tender_edit_row(pid, source_idx, brand=brand, model=model, remark=remark),
            lambda _r: self._on_snapshot_changed(),
        )

    def _confirm(self) -> None:
        pid = self._current_project
        snap = self.snapshot_combo.currentData()
        if not pid or not snap:
            QMessageBox.information(self, "提示", "请先上传招标文件并确认快照。")
            return
        if QMessageBox.question(self, "确认改单", "确认后写入项目 BOM 并生成方案清单 Excel，继续吗？") != QMessageBox.Yes:
            return
        run_api(
            self, self._threads,
            lambda: self.api.tender_confirm(pid, snap),
            self._on_confirmed,
        )

    def _on_confirmed(self, data: dict) -> None:
        files = data.get("files", {})
        excel = files.get("excel", "")
        msg = f"改单已确认：{len(data.get('rows', []))} 行 BOM"
        if excel:
            try:
                local = download_many(self.api, [excel], self._current_project)
                if local:
                    msg += f"\n方案清单已下载：{local[0]}"
                    open_in_folder(local[0])
            except Exception:
                pass
        QMessageBox.information(self, "完成", msg)
