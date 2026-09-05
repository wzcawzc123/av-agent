"""招标文件解析：Excel/Word/PDF 表格提取 -> TenderItem 列表。

列名用别名表识别（适配不同招标模板），参数字符串按换行/分号/序号拆分。
品牌型号混填时启发式拆分（含数字 token 视为型号，纯字母 token 视为品牌）。
"""
from __future__ import annotations

import re
from pathlib import Path

from app.engines.tender.model import TenderItem

# 标准字段 -> 列名别名（小写匹配）
COLUMN_ALIASES: dict[str, list[str]] = {
    "name": ["设备名称", "名称", "产品名称", "货物名称", "设备", "品名", "项目名称", "材料名称"],
    "brand": ["品牌", "参考品牌", "品牌型号", "厂牌", "推荐品牌"],
    "model": ["型号", "规格型号", "产品型号", "型号规格", "规格"],
    "params": ["技术参数", "参数要求", "技术要求", "规格参数", "技术规格", "主要技术参数", "参数", "技术说明"],
    "qty": ["数量", "工程量", "台数", "工程量清单"],
    "unit": ["单位", "计量单位"],
}

# 跳过行关键词（表头残留/合计行）
SKIP_NAME_WORDS = ("合计", "总计", "小计", "备注", "序号", "项目名称", "设备名称", "货物名称")

_HAS_DIGIT = re.compile(r"\d")
_SPLIT_TOKENS = re.compile(r"[\s/、,，]+")


def _norm(s) -> str:
    return re.sub(r"\s+", "", str(s or "")).lower()


def detect_columns(header: list) -> dict[str, int]:
    """表头行 -> {标准字段: 列索引}。别名长词优先（品牌型号 优先于 品牌）。"""
    cols: dict[str, int] = {}
    cells = [_norm(c) for c in header]
    for field, aliases in COLUMN_ALIASES.items():
        # 长别名优先匹配，避免「品牌型号」被「品牌」抢占后型号丢失
        for alias in sorted(aliases, key=len, reverse=True):
            a = _norm(alias)
            for i, cell in enumerate(cells):
                if i in cols.values():
                    continue
                if a in cell:
                    cols[field] = i
                    break
            if field in cols:
                break
    return cols


def split_params(text: str) -> list[str]:
    """参数字符串拆分：换行 -> 分号 -> 中文序号（1、 2. 3）)."""
    if not text:
        return []
    parts: list[str] = []
    for line in re.split(r"[\n\r]+", str(text)):
        for seg in re.split(r"[；;]", line):
            # 序号前缀拆分：「1、xxx2、yyy」粘连场景
            segs = re.split(r"(?<=[^\d])\d+[、.．]\s*", seg)
            for s in segs:
                s = re.sub(r"^\d+[、.．]\s*", "", s.strip())
                if s:
                    parts.append(s)
    # 去重保序
    seen: set[str] = set()
    out = []
    for p in parts:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def parse_model_field(brand_cell: str, model_cell: str) -> tuple[str, str]:
    """品牌/型号混填拆分：含数字 token -> 型号；纯字母/中文 token -> 品牌。"""
    brand = (brand_cell or "").strip()
    model = (model_cell or "").strip()

    # 品牌列混入型号（如 brand="ITC T-62200"）
    if brand:
        tokens = [t for t in _SPLIT_TOKENS.split(brand) if t]
        if len(tokens) >= 2 and any(_HAS_DIGIT.search(t) for t in tokens):
            b_parts = [t for t in tokens if not _HAS_DIGIT.search(t)]
            m_parts = [t for t in tokens if _HAS_DIGIT.search(t)]
            if b_parts and m_parts:
                brand = " ".join(b_parts)
                if not model:
                    model = " ".join(m_parts)

    # 型号列混入品牌（如 model="ITC T-62200" 或 "ITC/T-62200"）
    if model:
        tokens = [t for t in _SPLIT_TOKENS.split(model) if t]
        if len(tokens) >= 2:
            b_parts = [t for t in tokens if not _HAS_DIGIT.search(t)]
            m_parts = [t for t in tokens if _HAS_DIGIT.search(t)]
            if b_parts and m_parts:
                model = " ".join(m_parts)
                if not brand:
                    brand = " ".join(b_parts)
    return brand, model


def _parse_qty(v) -> int:
    m = re.search(r"\d+", str(v or ""))
    return int(m.group(0)) if m else 1


def rows_to_items(raw_rows: list[list]) -> list[TenderItem]:
    """原始表格行（含表头）-> TenderItem 列表。"""
    if not raw_rows:
        return []
    header_idx = 0
    cols: dict[str, int] = {}
    # 在前 5 行内寻找表头（能识别出 name 列的行）
    for i, row in enumerate(raw_rows[:5]):
        c = detect_columns(row)
        if "name" in c:
            header_idx = i
            cols = c
            break
    if not cols:
        return []

    def cell(row: list, field: str) -> str:
        idx = cols.get(field)
        if idx is None or idx >= len(row):
            return ""
        return str(row[idx] or "").strip()

    items: list[TenderItem] = []
    for row in raw_rows[header_idx + 1 :]:
        name = cell(row, "name")
        if not name or any(w in name for w in SKIP_NAME_WORDS):
            continue
        brand, model = parse_model_field(cell(row, "brand"), cell(row, "model"))
        params = split_params(cell(row, "params"))
        items.append(
            TenderItem(
                idx=len(items) + 1,
                name=name,
                brand=brand,
                model=model,
                qty=_parse_qty(cell(row, "qty")),
                params=params,
                raw=" | ".join(str(c or "") for c in row),
            )
        )
    return items


# ---------- 文件提取 ----------

def _extract_xlsx(path: Path) -> list[list[list]]:
    from openpyxl import load_workbook

    wb = load_workbook(path, read_only=True, data_only=True)
    tables = []
    for ws in wb.worksheets:
        rows = [list(r) for r in ws.iter_rows(values_only=True)]
        if rows:
            tables.append(rows)
    wb.close()
    return tables


def _extract_docx(path: Path) -> list[list[list]]:
    import docx

    d = docx.Document(str(path))
    tables = []
    for t in d.tables:
        rows = [[c.text for c in r.cells] for r in t.rows]
        if rows:
            tables.append(rows)
    return tables


def _extract_pdf(path: Path) -> list[list[list]]:
    import pdfplumber

    tables = []
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            for t in page.extract_tables() or []:
                if t:
                    tables.append(t)
    return tables


_EXTRACTORS = {
    ".xlsx": _extract_xlsx,
    ".xlsm": _extract_xlsx,
    ".docx": _extract_docx,
    ".pdf": _extract_pdf,
}


def parse_file(path: str | Path) -> list[TenderItem]:
    """解析招标文件，返回设备需求行。不支持的扩展名抛 ValueError。"""
    p = Path(path)
    ext = p.suffix.lower()
    if ext not in _EXTRACTORS:
        raise ValueError(f"不支持的文件类型：{ext}（支持 xlsx/xlsm/docx/pdf）")
    tables = _EXTRACTORS[ext](p)
    items: list[TenderItem] = []
    for t in tables:
        items.extend(rows_to_items(t))
    # 重新编号
    for i, it in enumerate(items, 1):
        it.idx = i
    return items
