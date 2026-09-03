"""通用产品库导入器。

支持两类真实清单格式：
- MAXHUB 全产品清单：多 sheet，每 sheet 含分类段行（如 "1.0—标准款"），
  产品名称可能只在分段首行出现（向下继承），扩展列（尺寸/视距/适用范围）归入 params_json；
- 报价清单：标题行 + 表头 + 分类段（如 "一、MCU平台类"），含单价/数量列（价格留空不导入）。

统一规则：
- 型号（型号/产品型号/销售型号/产品型号(新)）唯一；重复型号跳过，不覆盖更新；
- 价格（底价/市场价/单价）一律留空（0），后续由带价格的清单另行导入；
- 分类 = sheet名/分类段（如 "会议平板/标准款"、"音视频产品/MCU平台类"）；
- 无有效表头的 sheet（如 WPS 内部图片表）自动跳过。
"""
import json
import re

from openpyxl import load_workbook

from app.db.models import Product

_NAME_COLS = ("产品名称", "名称", "产品名")
_MODEL_COLS = ("型号", "产品型号", "销售型号", "产品型号(新)", "产品型号（新）")
_BRAND_COLS = ("品牌",)
_DESC_COLS = ("产品描述", "描述", "产品参数")
_CATEGORY_COLS = ("系统分类", "品类", "分类")
_EXTRA_COLS = {  # 扩展列归入 params_json
    "尺寸（长*宽*高）": "size",
    "尺寸(长*宽*高)": "size",
    "尺寸": "size",
    "建议视距": "viewing_distance",
    "适用范围": "application",
    "点间距": "pixel_pitch",
    "备注": "remark",
    "开票名称": "invoice_name",
    "单位": "unit",
    "参数": "spec",
}
_SECTION_RE = re.compile(r"^[\d一二三四五六七八九十]+(?:[.．]\d+)?[.、—-]*\s*(.+)$")


def _norm(s):
    return str(s or "").strip()


def _sheet_title(name):
    """规范化工作表名：去掉（导入）/空白等后缀，作为分类前缀。"""
    t = _norm(name)
    for suffix in ("（导入）", "(导入)", "表", " "):
        t = t.replace(suffix, "")
    return t.strip()


def _find_header(rows_iter):
    """在行流里找第一个含型号/名称列的表头行，返回 (header_row, 该行索引)。"""
    for row in rows_iter:
        cells = [_norm(c) for c in row]
        has_model = any(c in _MODEL_COLS for c in cells)
        has_name = any(c in _NAME_COLS for c in cells)
        if has_model or has_name:
            return cells
    return None


def _is_section_row(cells):
    """分类段行：第 1 列有值且不是产品行（没有型号）。"""
    first = cells[0] if cells else ""
    if not first:
        return False
    if any(c in _MODEL_COLS for c in cells):
        return False  # 这是表头
    # 分类段行特征：第一个单元格较短、不含型号
    if len(first) > 40:
        return False
    if _SECTION_RE.match(first) or first.startswith("--") or "—" in first or "、" in first:
        return True
    return False


def _section_name(cells):
    first = _norm(cells[0]) if cells else ""
    m = _SECTION_RE.match(first)
    if m and m.group(1):
        return m.group(1).strip()
    return first.lstrip("-").strip()


def _parse_product_row(cells, header, sheet_title, cur_section, inherit_name=""):
    """把一行数据映射为 Product 字段；返回 None 表示跳过。"""
    idx = {h: i for i, h in enumerate(header)}

    def get(cols):
        for c in cols:
            if c in idx:
                v = cells[idx[c]]
                if v is not None and _norm(v):
                    return v
        return None

    model = _norm(get(_MODEL_COLS))
    if not model:
        return None
    # 名称继承：分段首行有名称，后续行名称为空则继承
    raw_name = _norm(get(_NAME_COLS))
    name = raw_name or inherit_name or model
    brand = _norm(get(_BRAND_COLS))
    desc = _norm(get(_DESC_COLS))
    params = {}
    for col, key in _EXTRA_COLS.items():
        if col in idx:
            v = cells[idx[col]]
            if v is not None and _norm(v):
                params[key] = _norm(v)
    if get(_CATEGORY_COLS):
        sub = _norm(get(_CATEGORY_COLS))
        category = sub if sub == sheet_title else f"{sheet_title}/{sub}"
    else:
        # 子分类与 sheet 同名（如 "1--音视频产品" 段）时不重复拼接
        category = sheet_title if not cur_section or cur_section == sheet_title else f"{sheet_title}/{cur_section}"
    return {
        "name": name,
        "model": model,
        "brand": brand,
        "description": desc,
        "params_json": json.dumps(params, ensure_ascii=False),
        "base_price": 0,
        "market_price": 0,
        "category": category,
    }


def import_products_v2(excel_path: str, session) -> dict:
    wb = load_workbook(excel_path, read_only=True)
    inserted = skipped = 0
    for ws in wb.worksheets:
        rows_iter = ws.iter_rows(values_only=True)
        header = _find_header(rows_iter)
        if not header:
            continue  # 无表头 sheet（如 WPS 图片表）
        cur_section = ""
        cur_name = ""
        for row in rows_iter:
            cells = [_norm(c) for c in row]
            if not any(cells):
                continue
            data = _parse_product_row(cells, header, _sheet_title(ws.title), cur_section, cur_name)
            if data:
                cur_name = data["name"]  # 供后续行继承
            elif _is_section_row(cells):
                cur_section = _section_name(cells)
                continue
            else:
                continue
            if session.query(Product).filter_by(model=data["model"]).first():
                skipped += 1  # 重复型号：跳过不更新
                continue
            session.add(Product(**data))
            inserted += 1
    session.flush()
    wb.close()
    return {"inserted": inserted, "updated": 0, "skipped": skipped}


# 兼容旧接口（保留原行为，供旧调用方使用）
def import_products(excel_path: str, session) -> dict:
    return import_products_v2(excel_path, session)
