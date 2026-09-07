"""工具箱页：直接运行 4 个工具引擎（偏离表/LED/会议/广播），结果下载 Excel。

web 端有工具箱但桌面端此前只能靠对话触发引擎直通；本页提供表单化入口。
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from desktop.api import AvApi, ApiError
from desktop.files import download_file, open_in_folder
from desktop.worker import ApiCallThread, run_api


def _parse_qty_line(line: str) -> tuple[str, dict]:
    """解析 '一层 | 壁挂音箱×2, 音柱×4' → ("一层", {"壁挂音箱": 2, "音柱": 4})。"""
    name, _, rest = line.partition("|")
    zone_name = name.strip()
    items: dict[str, int] = {}
    for part in rest.split(","):
        part = part.strip()
        if not part:
            continue
        qty = 1
        model = part
        for sep in ("×", "x", "X", "*"):
            if sep in part:
                model, _, q = part.partition(sep)
                try:
                    qty = int(q.strip() or 1)
                except ValueError:
                    qty = 1
                break
        model = model.strip()
        if model:
            items[model] = items.get(model, 0) + qty
    return zone_name, items


class ToolsPage(QWidget):
    def __init__(self, api: AvApi):
        super().__init__()
        self.api = api
        self._threads: list[ApiCallThread] = []
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(10)

        title = QLabel("工具箱 · 引擎直出")
        title.setObjectName("title")
        root.addWidget(title)
        hint = QLabel("不依赖对话，直接运行工具引擎生成 Excel（偏离表/LED/会议/广播）。")
        hint.setObjectName("hint")
        root.addWidget(hint)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        lay = QVBoxLayout(body)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(14)

        lay.addWidget(self._deviation_card())
        lay.addWidget(self._led_card())
        lay.addWidget(self._meeting_card())
        lay.addWidget(self._broadcast_card())
        lay.addStretch(1)
        scroll.setWidget(body)
        root.addWidget(scroll, 1)

    # ---------- 引擎卡片 ----------

    def _card(self, label: str, form: QWidget, run_btn: QPushButton) -> QWidget:
        card = QWidget()
        lay = QVBoxLayout(card)
        t = QLabel(label)
        t.setObjectName("title")
        t.setStyleSheet("font-size: 14px;")
        lay.addWidget(t)
        lay.addWidget(form)
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_row.addWidget(run_btn)
        lay.addLayout(btn_row)
        return card

    def _deviation_card(self) -> QWidget:
        self.dev_items = QPlainTextEdit()
        self.dev_items.setPlaceholderText(
            "每行一项招标需求，格式自由，例如：\n华为 4K摄像机 20台 支持SDI\n"
            "专业功放 800W 8Ω 数量10\n也可只写需求文字，模型会智能提取"
        )
        self.dev_items.setFixedHeight(130)
        row = QHBoxLayout()
        row.addWidget(QLabel("品牌过滤（可选）"))
        self.dev_brand = QLineEdit()
        self.dev_brand.setPlaceholderText("如：MAXHUB，留空不限制")
        row.addWidget(self.dev_brand, 1)
        self.dev_llm = QCheckBox("LLM 智能匹配增强")
        row.addWidget(self.dev_llm)
        form = QWidget()
        fl = QVBoxLayout(form)
        fl.setContentsMargins(0, 0, 0, 0)
        fl.addWidget(self.dev_items)
        fl.addLayout(row)
        btn = QPushButton("🚀 生成偏离表")
        btn.clicked.connect(self._run_deviation)
        return self._card("偏离表（对照招标逐项判断满足/偏离）", form, btn)

    def _led_card(self) -> QWidget:
        form = QWidget()
        fl = QFormLayout(form)
        self.led_w = QLineEdit("5")
        self.led_h = QLineEdit("3")
        self.led_model = QComboBox()
        self.led_model.addItem("（加载中…）", "")
        run_api(self, self._threads, self.api.led_specs, self._load_led_specs)
        fl.addRow("宽（米）", self.led_w)
        fl.addRow("高（米）", self.led_h)
        fl.addRow("屏体型号", self.led_model)
        btn = QPushButton("🚀 生成 LED 排布清单")
        btn.clicked.connect(self._run_led)
        return self._card("LED 屏排布", form, btn)

    def _load_led_specs(self, data: dict) -> None:
        self.led_model.blockSignals(True)
        self.led_model.clear()
        for m in data.get("models", []):
            self.led_model.addItem(
                f"{m['model']}（{m['module']}，{m['res']}）", m["model"])
        self.led_model.blockSignals(False)

    def _meeting_card(self) -> QWidget:
        form = QWidget()
        fl = QFormLayout(form)
        self.meeting_code = QLineEdit()
        self.meeting_code.setPlaceholderText("可留空")
        fl.addRow("会议编号", self.meeting_code)
        dims = QHBoxLayout()
        self.m_len = QLineEdit("10")
        self.m_wid = QLineEdit("8")
        self.m_hei = QLineEdit("3")
        dims.addWidget(QLabel("长"))
        dims.addWidget(self.m_len)
        dims.addWidget(QLabel("宽"))
        dims.addWidget(self.m_wid)
        dims.addWidget(QLabel("高"))
        dims.addWidget(self.m_hei)
        fl.addRow("房间尺寸(米)", dims)
        self.meeting_scene = QComboBox()
        for s in ("圆桌", "阶梯", "报告厅"):
            self.meeting_scene.addItem(s)
        fl.addRow("场景", self.meeting_scene)
        self.meeting_config = QComboBox()
        for c in ("高配", "中配", "低配"):
            self.meeting_config.addItem(c)
        fl.addRow("配置", self.meeting_config)
        self.meeting_mic = QComboBox()
        for label, code in [("无", "0"), ("无线手持", "1"), ("无线会议", "2"), ("数字会议", "3")]:
            self.meeting_mic.addItem(label, code)
        fl.addRow("拾音", self.meeting_mic)
        btn = QPushButton("🚀 生成会议配置清单")
        btn.clicked.connect(self._run_meeting)
        return self._card("会议系统配置", form, btn)

    def _broadcast_card(self) -> QWidget:
        self.bc_zones = QPlainTextEdit()
        self.bc_zones.setPlaceholderText(
            "每行一个分区：分区名 | 音箱型号×数量（可多个，逗号分隔）\n"
            "一层 | 壁挂音箱×2, 音柱×4\n二层 | 壁挂音箱×2\n三层 | 壁挂音箱×2"
        )
        self.bc_zones.setFixedHeight(120)
        form = QWidget()
        fl = QVBoxLayout(form)
        fl.setContentsMargins(0, 0, 0, 0)
        fl.addWidget(self.bc_zones)
        btn = QPushButton("🚀 生成广播分区清单")
        btn.clicked.connect(self._run_broadcast)
        return self._card("公共广播分区", form, btn)

    # ---------- 执行 ----------

    def _download_result(self, data: dict) -> None:
        server_path = data.get("file") or (data.get("files") or {}).get("excel", "")
        if not server_path:
            QMessageBox.warning(self, "提示", "引擎未返回文件。")
            return
        try:
            local = download_file(self.api, server_path, None)
        except ApiError as e:
            QMessageBox.warning(self, "下载失败", e.message)
            return
        QMessageBox.information(self, "完成", f"已生成并下载：{local}")
        open_in_folder(local)

    def _run_deviation(self) -> None:
        items = [l.strip() for l in self.dev_items.toPlainText().splitlines() if l.strip()]
        if not items:
            QMessageBox.warning(self, "提示", "请至少输入一项招标需求。")
            return
        payload = {
            "tender_items": items,
            "models": [m.strip() for m in self.dev_brand.text().split(",") if m.strip()],
            "llm_enabled": self.dev_llm.isChecked(),
        }
        run_api(self, self._threads,
                lambda: self.api.run_engine("deviation", payload), self._download_result)

    def _run_led(self) -> None:
        try:
            w = float(self.led_w.text() or 0)
            h = float(self.led_h.text() or 0)
        except ValueError:
            w = h = 0
        if w <= 0 or h <= 0:
            QMessageBox.warning(self, "提示", "请输入有效的宽高。")
            return
        payload = {"want_w_m": w, "want_h_m": h, "model": self.led_model.currentData() or ""}
        run_api(self, self._threads,
                lambda: self.api.run_engine("led", payload), self._download_result)

    def _run_meeting(self) -> None:
        def _f(v: str) -> float:
            try:
                return float(v or 0)
            except ValueError:
                return 0

        payload = {
            "code": self.meeting_code.text().strip(),
            "length_m": _f(self.m_len.text()),
            "width_m": _f(self.m_wid.text()),
            "height_m": _f(self.m_hei.text()),
            "scene": self.meeting_scene.currentText(),
            "config": self.meeting_config.currentText(),
            "mic": self.meeting_mic.currentData() or "0",
            "antenna": "0",
        }
        run_api(self, self._threads,
                lambda: self.api.run_engine("meeting", payload), self._download_result)

    def _run_broadcast(self) -> None:
        zones = []
        for line in self.bc_zones.toPlainText().splitlines():
            line = line.strip()
            if not line:
                continue
            name, items = _parse_qty_line(line)
            if name:
                zone = {"zone": name, **items}
                zones.append(zone)
        if not zones:
            QMessageBox.warning(self, "提示", "请至少输入一个分区（格式：分区名 | 型号×数量）。")
            return
        run_api(self, self._threads,
                lambda: self.api.run_engine("broadcast", {"zones": zones}), self._download_result)
