"""迁移回归测试：旧库升级时 products 表必须补齐全量新列（曾漏 brand 等导致启动崩溃）。"""
import tempfile

from sqlalchemy import create_engine, text

from app.db import migrate


def _mk_old_db():
    """建一个 v1.0.0 风格的旧库：4 张表在，products 缺 brand/description/params_json/updated_at。"""
    db = tempfile.mktemp(suffix=".db")
    eng = create_engine(f"sqlite:///{db}")
    with eng.connect() as c:
        c.execute(text("CREATE TABLE products (id INTEGER PRIMARY KEY, name VARCHAR(200), model VARCHAR(100), base_price FLOAT DEFAULT 0, market_price FLOAT DEFAULT 0, category VARCHAR(100) DEFAULT '')"))
        c.execute(text("CREATE TABLE selection_rules (id INTEGER PRIMARY KEY, rule TEXT)"))
        c.execute(text("CREATE TABLE projects (id INTEGER PRIMARY KEY, name TEXT)"))
        c.execute(text("CREATE TABLE config_templates (id INTEGER PRIMARY KEY, name TEXT)"))
        c.commit()
    return db, eng


def test_migrate_products_backfills_all_new_columns():
    db, eng = _mk_old_db()
    try:
        before = migrate._existing_columns(eng, "products")
        assert "brand" not in before, "前置: 旧库不应有 brand"

        migrate.ensure_schema(eng)

        after = migrate._existing_columns(eng, "products")
        required = {"brand", "description", "params_json", "system",
                    "role_tags", "active", "updated_at", "name", "model"}
        assert required <= set(after), f"迁移后仍缺列: {required - set(after)}"
    finally:
        db and __import__("os").remove(db)


def test_migrate_products_idempotent():
    db, eng = _mk_old_db()
    try:
        migrate.ensure_schema(eng)
        col_count_1 = len(migrate._existing_columns(eng, "products"))
        migrate.ensure_schema(eng)
        col_count_2 = len(migrate._existing_columns(eng, "products"))
        assert col_count_1 == col_count_2, "重复执行不应新增列"
    finally:
        db and __import__("os").remove(db)
