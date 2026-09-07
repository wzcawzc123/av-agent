"""模型提供商页：当前模型配置 + 提供商管理。"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
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

COLUMNS = ["ID", "名称", "类型", "Base URL", "API Key", "模型数"]


class ProviderDialog(QDialog):
    """新增/编辑提供商表单。"""

    def __init__(self, parent=None, initial: Optional[dict] = None):
        super().__init__(parent)
        self.setWindowTitle("新增提供商" if initial is None else "编辑提供商")
        self.setMinimumWidth(480)
        form = QFormLayout(self)
        self.name = QLineEdit()
        form.addRow("名称 *", self.name)
        self.p_type = QComboBox()
        for label, value in [
            ("OpenAI 兼容", "openai_compatible"),
            ("Anthropic", "anthropic"),
            ("Gemini", "gemini"),
        ]:
            self.p_type.addItem(label, value)
        form.addRow("类型", self.p_type)
        self.base_url = QLineEdit()
        self.base_url.setPlaceholderText("https://api.openai.com/v1")
        form.addRow("Base URL", self.base_url)
        self.api_key = QLineEdit()
        self.api_key.setPlaceholderText("API Key（可为空，稍后配置）")
        form.addRow("API Key", self.api_key)
        self.models = QTextEdit()
        self.models.setPlaceholderText("每行一个模型，格式：model_id 或 model_id|显示名称")
        self.models.setFixedHeight(140)
        form.addRow("模型列表", self.models)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        if initial:
            self.name.setText(initial.get("name", ""))
            idx = self.p_type.findData(initial.get("provider_type", "openai_compatible"))
            self.p_type.setCurrentIndex(max(idx, 0))
            self.base_url.setText(initial.get("base_url", ""))
            self.api_key.setText(initial.get("api_key", ""))
            lines = []
            for m in initial.get("models", []):
                mid = m.get("model_id", "")
                disp = m.get("display_name", "")
                lines.append(mid if not disp or disp == mid else f"{mid}|{disp}")
            self.models.setPlainText("\n".join(lines))

    def payload(self) -> dict:
        models = []
        for line in self.models.toPlainText().strip().splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split("|")
            mid = parts[0].strip()
            disp = parts[1].strip() if len(parts) > 1 else ""
            models.append({"model_id": mid, "display_name": disp or mid})
        return {
            "name": self.name.text().strip(),
            "provider_type": self.p_type.currentData(),
            "base_url": self.base_url.text().strip(),
            "api_key": self.api_key.text().strip(),
            "endpoint_mode": "chat_completions",
            "models": models,
        }


class ProvidersPage(QWidget):
    def __init__(self, api: AvApi):
        super().__init__()
        self.api = api
        self._threads: list[ApiCallThread] = []
        self._providers: list[dict] = []
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(10)

        title = QLabel("模型提供商")
        title.setObjectName("title")
        root.addWidget(title)

        # 当前模型配置
        cfg_box = QWidget()
        cfg = QVBoxLayout(cfg_box)
        cfg.setContentsMargins(0, 0, 0, 4)
        cfg_label = QLabel("当前模型配置")
        cfg_label.setObjectName("title")
        cfg_label.setStyleSheet("font-size: 14px;")
        cfg.addWidget(cfg_label)
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("提供商"))
        self.provider_combo = QComboBox()
        self.provider_combo.setMinimumWidth(220)
        self.provider_combo.currentIndexChanged.connect(self._on_provider_combo)
        row1.addWidget(self.provider_combo)
        row1.addWidget(QLabel("模型"))
        self.model_combo = QComboBox()
        self.model_combo.setMinimumWidth(220)
        row1.addWidget(self.model_combo)
        row1.addStretch(1)
        cfg.addLayout(row1)
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("API Key"))
        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("填写新 Key；掩码 ****** 表示保持原值")
        row2.addWidget(self.key_input, 1)
        row2.addWidget(QLabel("Base URL"))
        self.base_url_input = QLineEdit()
        self.base_url_input.setPlaceholderText("留空使用该提供商默认地址")
        row2.addWidget(self.base_url_input, 2)
        save_btn = QPushButton("保存当前配置")
        save_btn.clicked.connect(self._save_model_config)
        row2.addWidget(save_btn)
        cfg.addLayout(row2)
        root.addWidget(cfg_box)

        # 提供商表格
        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        root.addWidget(self.table, 1)

        # 操作按钮
        ops = QHBoxLayout()
        for label, slot in [
            ("新增提供商", self._add),
            ("设为当前", self._set_current),
            ("复制", self._copy),
            ("重置为内置", self._reset),
            ("远程拉取模型", self._fetch_models),
            ("测试连接", self._test),
            ("删除", self._delete),
        ]:
            btn = QPushButton(label)
            btn.setObjectName("danger" if label == "删除" else "ghost")
            btn.clicked.connect(slot)
            ops.addWidget(btn)
        ops.addStretch(1)
        root.addLayout(ops)

    # ---------- 数据 ----------

    def on_show(self) -> None:
        run_api(self, self._threads, self.api.list_providers, self._load_providers)

    def _load_providers(self, providers: list[dict]) -> None:
        self._providers = providers
        selected = self.provider_combo.currentData()
        self.provider_combo.blockSignals(True)
        self.provider_combo.clear()
        for p in providers:
            key_state = "✔" if p.get("has_api_key") else "未配置Key"
            self.provider_combo.addItem(f"{p.get('name', '')}（{key_state}）", p.get("id"))
        idx = self.provider_combo.findData(selected)
        self.provider_combo.setCurrentIndex(max(idx, 0))
        self.provider_combo.blockSignals(False)
        self._fill_table()
        self._on_provider_combo()
        # 回填当前模型配置
        run_api(self, self._threads, self.api.get_model_config, self._load_model_config)

    def _fill_table(self) -> None:
        self.table.setRowCount(len(self._providers))
        for i, p in enumerate(self._providers):
            vals = [
                p.get("id", ""), p.get("name", ""), p.get("provider_type", ""),
                p.get("base_url", ""),
                "已配置" if p.get("has_api_key") else "未配置",
                str(len(p.get("models", []))),
            ]
            for j, v in enumerate(vals):
                item = QTableWidgetItem("" if v is None else str(v))
                if j == 0:
                    item.setData(Qt.UserRole, p.get("id"))
                self.table.setItem(i, j, item)

    def _load_model_config(self, cfg: dict) -> None:
        self._selected_cfg_provider = cfg.get("provider", "")
        self._selected_cfg_model = cfg.get("model", "")
        self.base_url_input.setText(cfg.get("base_url", ""))
        self.key_input.setText("******" if cfg.get("has_api_key") else "")
        # 让当前下拉选中已配置的提供商
        idx = self.provider_combo.findData(cfg.get("provider", ""))
        if idx >= 0:
            self.provider_combo.setCurrentIndex(idx)

    def _selected_provider(self) -> Optional[dict]:
        pid = self.provider_combo.currentData()
        for p in self._providers:
            if p.get("id") == pid:
                return p
        return None

    def _on_provider_combo(self) -> None:
        p = self._selected_provider()
        if not p:
            return
        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        models = p.get("models", [])
        if not models:
            self.model_combo.addItem("（该提供商没有模型，可点「远程拉取模型」）", "")
        else:
            for m in models:
                mid = m.get("model_id", "")
                disp = m.get("display_name", "") or mid
                self.model_combo.addItem(f"{disp}（{mid}）" if disp != mid else mid, mid)
        selected_model = getattr(self, "_selected_cfg_model", "")
        if selected_model:
            idx = self.model_combo.findData(selected_model)
            if idx >= 0:
                self.model_combo.setCurrentIndex(idx)
        self.model_combo.blockSignals(False)

    # ---------- 操作 ----------

    def _save_model_config(self) -> None:
        p = self._selected_provider()
        if not p:
            return
        key = self.key_input.text().strip()
        model = self.model_combo.currentData() or ""
        base_url = self.base_url_input.text().strip()
        if not model:
            QMessageBox.warning(self, "提示", "请先选择模型。")
            return
        run_api(
            self, self._threads,
            lambda: self.api.put_model_config(
                provider=p.get("id", ""), api_key=key, model=model, base_url=base_url,
            ),
            lambda _r: QMessageBox.information(self, "完成", "当前模型配置已保存。"),
        )

    def _add(self) -> None:
        dlg = ProviderDialog(self)
        if dlg.exec() != QDialog.Accepted:
            return
        payload = dlg.payload()
        if not payload["name"]:
            QMessageBox.warning(self, "提示", "名称不能为空。")
            return
        run_api(
            self, self._threads,
            lambda: self.api.create_provider(payload),
            lambda r: (QMessageBox.information(self, "完成", f"已新增提供商：{r}"), self.on_show()),
        )

    def _table_selected_id(self) -> Optional[str]:
        row = self.table.currentRow()
        if row < 0:
            return None
        return self.table.item(row, 0).data(Qt.UserRole)

    def _set_current(self) -> None:
        pid = self._table_selected_id()
        if not pid:
            return
        self.provider_combo.setCurrentIndex(self.provider_combo.findData(pid))

    def _copy(self) -> None:
        pid = self._table_selected_id()
        if not pid:
            return
        run_api(self, self._threads, lambda: self.api.copy_provider(pid), lambda _r: self.on_show())

    def _reset(self) -> None:
        pid = self._table_selected_id()
        if not pid:
            return
        run_api(self, self._threads, lambda: self.api.reset_provider(pid), lambda _r: self.on_show())

    def _fetch_models(self) -> None:
        pid = self._table_selected_id()
        if not pid:
            return
        run_api(
            self, self._threads,
            lambda: self.api.fetch_provider_models(pid),
            lambda r: (QMessageBox.information(self, "完成", f"拉取到模型：{r.get('fetched', [])}"), self.on_show()),
        )

    def _test(self) -> None:
        pid = self._table_selected_id()
        if not pid:
            return
        run_api(
            self, self._threads,
            lambda: self.api.test_provider(pid),
            lambda r: QMessageBox.information(
                self, "测试连接",
                "连接正常。" if r.get("ok") else f"返回：{r}",
            ),
        )

    def _delete(self) -> None:
        pid = self._table_selected_id()
        if not pid:
            return
        if QMessageBox.question(self, "删除", "确定删除该提供商吗？") != QMessageBox.Yes:
            return
        run_api(self, self._threads, lambda: self.api.delete_provider(pid), lambda _r: self.on_show())
