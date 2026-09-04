"""轻量 schema 迁移：SQLite 上按需补列（不引入 Alembic）。"""
from sqlalchemy import text


def _existing_columns(engine, table: str) -> set[str]:
    with engine.connect() as conn:
        rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
    return {r[1] for r in rows}


_TABLE_COLUMNS = {
    "selection_rules": [
        ("mic_level", "VARCHAR(20)"),
        ("antenna_level", "VARCHAR(20)"),
    ],
    "products": [
        ("system", "VARCHAR(50) DEFAULT ''"),
        ("role_tags", "TEXT DEFAULT '[]'"),
        ("active", "INTEGER DEFAULT 1"),
    ],
}


def ensure_schema(engine):
    """为既有表补齐新增列（幂等）。"""
    for table, cols in _TABLE_COLUMNS.items():
        existing = _existing_columns(engine, table)
        additions = [f"{name} {ddl}" for name, ddl in cols if name not in existing]
        if additions:
            with engine.connect() as conn:
                for ddl in additions:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {ddl}"))
                conn.commit()
            print(f"[migrate] {table} 新增列: {additions}")
