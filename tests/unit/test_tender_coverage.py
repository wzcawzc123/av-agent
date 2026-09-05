"""能力覆盖合并检测测试。"""
import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, Product
from app.engines.tender.coverage import detect_merge, item_caps, product_caps
from app.engines.tender.model import TenderMatchRow


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    yield s
    s.close()


def _row(idx, name, params, product_id, model, status="matched"):
    return TenderMatchRow(
        source_idx=idx,
        name=name,
        params=params,
        matched_product_id=product_id,
        matched_model=model,
        status=status,
    )


class TestCaps:
    def test_item_caps(self):
        assert "mixer" in item_caps("调音台", ["16路"])

    def test_product_caps_rule_fallback(self, session):
        p = Product(name="数字广播功放", model="GX-1", description="定压功放，内置调音台/USB播放/前置放大")
        session.add(p)
        session.commit()
        caps = product_caps(session, p.id)
        assert "broadcast_amp" in caps
        assert "mixer" in caps


class TestDetectMerge:
    def test_mixer_covered_by_broadcast_host(self, session):
        # 广播主机产品具备 mixer 能力，调音台行可合并
        host = Product(
            name="数字广播功放", model="GX-1", description="定压功放，内置调音台/USB播放/前置放大"
        )
        session.add(host)
        session.commit()
        rows = [
            _row(1, "调音台", ["16路"], host.id, "GX-1"),
            _row(2, "广播功放", ["定压"], host.id, "GX-1"),
        ]
        n = detect_merge(rows, session)
        assert n == 1
        assert rows[0].status == "merged"
        assert rows[0].merged_into == "GX-1"

    def test_same_type_not_merged(self, session):
        # 两个调音台（同类需求）不应互相合并
        host = Product(name="调音台", model="MG-16", description="16路调音台")
        session.add(host)
        session.commit()
        rows = [
            _row(1, "主调音台", ["16路"], host.id, "MG-16"),
            _row(2, "备用调音台", ["12路"], host.id, "MG-16"),
        ]
        assert detect_merge(rows, session) == 0
        assert rows[0].status == "matched"
        assert rows[1].status == "matched"

    def test_no_caps_no_merge(self, session):
        host = Product(name="主音箱", model="SP-1", description="15寸音箱")
        session.add(host)
        session.commit()
        rows = [
            _row(1, "主音箱", ["15寸"], host.id, "SP-1"),
            _row(2, "补声音箱", ["12寸"], host.id, "SP-1"),
        ]
        assert detect_merge(rows, session) == 0