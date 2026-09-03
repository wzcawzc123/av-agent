"""轻量 schema 迁移：SQLite 上按需补列（不引入 Alembic）。"""
from sqlalchemy import text


def _existing_columns(engine, table: str) -> set[str]:
    with engine.connect() as conn:
        rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
    return {r[1] for r in rows}


def ensure_schema(engine):
    """为既有表补齐新增列（幂等）。"""
    cols = _existing_columns(engine, "selection_rules")
    additions = []
    if "mic_level" not in cols:
        additions.append("mic_level VARCHAR(20)")
    if "antenna_level" not in cols:
        additions.append("antenna_level VARCHAR(20)")
    if additions:
        with engine.connect() as conn:
            for ddl in additions:
                conn.execute(text(f"ALTER TABLE selection_rules ADD COLUMN {ddl}"))
            conn.commit()
        print(f"[migrate] selection_rules 新增列: {additions}")
