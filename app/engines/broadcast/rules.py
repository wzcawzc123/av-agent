from app.db.models import AmplifierTier, SpeakerSpec

_SPEAKERS = [
    ("T-105", 6, "天花喇叭"), ("T-601", 10, "壁挂喇叭"),
    ("T-701A", 10, "壁挂音柱"), ("T-802", 25, "防水音柱"),
    ("T-803", 35, "防水音柱"), ("T-804", 45, "防水音柱"),
    ("T-904", 120, "大功率防水音柱"), ("T-300", 15, "草地音响"),
]

_AMPLIFIERS = [  # (min_w, max_w, model)
    (0, 60, "T-60"), (60, 120, "T-120"), (120, 240, "T-240"),
    (240, 360, "T-360"), (360, 500, "T-500"),
]


def seed_speaker_specs(session):
    """幂等写入喇叭功率规格（逆向自 itc 点位表）。"""
    for model, w, cat in _SPEAKERS:
        if not session.query(SpeakerSpec).filter_by(model=model).first():
            session.add(SpeakerSpec(model=model, power_w=w, category=cat))
    session.commit()


def seed_amplifier_tiers(session):
    """幂等写入功放功率档位（区域总功率×1.5 后匹配）。"""
    for mn, mx, model in _AMPLIFIERS:
        if not session.query(AmplifierTier).filter_by(model=model).first():
            session.add(AmplifierTier(min_w=mn, max_w=mx, model=model))
    session.commit()
