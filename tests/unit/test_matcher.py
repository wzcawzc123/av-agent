"""参数智能匹配单测：规范化、规格提取、打分排序、核心名词。"""

import pytest

from app.catalog.matcher import (
    BRAND_ALIASES,
    _core_term,
    extract_specs,
    match_products,
    normalize,
)


def test_normalize_units_and_alias():
    assert normalize("300W 功放 8Ω 75英寸") == "300w功放8ω75寸"
    assert normalize("MAXHUB 会议平板") == "MAXHUB会议平板"
    assert normalize("惠威 音箱 75英寸") == "惠威音箱75寸"


def test_extract_specs():
    assert extract_specs("300W 功放 8Ω") == {"power_w": 300.0, "impedance": 8.0}
    assert extract_specs("75寸会议平板") == {"size_inch": 75.0}
    assert extract_specs("P2.5 LED屏") == {"pitch_mm": 2.5}
    assert extract_specs("音箱") == {}
    # 型号内字母+数字不误判为点距（回归：PAS28LA 不应提取 pitch）
    assert extract_specs("型号 PAS28LA 音箱") == {}


def test_core_term():
    assert _core_term("无线话筒") == "话筒"
    assert _core_term("300W 专业功放") == "功放"
    assert _core_term("MAXHUB 会议平板 75寸") == "平板"
    assert _core_term("音箱") == "音箱"


def test_brand_aliases_cover_common_brands():
    assert normalize("sony 摄像机") == "SONY摄像机"
    assert normalize("领效 会议平板") == "MAXHUB会议平板"
    assert normalize("利亚德 LED屏") == "利亚德led屏"


@pytest.fixture
def engine(tmp_path):
    from app.db.migrate import ensure_schema
    from app.db.models import Base, Product
    from app.db.session import get_engine, get_session

    eng = get_engine(f"sqlite:///{tmp_path}/match.db")
    Base.metadata.create_all(eng)
    ensure_schema(eng)
    with get_session(eng) as s:
        s.add(Product(name="专业功放", model="AMP-300P", brand="测试音响",
                      params_json='{"功率":"300W","阻抗":"8Ω"}', market_price=3800))
        s.add(Product(name="数字功放", model="MH-L240", brand="MAXHUB",
                      params_json='{"功率":"400W","阻抗":"8Ω"}', market_price=5200))
        s.add(Product(name="吸顶音箱", model="SPK-8C", brand="测试音响",
                      params_json='{"尺寸":"8寸","功率":"60W"}', market_price=880))
        s.add(Product(name="LED显示屏", model="LED-P2", brand="测试显示",
                      params_json='{"点距":"P2"}', market_price=48000))
    return eng


def test_match_power_amplifier(engine):
    from app.db.session import get_session

    with get_session(engine) as s:
        ms = match_products(s, "300W 功放", limit=3)
        assert ms and ms[0]["product"]["model"] in ("AMP-300P", "MH-L240")
        assert ms[0]["score"] >= 60
        assert "匹配" in ms[0]["reason"]


def test_match_speaker(engine):
    from app.db.session import get_session

    with get_session(engine) as s:
        ms = match_products(s, "8寸音箱", limit=3)
        assert ms and ms[0]["product"]["model"] == "SPK-8C"
        assert ms[0]["score"] >= 75  # 高置信
        assert "尺寸" in ms[0]["reason"] or "匹配" in ms[0]["reason"]


def test_match_led_pitch(engine):
    from app.db.session import get_session

    with get_session(engine) as s:
        ms = match_products(s, "P2 LED屏", limit=3)
        assert ms and ms[0]["product"]["model"] == "LED-P2"


def test_match_empty_query(engine):
    from app.db.session import get_session

    with get_session(engine) as s:
        assert match_products(s, "") == []
        assert match_products(s, "  ") == []
