"""广播计算引擎：喇叭规格种子 / 点位功率 / 功放选型"""
from app.db.models import AmplifierTier, Base, SpeakerSpec
from app.db.session import get_engine, get_session
from app.engines.broadcast.calculator import compute_zone_power, select_amplifier
from app.engines.broadcast.rules import seed_speaker_specs


def test_compute_zone_power():
    specs = {"T-105": 6.0, "T-601": 10.0}
    assert compute_zone_power({"T-105": 12, "T-601": 4}, specs) == 112


def test_compute_zone_power_missing_spec_ignored():
    assert compute_zone_power({"T-999": 5}, {"T-105": 6.0}) == 0


def test_select_amplifier():
    tiers = [AmplifierTier(min_w=0, max_w=60, model="T-60"),
             AmplifierTier(min_w=60, max_w=120, model="T-120")]
    assert select_amplifier(80, tiers) == "T-120"
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
        t105 = s.query(SpeakerSpec).filter_by(model="T-105").first()
        assert t105.power_w == 6 and t105.category == "天花喇叭"
