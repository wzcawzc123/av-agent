"""项目页：项目列表、产出文件、报价 BOM、消息历史。"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from desktop.api import AvApi, ApiError
from desktop.files import download_many, open_in_folder
from desktop.worker import ApiCallThread, run_api

BOM_COLUMNS = ["名称", "品牌", "型号", "系统", "类型", "规格", "数量", "单位", "市场价", "底价", "备注"]


class ProjectsPage(QWidget):
    def __init__(self, api: AvApi):
        super().__init__()
        self.api = api
        self._threads: list[ApiCallThread] = []
        self._current_id: Optional[int] = None
        self._all_projects: list[dict] = []
        self._build_ui()

    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)

        splitter = QSplitter(Qt.Horizontal)

        # 左：项目列表
        left = QWidget()
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(0, 0, 8, 0)
        title = QLabel("项目列表")
        title.setObjectName("title")
        left_lay.addWidget(title)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 搜索项目名称…")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self._filter_projects)
        left_lay.addWidget(self.search_input)
        self.project_list = QListWidget()
        self.project_list.currentItemChanged.connect(self._on_select)
        left_lay.addWidget(self.project_list, 1)
        del_btn = QPushButton("删除选中项目")
        del_btn.setObjectName("danger")
        del_btn.clicked.connect(self._delete_project)
        left_lay.addWidget(del_btn)
        splitter.addWidget(left)

        # 右：详情
        right = QWidget()
        right_lay = QVBoxLayout(right)
        right_lay.setContentsMargins(8, 0, 0, 0)
        self.detail_title = QLabel("选择一个项目")
        self.detail_title.setObjectName("title")
        right_lay.addWidget(self.detail_title)

        self.tabs = QTabWidget()
        self.tabs.setVisible(False)

        # 产出文件 tab
        files_tab = QWidget()
        files_lay = QVBoxLayout(files_tab)
        self.files_table = QTableWidget(0, 2)
        self.files_table.setHorizontalHeaderLabels(["文件", "类型"])
        self.files_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.files_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.files_table.setSelectionBehavior(QTableWidget.SelectRows)
        files_lay.addWidget(self.files_table, 1)
        files_btns = QHBoxLayout()
        dl_all = QPushButton("下载全部文件")
        dl_all.clicked.connect(self._download_all)
        files_btns.addWidget(dl_all)
        open_btn = QPushButton("打开输出文件夹")
        open_btn.setObjectName("outlined")
        open_btn.clicked.connect(self._open_output)
        files_btns.addWidget(open_btn)
        files_btns.addStretch(1)
        files_lay.addLayout(files_btns)
        self.tabs.addTab(files_tab, "产出文件")

        # BOM tab
        bom_tab = QWidget()
        bom_lay = QVBoxLayout(bom_tab)
        self.bom_table = QTableWidget(0, len(BOM_COLUMNS))
        self.bom_table.setHorizontalHeaderLabels(BOM_COLUMNS)
        self.bom_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.bom_table.setSelectionBehavior(QTableWidget.SelectRows)
        # 仅名称/数量/市场价/底价/备注可编辑
        self.bom_table.setEditTriggers(QTableWidget.DoubleClicked | QTableWidget.EditKeyPressed)
        self.bom_table.itemChanged.connect(self._on_bom_edited)
        self._loading_bom = False
        bom_lay.addWidget(self.bom_table, 1)
        self.bom_total = QLabel("合计：0.00 元")
        self.bom_total.setObjectName("ok")
        bom_lay.addWidget(self.bom_total)
        bom_btns = QHBoxLayout()
        add_row = QPushButton("＋ 添加行")
        add_row.setObjectName("outlined")
        add_row.clicked.connect(self._add_bom_row)
        bom_btns.addWidget(add_row)
        del_row = QPushButton("删除选中行")
        del_row.setObjectName("danger")
        del_row.clicked.connect(self._del_bom_row)
        bom_btns.addWidget(del_row)
        save_btn = QPushButton("💾 保存并重出 Excel 报价表")
        save_btn.clicked.connect(self._save_bom)
        bom_btns.addWidget(save_btn)
        save_tpl = QPushButton("存为配置模板")
        save_tpl.setObjectName("outlined")
        save_tpl.clicked.connect(self._save_as_template)
        bom_btns.addWidget(save_tpl)
        bom_btns.addStretch(1)
        bom_lay.addLayout(bom_btns)
        self.tabs.addTab(bom_tab, "报价 BOM")

        # 消息历史 tab
        self.msg_browser = QTextBrowser()
        self.tabs.addTab(self.msg_browser, "消息历史")

        # 方案/报价记录 tab
        self.record_browser = QTextBrowser()
        self.tabs.addTab(self.record_browser, "方案/报价记录")

        right_lay.addWidget(self.tabs, 1)
        splitter.addWidget(right)
        splitter.setSizes([280, 900])
        root.addWidget(splitter)

    # ---------- 生命周期 ----------

    def on_show(self) -> None:
        run_api(self, self._threads, self.api.list_projects, self._load_projects)

    def _load_projects(self, projects: list[dict]) -> None:
        self._all_projects = projects
        current = self._current_id
        keyword = self.search_input.text().strip().lower()
        filtered = [p for p in projects
                    if not keyword or keyword in str(p["name"]).lower()]
        self.project_list.blockSignals(True)
        self.project_list.clear()
        for p in filtered:
            item = QListWidgetItem(f"#{p['id']} {p['name']}")
            item.setData(Qt.UserRole, p["id"])
            self.project_list.addItem(item)
        if current is not None:
            for i in range(self.project_list.count()):
                if self.project_list.item(i).data(Qt.UserRole) == current:
                    self.project_list.setCurrentRow(i)
                    break
        self.project_list.blockSignals(False)
        if self.project_list.currentItem() is None and self.project_list.count() > 0:
            self.project_list.setCurrentRow(0)

    def _filter_projects(self, _text: str) -> None:
        self._load_projects(self._all_projects)

    def _on_select(self, current: Optional[QListWidgetItem], _prev: Optional[QListWidgetItem]) -> None:
        if current is None:
            return
        pid = current.data(Qt.UserRole)
        self._current_id = pid
        self.tabs.setVisible(True)
        run_api(self, self._threads, lambda: self.api.get_project(pid), self._load_detail)

    def _load_detail(self, project: dict) -> None:
        self.detail_title.setText(f"项目 #{project['id']}：{project.get('name', '')}（状态 {project.get('status', '')}）")
        pid = project["id"]
        run_api(self, self._threads, lambda: self.api.project_files(pid), self._load_files)
        run_api(self, self._threads, lambda: self.api.project_bom(pid), self._load_bom)
        run_api(self, self._threads, lambda: self.api.project_messages(pid), self._load_messages)
        run_api(self, self._threads, lambda: self.api.project_solutions(pid), self._load_solutions)
        run_api(self, self._threads, lambda: self.api.project_quotations(pid), self._load_quotations)

    def _load_solutions(self, data: dict) -> None:
        self._solutions = data.get("solutions", [])

    def _load_quotations(self, data: dict) -> None:
        self._quotations = data.get("quotations", [])
        self._render_records()

    def _render_records(self) -> None:
        lines = ["📄 方案记录"]
        sols = getattr(self, "_solutions", [])
        if not sols:
            lines.append("  （暂无）")
        for s in sols:
            files = s.get("files") or []
            lines.append(f"- {s.get('title', '方案')}  [{s.get('status', '')}]  {s.get('created_at', '')[:16]}")
            for f in files:
                lines.append(f"    · {f}")
        lines.append("")
        lines.append("💰 报价记录")
        quots = getattr(self, "_quotations", [])
        if not quots:
            lines.append("  （暂无）")
        for q in quots:
            amount = q.get("total_amount")
            amount_txt = f"{amount:,.2f} 元" if isinstance(amount, (int, float)) else "—"
            lines.append(f"- {q.get('title', '报价')}  合计 {amount_txt}  {q.get('created_at', '')[:16]}")
        self.record_browser.setPlainText("\n".join(lines))

    def _load_files(self, data: dict) -> None:
        files = data.get("files", [])
        self.files_table.setRowCount(len(files))
        for i, f in enumerate(files):
            name_item = QTableWidgetItem(f.get("name", ""))
            name_item.setData(Qt.UserRole, f.get("path", ""))
            self.files_table.setItem(i, 0, name_item)
            self.files_table.setItem(i, 1, QTableWidgetItem(f.get("kind", "")))
        if not files:
            self.files_table.setRowCount(1)
            self.files_table.setItem(0, 0, QTableWidgetItem("（暂无产出文件，先到「对话」页生成）"))

    def _load_bom(self, data: dict) -> None:
        rows = data.get("rows", [])
        self._loading_bom = True
        self.bom_table.setRowCount(len(rows))
        keys = ["name", "brand", "model", "system", "type", "spec", "qty", "unit", "market_price", "base_price", "note"]
        for i, row in enumerate(rows):
            for j, key in enumerate(keys):
                val = row.get(key, "")
                item = QTableWidgetItem(str(val) if val not in (None, "") else "")
                if key in ("qty", "market_price", "base_price"):
                    item.setData(Qt.UserRole, key)
                if j not in (0, 6, 8, 9, 10):
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.bom_table.setItem(i, j, item)
        self._loading_bom = False
        self._recalc_bom_total()

    # ---------- BOM 编辑器 ----------

    def _on_bom_edited(self, _item) -> None:
        if getattr(self, "_loading_bom", False):
            return
        self._recalc_bom_total()

    def _recalc_bom_total(self) -> None:
        total = 0.0
        for i in range(self.bom_table.rowCount()):
            qty_item = self.bom_table.item(i, 6)
            price_item = self.bom_table.item(i, 8)
            try:
                qty = float(qty_item.text() or 0) if qty_item else 0
            except ValueError:
                qty = 0
            try:
                price = float(price_item.text() or 0) if price_item else 0
            except ValueError:
                price = 0
            total += qty * price
        self.bom_total.setText(f"💰 合计（市场价）：{total:,.2f} 元")

    def _collect_bom_rows(self) -> list[dict]:
        keys = ["name", "brand", "model", "system", "type", "spec", "qty", "unit", "market_price", "base_price", "note"]
        rows = []
        for i in range(self.bom_table.rowCount()):
            row = {}
            for j, key in enumerate(keys):
                item = self.bom_table.item(i, j)
                val = item.text().strip() if item else ""
                if key in ("qty", "market_price", "base_price"):
                    try:
                        val = float(val or 0)
                    except ValueError:
                        val = 0
                row[key] = val
            if row.get("name") or row.get("model") or row.get("type"):
                rows.append(row)
        return rows

    def _add_bom_row(self) -> None:
        row = self.bom_table.rowCount()
        self.bom_table.insertRow(row)
        defaults = ["新增设备", "", "", "", "", "", "1", "台", "0", "0", ""]
        self._loading_bom = True
        for j, val in enumerate(defaults):
            item = QTableWidgetItem(val)
            if j not in (0, 6, 8, 9, 10):
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            self.bom_table.setItem(row, j, item)
        self._loading_bom = False
        self.bom_table.setCurrentCell(row, 0)
        self.bom_table.editItem(self.bom_table.item(row, 0))

    def _del_bom_row(self) -> None:
        row = self.bom_table.currentRow()
        if row < 0:
            return
        self.bom_table.removeRow(row)
        self._recalc_bom_total()

    def _save_bom(self) -> None:
        pid = self._current_id
        if not pid:
            return
        rows = self._collect_bom_rows()
        if not rows:
            QMessageBox.warning(self, "提示", "清单为空，无法生成。")
            return
        run_api(
            self, self._threads,
            lambda: self.api.rebuild_bom(pid, rows=rows),
            self._on_rebuild,
        )

    def _on_rebuild(self, data: dict) -> None:
        files = data.get("files", {})
        excel = files.get("excel", "")
        msg = f"已重出 Excel（{data.get('rows', 0)} 行）"
        if excel:
            try:
                local = download_many(self.api, [excel], self._current_id)
                if local:
                    msg += f"，已下载：{local[0]}"
            except ApiError:
                pass
        QMessageBox.information(self, "完成", msg)

    def _load_messages(self, messages: list[dict]) -> None:
        lines = []
        for m in messages:
            role = m.get("role", "")
            text = m.get("text", m.get("content", ""))
            if role in ("user", "assistant"):
                lines.append(f"[{role}] {text}")
        self.msg_browser.setPlainText("\n\n".join(lines))

    # ---------- 操作 ----------

    def _delete_project(self) -> None:
        pid = self._current_id
        if not pid:
            return
        if QMessageBox.question(self, "删除项目", f"确定删除项目 #{pid} 吗？") != QMessageBox.Yes:
            return
        run_api(self, self._threads, lambda: self.api.delete_project(pid), lambda _r: self.on_show())

    def _download_all(self) -> None:
        pid = self._current_id
        if not pid:
            return
        paths = []
        for i in range(self.files_table.rowCount()):
            item = self.files_table.item(i, 0)
            if item:
                server = item.data(Qt.UserRole)
                if server:
                    paths.append(server)
        if not paths:
            QMessageBox.information(self, "提示", "没有可下载的文件。")
            return
        try:
            local = download_many(self.api, paths, pid)
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "下载失败", str(e))
            return
        if local:
            QMessageBox.information(self, "完成", f"已下载 {len(local)} 个文件到本地输出目录。")
            open_in_folder(local[0])

    def _open_output(self) -> None:
        import os

        folder = os.path.join(os.path.expanduser("~"), "AVAgent 输出", f"项目{self._current_id or 0}")
        os.makedirs(folder, exist_ok=True)
        open_in_folder(folder)

    def _save_as_template(self) -> None:
        pid = self._current_id
        if not pid:
            return
        from PySide6.QtWidgets import QInputDialog

        name, ok = QInputDialog.getText(self, "存为配置模板", "模板名称：", text="项目模板")
        if not ok or not name.strip():
            return
        bom = self.api.project_bom(pid)
        rows = bom.get("rows", [])
        if not rows:
            QMessageBox.warning(self, "提示", "当前项目没有 BOM 行。")
            return
        run_api(
            self, self._threads,
            lambda: self.api.save_bom_template(name.strip(), rows=rows),
            lambda _r: QMessageBox.information(self, "完成", "已存入模板库。"),
        )
