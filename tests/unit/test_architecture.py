"""P0 架构新增模块单测：系统目录/品牌约束/角色引擎/composer 无 LLM 链路。"""
import json

import pytest

from app.catalog import backfill_role, brand_allowed, parse_brand_constraints, search_products
from app.db.models import Base, DeviceRole, Product, System
from app.db.session import get_engine, get_session
from app.db.system_seed import seed_system_catalog
from app.db.tagger import infer_role_tags, infer_system, tag_product
from app.engines.composer import backfill, build_rows_for_systems
from app.engines.systems.engines import (
    build_control, build_display, build_distributed, build_lighting,
    build_paperless, build_prosound, build_speech,
)
from app.engines.systems.scene import infer_systems, resolve_seats


@pytest.fixture()
def db():
    engine = get_engine("sqlite://")
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with get_session(engine) as s:
        seed_system_catalog(s)
        s.add(Product(name="8寸专业音箱", model="HV-8A", brand="惠威",
                      system="prosound", role_tags='["main_speaker"]',
                      base_price=800, market_price=1200))
        s.add(Product(name="专业功放", model="HV-PA250", brand="惠威",
                      system="prosound", role_tags='["amplifier"]',
                      base_price=1500, market_price=2200))
        s.add(Product(name="MAXHUB会议平板", model="W85PN3", brand="MAXHUB",
                      system="display", role_tags='["single_display"]',
                      base_price=9000, market_price=12000))
        s.add(Product(name="HDMI矩阵", model="MH-MX0808", brand="MAXHUB",
                      system="control", role_tags='["matrix_hdmi"]',
                      base_price=5000, market_price=6500))
        s.flush()
    yield engine


def test_seed_system_catalog(db):
    with get_session(db) as s:
        systems = {r.code for r in s.query(System).all()}
        assert {"prosound", "speech", "display", "paperless", "control",
                "distributed", "lighting", "broadcast", "videoconf"} <= systems
        assert s.query(DeviceRole).filter_by(role_code="main_speaker").count() == 1


@pytest.mark.parametrize("text,expected", [
    (None, {"mode": "any"}),
    ("", {"mode": "any"}),
    ("不限", {"mode": "any"}),
    ("惠威", {"mode": "specified", "all": ["惠威"]}),
    ("惠威和MAXHUB组合", {"mode": "specified", "all": ["惠威", "MAXHUB"]}),
    ("全部用惠威", {"mode": "specified", "all": ["惠威"]}),
    ("都用MAXHUB", {"mode": "specified", "all": ["MAXHUB"]}),
    ("扩声和发言都用MAXHUB",
     {"mode": "by_system", "systems": {"prosound": ["MAXHUB"], "speech": ["MAXHUB"]}}),
    ("扩声用惠威，显示用MAXHUB",
     {"mode": "by_system", "systems": {"prosound": ["惠威"], "display": ["MAXHUB"]}}),
])
def test_parse_brand_constraints(text, expected):
    assert parse_brand_constraints(text) == expected


def test_brand_allowed(db):
    bc = parse_brand_constraints("扩声用惠威，显示用MAXHUB")
    assert brand_allowed(bc, "prosound") == ["惠威"]
    assert brand_allowed(bc, "display") == ["MAXHUB"]
    assert brand_allowed(bc, "speech") is None  # 未指定系统不限品牌
    assert brand_allowed({"mode": "any"}, "prosound") is None


def test_search_products_role_and_brand(db):
    with get_session(db) as s:
        hits = search_products(s, system="prosound", role="main_speaker", brand=["惠威"])
        assert len(hits) == 1 and hits[0]["model"] == "HV-8A"
        # 品牌不符则回退不限品牌检索（backfill 层）
        filled = backfill_role(s, "prosound", "main_speaker", ["MAXHUB"])
        assert filled is not None  # 允许回退


