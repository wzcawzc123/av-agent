"""产品库页：搜索、上传、改价、删除。"""

from __future__ import annotations

from typing import Optional

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

COLUMNS = ["ID", "名称", "型号", "品牌", "分类", "描述", "底价", "市场价"]


class ProductsPage(QWidget):
    def __init__(self, api: AvApi):
        super().__init__()
        self.api = api
        self._threads: list[ApiCallThread] = []
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(10)

        title = QLabel("产品库")
        title.setObjectName("title")
        root.addWidget(title)

        bar = QHBoxLayout()
        bar.addWidget(QLabel("关键词"))
        self.q_input = QLineEdit()
        self.q_input.setPlaceholderText("名称 / 型号 / 品牌")
        self.q_input.returnPressed.connect(self._search)
        bar.addWidget(self.q_input, 1)
        bar.addWidget(QLabel("品牌"))
        self.brand_input = QLineEdit()
        self.brand_input.setFixedWidth(140)
        self.brand_input.returnPressed.connect(self._search)
        bar.addWidget(self.brand_input)
        search_btn = QPushButton("搜索")
        search_btn.setObjectName("outlined")
        search_btn.clicked.connect(self._search)
        bar.addWidget(search_btn)
        upload_btn = QPushButton("上传产品 Excel")
        upload_btn.clicked.connect(self._upload)
        bar.addWidget(upload_btn)
        root.addLayout(bar)

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        root.addWidget(self.table, 1)

        btns = QHBoxLayout()
        price_btn = QPushButton("修改选中行价格")
        price_btn.clicked.connect(self._edit_price)
        btns.addWidget(price_btn)
        del_btn = QPushButton("删除选中产品")
        del_btn.setObjectName("danger")
        del_btn.clicked.connect(self._delete)
        btns.addWidget(del_btn)
        btns.addStretch(1)
        root.addLayout(btns)

        self.on_show()

    def on_show(self) -> None:
        self._search()

    def _search(self) -> None:
        q = self.q_input.text().strip()
        brand = self.brand_input.text().strip()
        run_api(
            self, self._threads,
            lambda: self.api.list_products(q=q, brand=brand),
            self._load,
        )

    def _load(self, products: list[dict]) -> None:
        self.table.setRowCount(len(products))
        for i, p in enumerate(products):
            vals = [
                p.get("id", ""), p.get("name", ""), p.get("model", ""),
                p.get("brand", ""), p.get("category", ""), p.get("description", ""),
                p.get("base_price", ""), p.get("market_price", ""),
            ]
            for j, v in enumerate(vals):
                item = QTableWidgetItem("" if v is None else str(v))
                if j == 0:
                    item.setData(Qt.UserRole, p.get("id"))
                self.table.setItem(i, j, item)

    def _selected_product_id(self) -> Optional[int]:
        row = self.table.currentRow()
        if row < 0:
            return None
        return self.table.item(row, 0).data(Qt.UserRole)

    def _upload(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择产品 Excel", "", "Excel (*.xlsx *.xls)")
        if not path:
            return
        run_api(
            self, self._threads,
            lambda: self.api.upload_products(path),
            lambda r: (QMessageBox.information(self, "完成", f"导入成功：{r}"), self._search()),
        )

    def _edit_price(self) -> None:
        pid = self._selected_product_id()
        if pid is None:
            QMessageBox.information(self, "提示", "请先选中一行。")
            return
        from PySide6.QtWidgets import QInputDialog

        base, ok1 = QInputDialog.getDouble(self, "改价", "底价：", 0, 0, 1_000_000_000, 2)
        if not ok1:
            return
        market, ok2 = QInputDialog.getDouble(self, "改价", "市场价：", 0, 0, 1_000_000_000, 2)
        if not ok2:
            return
        run_api(
            self, self._threads,
            lambda: self.api.update_product_price(pid, base, market),
            lambda _r: self._search(),
        )

    def _delete(self) -> None:
        pid = self._selected_product_id()
        if pid is None:
            return
        if QMessageBox.question(self, "删除", "确定删除该产品吗？") != QMessageBox.Yes:
            return
        run_api(self, self._threads, lambda: self.api.delete_product(pid), lambda _r: self._search())
