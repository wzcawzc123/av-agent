"""架构映射测试。"""
import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, DeviceRole
from app.engines.tender.mapping import map_item, systems_covered
from app.engines.tender.model import TenderItem


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    for code, role, kws in [
        ("prosound", "main_speaker", ["音箱", "扬声器", "音柱"]),
        ("display", "led_screen", ["LED", "led", "显示屏"]),
        ("control", "matrix_hdmi", ["矩阵", "切换器"]),
    ]:
        s.add(
            DeviceRole(
                system_code=code,
                role_code=role,
                role_name=role,
                match_keywords=json.dumps(kws, ensure_ascii=False),
            )
        )
    s.commit()
    yield s
    s.close()


class TestMapItem:
    def test_hit_speaker(self, session):
        code, role = map_item(session, "主音箱")
        assert code == "prosound"
        assert role == "main_speaker"

    def test_hit_led(self, session):
        code, role = map_item(session, "LED显示屏")
        assert code == "display"
        assert role == "led_screen"

    def test_long_keyword_priority(self, session):
        # 「切换器」短关键词 vs 「矩阵」——item 含矩阵应中 control
        code, _ = map_item(session, "HDMI矩阵切换器")
        assert code == "control"

    def test_miss(self, session):
        assert map_item(session, "多功能电源") is None


class TestSystemsCovered:
    def test_count(self, session):
        items = [
            TenderItem(1, "主音箱"),
            TenderItem(2, "补声音箱"),
            TenderItem(3, "LED显示屏"),
        ]
        covered = systems_covered(session, items)
        assert covered == {"prosound": 2, "display": 1}

    def test_empty(self, session):
        assert systems_covered(session, []) == {}