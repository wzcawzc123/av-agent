"""品牌就近匹配器与持久化测试。"""
import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, Product
from app.engines.tender import store
from app.engines.tender.matcher import (
    brand_pool,
    brand_seen,
    find_candidates,
    match_item,
    match_items,
)
from app.engines.tender.model import TenderItem


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    yield s
    s.close()


def _add(s, name, model, brand, desc="", params=None):
    p = Product(
        name=name,
        model=model,
        brand=brand,
        description=desc,
        params_json=json.dumps(params or {}, ensure_ascii=False),
    )
    s.add(p)
    s.commit()
    return p


def _seed(session):
    _add(session, "专业功放", "HW-A180", "惠威", "额定功率180W 阻抗8Ω")
    _add(session, "专业功放", "HW-A120", "惠威", "额定功率120W 阻抗8Ω")
    _add(session, "数字功放", "MH-A150", "MAXHUB", "额定功率150W 阻抗8Ω")


class TestBrandPool:
    def test_pool_counts(self, session):
        _seed(session)
        assert brand_pool(session) == {"惠威": 2, "MAXHUB": 1}

    def test_brand_seen(self, session):
        _seed(session)
        assert brand_seen(session, "惠威")
        assert not brand_seen(session, "新品牌")
        assert brand_seen(session, "")  # 无品牌不触发提示

    def test_inactive_excluded(self, session):
        p = _add(session, "旧功放", "OLD-1", "旧牌")
        p.active = 0
        session.commit()
        assert "旧牌" not in brand_pool(session)


class TestMatcher:
    def test_pick_higher(self, session):
        _seed(session)
        item = TenderItem(1, "专业功放", brand="惠威", params=["额定功率150W", "阻抗8Ω"])
        row = match_item(session, item, preference="higher")
        assert row.matched_model == "HW-A180"  # 就近取高
        assert row.status == "matched"

    def test_pick_lower(self, session):
        _seed(session)
        item = TenderItem(1, "专业功放", brand="惠威", params=["额定功率150W", "阻抗8Ω"])
        row = match_item(session, item, preference="lower")
        assert row.matched_model == "HW-A120"  # 就近取低

    def test_brand_filter_beats_global_best(self, session):
        _seed(session)
        # MAXHUB 150W 完全匹配，但指定惠威时应只在惠威内选
        item = TenderItem(1, "专业功放", brand="惠威", params=["额定功率150W", "阻抗8Ω"])
        row = match_item(session, item)
        assert row.brand == "惠威"
        assert row.matched_model.startswith("HW-")

    def test_first_seen_brand_falls_back_global(self, session):
        _seed(session)
        item = TenderItem(1, "专业功放", brand="新品牌", params=["额定功率150W", "阻抗8Ω"])
        row = match_item(session, item)
        assert row.matched_model == "MH-A150"  # 全库最优
        assert "首次出现" in row.remark

    def test_no_match_generates_new(self, session):
        _seed(session)
        item = TenderItem(1, "65英寸触摸屏", brand="", params=["65英寸 触摸"])
        row = match_item(session, item)
        assert row.status == "no_match"
        assert "新增" in row.remark

    def test_partial_status(self, session):
        _seed(session)
        item = TenderItem(1, "大功率功放", brand="惠威", params=["额定功率400W"])
        row = match_item(session, item, preference="higher")
        # 库里最高 180W：不足罚分 (400-180)/400=0.55 -> partial
        assert row.status == "partial"
        assert "确认" in row.remark

    def test_gap_reported_in_remark(self, session):
        _seed(session)
        item = TenderItem(1, "四通道功放", brand="惠威", params=["4通道", "额定功率150W"])
        row = match_item(session, item)
        assert "channels" in row.remark

    def test_match_items_batch(self, session):
        _seed(session)
        items = [
            TenderItem(1, "功放", brand="惠威", params=["额定功率150W"]),
            TenderItem(2, "65英寸屏", params=["65英寸"]),
        ]
        rows = match_items(session, items)
        assert len(rows) == 2
        assert rows[0].status == "matched"
        assert rows[1].status == "no_match"


class TestStore:
    def test_snapshot_roundtrip(self, session):
        _seed(session)
        item = TenderItem(1, "专业功放", brand="惠威", params=["额定功率150W"])
        rows = match_items(session, [item])
        snap = store.save_snapshot(session, 99, rows)
        session.commit()
        loaded = store.load_rows(session, 99)
        assert len(loaded) == 1
        assert loaded[0].matched_model == rows[0].matched_model
        assert loaded[0].params == ["额定功率150W"]
        # 指定快照读取
        assert len(store.load_rows(session, 99, snapshot=snap)) == 1

    def test_latest_snapshot_wins(self, session):
        _seed(session)
        r1 = match_items(session, [TenderItem(1, "功放A", params=["额定功率150W"])])
        store.save_snapshot(session, 7, r1)
        session.commit()
        r2 = match_items(session, [TenderItem(2, "功放B", params=["额定功率120W"])])
        store.save_snapshot(session, 7, r2)
        session.commit()
        loaded = store.load_rows(session, 7)
        assert [r.name for r in loaded] == ["功放B"]

    def test_update_row(self, session):
        _seed(session)
        rows = match_items(session, [TenderItem(1, "功放", brand="惠威", params=["额定功率150W"])])
        store.save_snapshot(session, 5, rows)
        session.commit()
        m = session.query(store.TenderMatch).first()
        assert store.update_row(session, m.id, status="merged", remark="功能已集成")
        session.commit()
        loaded = store.load_rows(session, 5)
        assert loaded[0].status == "merged"

    def test_to_bom_rows(self, session):
        _seed(session)
        rows = match_items(
            session,
            [
                TenderItem(1, "专业功放", brand="惠威", params=["额定功率150W"]),
                TenderItem(2, "65英寸屏", params=["65英寸"]),
            ],
        )
        rows[1].status = "merged"  # 模拟功能集成
        bom = store.to_bom_rows(rows)
        assert len(bom) == 1  # merged 不进 BOM
        assert bom[0]["model"] == rows[0].matched_model
        assert bom[0]["type"] == "专业功放"
        assert bom[0]["unit"] == "台"
