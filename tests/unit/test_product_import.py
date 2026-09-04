"""产品导入器单测：分类打标、重复跳过、带价格导入与二次补价。"""
import pytest


@pytest.fixture()
def db(tmp_path):
    from app.db.session import get_engine, get_session
    from app.db.migrate import ensure_schema
    from app.db.models import Base
    eng = get_engine(f"sqlite:///{tmp_path / 'imp.db'}")
    Base.metadata.create_all(eng)
    ensure_schema(eng)
    with get_session(eng) as s:
        yield s



def test_import_with_price_and_backfill(tmp_path, db):
    """带价格列清单导入 + 二次导入补价。"""
    from openpyxl import Workbook
    from app.db.product_importer import import_products
    from app.db.models import Product

    def make(path, rows, with_price=True):
        wb = Workbook()
        ws = wb.active
        header = ["产品名称", "型号", "底价", "市场价", "单位"] if with_price else ["产品名称", "型号", "单位"]
        ws.append(header)
        for r in rows:
            ws.append(r if with_price else [r[0], r[1], r[2]])
        wb.save(path)

    p1 = tmp_path / "p1.xlsx"
    make(p1, [["音箱A", "SPK-A", "只"]], with_price=False)
    import_products(str(p1), db)
    a0 = db.query(Product).filter_by(model="SPK-A").first()
    assert a0.market_price == 0

    p2 = tmp_path / "p2.xlsx"
    make(p2, [["音箱B", "SPK-B", None, 2600, "只"]])
    r = import_products(str(p2), db)
    assert r["inserted"] == 1
    b = db.query(Product).filter_by(model="SPK-B").first()
    assert b.base_price == 0 and b.market_price == 2600

    p3 = tmp_path / "p3.xlsx"
    make(p3, [["音箱A补价", "SPK-A", 1300, 1900, "只"]])
    r3 = import_products(str(p3), db)
    assert r3["updated"] == 1
    a = db.query(Product).filter_by(model="SPK-A").first()
    assert a.base_price == 1300 and a.market_price == 1900
