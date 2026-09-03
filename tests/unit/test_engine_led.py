"""LED 排布引擎：屏体规格种子 / 排布计算"""
from app.db.models import Base, LedPanelSpec
from app.db.session import get_engine, get_session
from app.engines.led.layout import calc_layout
from app.engines.led.rules import seed_led_specs


def test_calc_layout_round_mode():
    panel = LedPanelSpec(model="TV-PH250-YZ", module_w_mm=250, module_h_mm=250,
                         res_w=64, res_h=64, type="常规室内屏")
    r = calc_layout(6, 4, panel, "就近")
    assert r["count_w"] == 24 and r["count_h"] == 16
    assert abs(r["actual_w_m"] - 6.0) < 1e-6
    assert r["res_w"] == 24 * 64 and r["res_h"] == 16 * 64


def test_calc_layout_ceil_floor():
    panel = LedPanelSpec(model="P2", module_w_mm=320, module_h_mm=160,
                         res_w=160, res_h=80, type="常规室内屏")
    assert calc_layout(5, 3, panel, "向上")["count_w"] == 16
    assert calc_layout(5, 3, panel, "向下")["count_w"] == 15


def test_calc_layout_power_and_cable():
    panel = LedPanelSpec(model="P2", module_w_mm=320, module_h_mm=160,
                         res_w=160, res_h=80, type="常规室内屏")
    r = calc_layout(6.4, 3.2, panel, "就近")
    # 6.4m/0.32=20 块，3.2m/0.16=20 块 → 20.48m² *300W *1.3 ≈ 7.99kW
    assert r["count_w"] == 20 and r["count_h"] == 20
    assert 7.0 < r["power_kw"] < 9.0
    assert r["cable_mm2"] >= 200


def test_seed_led_specs(tmp_path):
    engine = get_engine(f"sqlite:///{tmp_path}/t.db")
    Base.metadata.create_all(engine)
    with get_session(engine) as s:
        seed_led_specs(s)
        seed_led_specs(s)  # 幂等
        assert s.query(LedPanelSpec).count() >= 4
