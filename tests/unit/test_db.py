from app.db.session import get_engine, get_session
from app.db.models import Base, Product, Project, Setting


def test_engine_creates_tables(tmp_path):
    engine = get_engine(f"sqlite:///{tmp_path}/t.db")
    Base.metadata.create_all(engine)
    with engine.connect() as conn:
        tables = [r[0] for r in conn.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='table'")]
    assert "products" in tables and "projects" in tables and "settings" in tables


def test_product_crud(tmp_path):
    engine = get_engine(f"sqlite:///{tmp_path}/t.db")
    Base.metadata.create_all(engine)
    with get_session(engine) as s:
        p = Product(name="8寸音箱", model="AV-8A", params_json='{"功率":"80W"}',
                    base_price=800, market_price=1200, category="音箱")
        s.add(p)
        s.commit()
        got = s.query(Product).filter_by(model="AV-8A").first()
        assert got is not None and got.name == "8寸音箱"
        assert got.market_price == 1200
