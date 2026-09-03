import json

from openpyxl import load_workbook

from app.db.models import Product

HEADER_MAP = {
    "产品名称": "name",
    "型号": "model",
    "参数": "params_json",
    "低价": "low_price",
    "市场价": "market_price",
    "分类": "category",
}


def _norm(s):
    return str(s or "").strip()


def import_products(excel_path: str, session) -> dict:
    wb = load_workbook(excel_path, read_only=True)
    ws = wb.active
    rows = ws.iter_rows(values_only=True)
    header = [_norm(c) for c in next(rows)]
    col = {HEADER_MAP[h]: i for i, h in enumerate(header) if h in HEADER_MAP}
    inserted = updated = 0
    for row in rows:
        if not row or not _norm(row[col["model"]]):
            continue
        model = _norm(row[col["model"]])
        data = {k: row[i] for k, i in col.items()}
        if data.get("params_json") is not None and not isinstance(data["params_json"], str):
            data["params_json"] = json.dumps(data["params_json"], ensure_ascii=False)
        existing = session.query(Product).filter_by(model=model).first()
        if existing:
            for k, v in data.items():
                setattr(existing, k, v)
            updated += 1
        else:
            session.add(Product(**data))
            inserted += 1
    session.flush()
    wb.close()
    return {"inserted": inserted, "updated": updated}
