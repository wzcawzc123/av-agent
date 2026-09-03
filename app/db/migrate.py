"""轻量 schema 迁移：让已有 SQLite 库与当前模型对齐。

- 旧版列名 low_price -> base_price（自动重命名，数据保留）；
- 模型新增列（如 brand/description）自动 ADD COLUMN；
- 不动已有表结构以外的数据。
"""
from sqlalchemy import text

from app.db.models import Product

_COLUMN_DDL = {
    "name": "VARCHAR(200)",
    "model": "VARCHAR(100)",
    "brand": "VARCHAR(100) DEFAULT ''",
    "description": "TEXT DEFAULT ''",
    "params_json": "TEXT DEFAULT '{}'",
    "base_price": "FLOAT DEFAULT 0",
    "low_price": "FLOAT DEFAULT 0",
    "market_price": "FLOAT DEFAULT 0",
    "category": "VARCHAR(100) DEFAULT ''",
    "updated_at": "DATETIME",
}

_RENAME = {"low_price": "base_price"}


def ensure_schema(engine) -> None:
    with engine.connect() as conn:
        # 1) 旧列名重命名（SQLite 支持 RENAME COLUMN，版本 >= 3.25）
        try:
            existing = {r[1] for r in conn.execute(text("PRAGMA table_info(products)"))}
        except Exception:
            conn.rollback()
            return
        for old, new in _RENAME.items():
            if old in existing and new not in existing:
                conn.execute(text(f"ALTER TABLE products RENAME COLUMN {old} TO {new}"))
        # 2) 按模型补齐缺失列
        existing = {r[1] for r in conn.execute(text("PRAGMA table_info(products)"))}
        model_cols = {c.name for c in Product.__table__.columns}
        for col in model_cols:
            if col in existing or col not in _COLUMN_DDL:
                continue
            conn.execute(text(f"ALTER TABLE products ADD COLUMN {col} {_COLUMN_DDL[col]}"))
        conn.commit()
