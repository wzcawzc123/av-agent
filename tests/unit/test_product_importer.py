import pytest
from openpyxl import Workbook

from app.db.session import get_engine, get_session
from app.db.models import Base, Product
from app.db.product_importer import import_products


@pytest.fixture
def excel_path(tmp_path):
    wb = Workbook()
    ws = wb.active
    ws.append(["产品名称", "型号", "参数", "底价", "市场价", "分类"])
    ws.append(["8寸音箱", "AV-8A", '{"功率":"80W"}', 800, 1200, "音箱"])
    ws.append(["功放", "PA-400", '{"功率":"400W"}', 1500, 2200, "功放"])
    p = tmp_path / "products.xlsx"
    wb.save(p)
    return str(p)


def test_import_new(tmp_path, excel_path):
    engine = get_engine(f"sqlite:///{tmp_path}/t.db")
    Base.metadata.create_all(engine)
    with get_session(engine) as s:
        r = import_products(excel_path, s)
        assert r["inserted"] == 2 and r["updated"] == 0
        assert s.query(Product).count() == 2


def test_import_skips_duplicate(tmp_path, excel_path):
    """重复型号：名称不被覆盖；已有价格不被低价值覆盖（仅补 0 价）。"""
    engine = get_engine(f"sqlite:///{tmp_path}/t.db")
    Base.metadata.create_all(engine)
    with get_session(engine) as s:
        import_products(excel_path, s)
    with get_session(engine) as s:
        wb = Workbook()
        ws = wb.active
        ws.append(["产品名称", "型号", "参数", "底价", "市场价", "分类"])
        ws.append(["8寸音箱改", "AV-8A", "{}", 900, 1300, "音箱"])
        p2 = tmp_path / "p2.xlsx"
        wb.save(p2)
        r = import_products(str(p2), s)
        assert r["inserted"] == 0 and r["updated"] == 0 and r["skipped"] == 1
        got = s.query(Product).filter_by(model="AV-8A").first()
        assert got.name == "8寸音箱" and got.base_price == 800
