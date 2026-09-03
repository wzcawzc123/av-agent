"""引擎相关新表：selection_rules / speaker_specs / led_panel_specs / amplifier_tiers"""
from sqlalchemy import text

from app.db.models import (
    Base,
    AmplifierTier,
    LedPanelSpec,
    SelectionRule,
    SpeakerSpec,
)
from app.db.session import get_engine, get_session


def test_engine_tables_create_and_rw(tmp_path):
    engine = get_engine(f"sqlite:///{tmp_path}/t.db")
    Base.metadata.create_all(engine)
    with get_session(engine) as s:
        s.add(SelectionRule(scene="圆桌", area_min=0, area_max=9999, config_level="中配",
                            device_role="主音箱", model="TK-L208", qty=4, unit="只"))
        s.add(SpeakerSpec(model="T-105", power_w=6, category="天花喇叭"))
        s.add(LedPanelSpec(model="TV-PH250-YZ", module_w_mm=250, module_h_mm=250,
                           res_w=64, res_h=64, type="常规室内屏"))
        s.add(AmplifierTier(min_w=0, max_w=60, model="T-60"))
    with get_session(engine) as s:
        assert s.query(SelectionRule).count() == 1
        assert s.query(SpeakerSpec).count() == 1
        assert s.query(LedPanelSpec).count() == 1
        assert s.query(AmplifierTier).count() == 1
        r = s.query(SelectionRule).first()
        assert r.scene == "圆桌" and r.qty == 4


def test_engine_tables_indexed(tmp_path):
    engine = get_engine(f"sqlite:///{tmp_path}/t.db")
    Base.metadata.create_all(engine)
    with engine.connect() as conn:
        tables = {r[0] for r in conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))}
    for t in ("selection_rules", "speaker_specs", "led_panel_specs", "amplifier_tiers"):
        assert t in tables, f"缺少表 {t}"
