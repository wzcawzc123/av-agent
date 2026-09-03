"""广播计算引擎：喇叭规格种子 / 点位功率 / 功放选型"""
from app.db.models import AmplifierTier, Base, SpeakerSpec
from app.db.session import get_engine, get_session
from app.engines.broadcast.calculator import compute_zone_power, select_amplifier
from app.engines.broadcast.rules import seed_amplifier_tiers, seed_speaker_specs


def test_compute_zone_power():
    specs = {"MH-V5-PAS04C": 30.0, "PAS71C": 50.0}
    assert compute_zone_power({"MH-V5-PAS04C": 12, "PAS71C": 4}, specs) == 560


def test_compute_zone_power_missing_spec_ignored():
    assert compute_zone_power({"T-999": 5}, {"MH-V5-PAS04C": 30.0}) == 0


def test_select_amplifier():
    tiers = [AmplifierTier(min_w=0, max_w=150, model="MH-L215"),
             AmplifierTier(min_w=150, max_w=250, model="MH-L225")]
    assert select_amplifier(200, tiers) == "MH-L225"
    assert select_amplifier(500, tiers) == ""


def test_seed_speaker_specs(tmp_path):
    engine = get_engine(f"sqlite:///{tmp_path}/t.db")
    Base.metadata.create_all(engine)
    with get_session(engine) as s:
        seed_speaker_specs(s)
        seed_speaker_specs(s)  # 幂等
        assert s.query(SpeakerSpec).count() >= 8


def test_seed_speaker_specs_values(tmp_path):
    engine = get_engine(f"sqlite:///{tmp_path}/t.db")
    Base.metadata.create_all(engine)
    with get_session(engine) as s:
        seed_speaker_specs(s)
        sp = s.query(SpeakerSpec).filter_by(model="MH-V5-PAS04C").first()
        assert sp.power_w == 30 and sp.category == "4寸天花音箱"


def test_seed_replaces_old_itc_models(tmp_path):
    """旧 itc 型号（T-*）在同步种子时被真实库型号替换。"""
    engine = get_engine(f"sqlite:///{tmp_path}/t.db")
    Base.metadata.create_all(engine)
    with get_session(engine) as s:
        s.add(SpeakerSpec(model="T-105", power_w=6, category="天花喇叭"))
        s.add(AmplifierTier(min_w=240, max_w=360, model="T-360"))
        seed_speaker_specs(s)
        seed_amplifier_tiers(s)
        assert s.query(SpeakerSpec).filter_by(model="T-105").first() is None
        assert s.query(AmplifierTier).filter_by(model="T-360").first() is None
        assert s.query(SpeakerSpec).filter_by(model="MH-C8A").first() is not None
        assert s.query(AmplifierTier).filter_by(model="MH-L240").first() is not None
