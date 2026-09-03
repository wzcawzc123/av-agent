"""会议引擎配置级扩展：高/中/低配 + 话筒段 + 天线段。"""
from app.db.session import get_session, get_engine
from app.db.models import Base, Product, SelectionRule
from app.engines.meeting.codec import parse_code
from app.engines.meeting.rules import seed_selection_rules
from app.engines.meeting.selector import select_devices


def _seed(tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.settings.DB_PATH", str(tmp_path / "m.db"))
    engine = get_engine()
    Base.metadata.create_all(engine)
    with get_session(engine) as s:
        for model, name in [
            ("MH-VS08", "8寸音箱"), ("MH-VS10", "10寸音箱"), ("MH-VS12", "12寸音箱"),
            ("MH-L240", "功放240"), ("MH-L440", "功放440"), ("MH-L215", "功放215"),
            ("MH-MA0808", "矩阵8x8"), ("MH-MA1616", "矩阵16x16"),
            ("MH-V5-MIX1004", "调音台10"), ("MH-V5-MIX1812", "调音台18"),
            ("EG65MZ", "65寸屏"), ("EG75MZ", "75寸屏"), ("EG86MZ", "86寸屏"),
            ("MH-U1902MS", "一拖二无线手持"), ("MH-V5-MC5900M", "无线会议主机"),
            ("MH-V5-MC5840C", "无线主席"), ("MH-V5-MC5840D", "无线代表"),
            ("MH-V5-MC6500M", "数字会议主机"), ("MH-V5-MC6710C", "数字主席"),
            ("MH-V5-MC6710D", "数字代表"), ("MH-BK895", "天线分配器"),
            ("MH-QH10", "吸顶天线"),
        ]:
            s.add(Product(model=model, name=name, brand="MAXHUB", description=name))
    return engine


def _rows(engine, code):
    with get_session(engine) as s:
        seed_selection_rules(s)
        return select_devices(s, parse_code(code))


def test_high_config_uses_bigger_devices(tmp_path, monkeypatch):
    engine = _seed(tmp_path, monkeypatch)
    rows = _rows(engine, "12-10-5-0-0-1-1-")
    models = {r["role"]: r["model"] for r in rows}
    assert models["主音箱"] == "MH-VS10" and rows[0]["qty"] == 2  # 120平落 0-150 档
    assert models["功放"] == "MH-L440"


def test_low_config_uses_smaller_devices(tmp_path, monkeypatch):
    engine = _seed(tmp_path, monkeypatch)
    rows = _rows(engine, "12-10-5-0-0-1-3-")
    models = {r["role"]: r["model"] for r in rows}
    assert models["主音箱"] == "MH-VS06" and rows[0]["qty"] == 2  # 低配 120平 用 6.5寸
    assert models["功放"] == "MH-L215"


def test_mic_segment_1_wireless_handheld(tmp_path, monkeypatch):
    engine = _seed(tmp_path, monkeypatch)
    rows = _rows(engine, "12-10-5-0-0-1-2-0-1-")
    roles = [r["role"] for r in rows]
    assert "无线手持" in roles
    mic = [r for r in rows if r["role"] == "无线手持"][0]
    assert mic["model"] == "MH-U1902MS" and mic["qty"] == 1


def test_mic_segment_2_wireless_conference(tmp_path, monkeypatch):
    engine = _seed(tmp_path, monkeypatch)
    rows = _rows(engine, "12-10-5-0-0-1-2-0-2-")
    roles = {r["role"] for r in rows}
    assert {"无线会议主机", "无线主席", "无线代表"} <= roles


def test_antenna_segment_1_adds_antenna(tmp_path, monkeypatch):
    engine = _seed(tmp_path, monkeypatch)
    rows = _rows(engine, "12-10-5-0-0-1-2-0-2-1-")
    roles = {r["role"] for r in rows}
    assert "天线分配器" in roles and "吸顶天线" in roles


def test_no_mic_segment_keeps_basic_only(tmp_path, monkeypatch):
    engine = _seed(tmp_path, monkeypatch)
    rows = _rows(engine, "12-10-5-0-0-1-2-")
    roles = {r["role"] for r in rows}
    assert not (roles & {"手持话筒", "无线会议主机", "天线分配器"})


def test_digital_mic_gets_no_antenna(tmp_path, monkeypatch):
    """数字会议（有线，段3）不应配天线。"""
    engine = _seed(tmp_path, monkeypatch)
    rows = _rows(engine, "12-10-5-0-0-1-2-0-3-1-")
    roles = {r["role"] for r in rows}
    assert "数字会议主机" in roles
    assert not (roles & {"天线分配器", "吸顶天线"})


def test_wireless_handheld_with_antenna(tmp_path, monkeypatch):
    """无线手持（段1）+ 天线段1 → 配天线。"""
    engine = _seed(tmp_path, monkeypatch)
    rows = _rows(engine, "12-10-5-0-0-1-2-0-1-1-")
    roles = {r["role"] for r in rows}
    assert "无线手持" in roles and "天线分配器" in roles
