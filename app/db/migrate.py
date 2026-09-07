"""轻量 schema 迁移：SQLite 上按需补列（不引入 Alembic）。"""
from sqlalchemy import text


def _existing_columns(engine, table: str) -> set[str]:
    with engine.connect() as conn:
        rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
    return {r[1] for r in rows}


def _table_exists(engine, table: str) -> bool:
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT 1 FROM sqlite_master WHERE type='table' AND name=:t"),
            {"t": table},
        ).fetchone()
    return row is not None


_TABLE_COLUMNS = {
    "selection_rules": [
        ("mic_level", "VARCHAR(20)"),
        ("antenna_level", "VARCHAR(20)"),
    ],
    "products": [
        ("brand", "VARCHAR(100) DEFAULT ''"),
        ("description", "TEXT DEFAULT ''"),
        ("params_json", "TEXT DEFAULT '{}'"),
        ("unit", "VARCHAR(30) DEFAULT ''"),
        ("system", "VARCHAR(50) DEFAULT ''"),
        ("role_tags", "TEXT DEFAULT '[]'"),
        ("active", "INTEGER DEFAULT 1"),
        ("source_batch", "VARCHAR(40) DEFAULT ''"),
        ("updated_at", "DATETIME DEFAULT '1970-01-01 00:00:00'"),
    ],
    "projects": [
        ("bom_json", "TEXT DEFAULT '{}'"),
        ("org_id", "INTEGER"),
        ("customer_name", "VARCHAR(200) DEFAULT ''"),
        ("memory_json", "TEXT DEFAULT '{}'"),
    ],
    "config_templates": [
        ("systems", "TEXT DEFAULT '[]'"),
        ("config_level", "VARCHAR(50) DEFAULT ''"),
        ("brand", "VARCHAR(200) DEFAULT ''"),
        ("scale_rules", "TEXT DEFAULT '[]'"),
    ],
    "tasks": [
        ("task_key", "VARCHAR(64) DEFAULT ''"),
        ("message", "TEXT DEFAULT ''"),
        ("result_json", "TEXT DEFAULT '{}'"),
        ("finished_at", "DATETIME"),
    ],
}


def ensure_schema(engine):
    """为既有表补齐新增列（幂等）；仅 SQLite 需要补列迁移，PG 新表由 create_all 建。"""
    if engine.dialect.name != "sqlite":
        return
    for table, cols in _TABLE_COLUMNS.items():
        if not _table_exists(engine, table):
            # 新表由 create_all 创建，不需要补列迁移（旧库从未存在该表）
            continue
        existing = _existing_columns(engine, table)
        additions = [f"{name} {ddl}" for name, ddl in cols if name not in existing]
        if additions:
            with engine.connect() as conn:
                for ddl in additions:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {ddl}"))
                conn.commit()
            print(f"[migrate] {table} 新增列: {additions}")
