"""会议选型引擎：codec 编码解析 / 选型规则种子 / 选型主逻辑"""
from app.db.models import Base, Product, SelectionRule
from app.db.session import get_engine, get_session
from app.engines.meeting.codec import MeetingParams, parse_code
from app.engines.meeting.rules import seed_selection_rules
from app.engines.meeting.selector import select_devices


def test_parse_code_full():
    p = parse_code("12-10-4-0-0-1-2-0-1-0-")
    assert p.scene == "圆桌"
    assert p.length_m == 12 and p.width_m == 10 and p.height_m == 4
    assert p.config == "中配"
    assert p.area == 120


def test_parse_code_missing_segments():
    p = parse_code("10-4-")
    assert p.height_m == 0 and p.config == "中配" and p.area == 40


def test_parse_code_bad_scene_falls_back():
    p = parse_code("99-5-5-")
    assert p.scene == "圆桌"


def test_parse_code_scene_and_config_mapping():
    assert parse_code("1-1-1-1-1-3-1-").scene == "报告厅"
    assert parse_code("1-1-1-1-1-2-3-").config == "低配"


def test_seed_selection_rules(tmp_path):
    engine = get_engine(f"sqlite:///{tmp_path}/t.db")
    Base.metadata.create_all(engine)
    with get_session(engine) as s:
        seed_selection_rules(s)
        seed_selection_rules(s)  # 幂等
        n = s.query(SelectionRule).count()
        assert n >= 15


def test_select_devices_meeting(tmp_path):
    engine = get_engine(f"sqlite:///{tmp_path}/t.db")
    Base.metadata.create_all(engine)
    with get_session(engine) as s:
        s.add(Product(name="8寸多功能专业音箱", model="MH-VS08", brand="MAXHUB",
                      description="8寸两分频无源音箱"))
        s.add(Product(name="2*400W数字功放", model="MH-L240", brand="MAXHUB",
                      description="双通道数字功放"))
        s.commit()
        seed_selection_rules(s)
        rows = select_devices(s, parse_code("1-10-5-"))
        assert len(rows) >= 5
        tk = [r for r in rows if r["model"] == "MH-VS08"][0]
        assert tk["name"] == "8寸多功能专业音箱" and tk["qty"] == 2
        assert tk["price"] == 0


def test_select_devices_unknown_scene_falls_back(tmp_path):
    engine = get_engine(f"sqlite:///{tmp_path}/t.db")
    Base.metadata.create_all(engine)
    with get_session(engine) as s:
        seed_selection_rules(s)
        rows = select_devices(s, parse_code("88-10-5-"))
        assert len(rows) >= 5  # 回落到圆桌规则