def test_tagger_inference():
    t = tag_product("8寸专业音箱", "音箱/专业音箱", "惠威")
    assert t["system"] == "prosound" and "main_speaker" in t["role_tags"]
    t2 = tag_product("MAXHUB会议平板", "会议平板", "MAXHUB")
    assert t2["system"] == "display"
    t3 = tag_product("无纸化升降屏终端", "无纸化", "")
    assert t3["system"] == "paperless" and "paperless_terminal" in t3["role_tags"]
    assert infer_system("普通交换机", "") == ""
    assert infer_role_tags("主席台实木家具", "", "speech") == []  # 黑名单


def test_infer_systems_and_seats():
    assert infer_systems({"systems": ["control", "display"]}) == ["control", "display"]
    assert "lighting" in infer_systems({"scene": "报告厅"})
    assert "broadcast" in infer_systems({"scene": "学校园区广播"})
    assert infer_systems({"scene": "智能会议室"}) == ["prosound", "speech", "display", "paperless"]
    assert resolve_seats({"area": 60})["delegate"] == 6
    assert resolve_seats({"area": 280})["delegate"] == 19
    assert resolve_seats({"seats": {"chairman": 1, "delegate": 10}})["delegate"] == 10


def test_builders_produce_role_rows():
    rows = build_prosound({"area": 280, "scene": "智能会议室"})
    by_role = {r["role"]: r for r in rows}
    assert by_role["main_speaker"]["qty"] == 6
    assert by_role["amplifier"]["qty"] == 3
    assert "audio_processor" in by_role  # >200㎡ 配处理器

    speech = build_speech({"seats": {"chairman": 1, "delegate": 10}})
    by_role = {r["role"]: r for r in speech}
    assert by_role["delegate_unit"]["qty"] == 10

    ctl = build_control({"signal_sources": 8, "display_count": 2})
    assert any(r["role"] == "matrix_hdmi" and "8进8出" in r["spec"] for r in ctl)

    disp = build_display({"area": 280, "scene": "智能会议室"})
    assert any(r["role"] == "single_display" and "98寸" in r["spec"] for r in disp)
    splice = build_display({"scene": "指挥中心", "display": {"mode": "splicing", "cols": 3, "rows": 2}})
    assert any(r["role"] == "lcd_splicing" and r["qty"] == 6 for r in splice)
    led = build_display({"scene": "led会议室", "display": {"mode": "led", "pitch": 1.86, "w": 4, "h": 2}})
    assert any(r["role"] == "led_screen" and r["qty"] == 8 for r in led)

    pl = build_paperless({"seats": {"chairman": 1, "delegate": 10}})
    assert any(r["role"] == "paperless_terminal" and r["qty"] == 11 for r in pl)

    dist = build_distributed({"signal_sources": 4, "display_count": 2})
    assert any(r["role"] == "encode_node" and r["qty"] == 4 for r in dist)

    light = build_lighting({"area": 150, "scene": "智能会议室"})
    assert any(r["role"] == "panel_light" for r in light)
    stage = build_lighting({"scene": "舞台演出"})
    assert any(r["role"] == "beam_light" for r in stage)


def test_composer_backfill_with_brand_constraint(db):
    with get_session(db) as s:
        slots = {"area": 280, "scene": "智能会议室", "brand": "扩声用惠威，显示用MAXHUB"}
        rows = build_rows_for_systems(slots)
        assert rows, "引擎应产出角色行"
        devs = backfill(rows, s, parse_brand_constraints(slots["brand"]))
        filled_prosound = [d for d in devs if d["system"] == "prosound" and d["model"]]
        filled_display = [d for d in devs if d["system"] == "display" and d["model"]]
        assert filled_prosound and all(d["brand"] == "惠威" for d in filled_prosound)
        assert filled_display and all(d["brand"] == "MAXHUB" for d in filled_display)
        pending = [d for d in devs if not d["model"]]
        assert pending and all("待选型" in d["note"] for d in pending)
