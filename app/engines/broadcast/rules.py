from app.db.models import SpeakerSpec

_SPEAKERS = [
    ("T-105", 6, "天花喇叭"), ("T-601", 10, "壁挂喇叭"),
    ("T-701A", 10, "壁挂音柱"), ("T-802", 25, "防水音柱"),
    ("T-803", 35, "防水音柱"), ("T-804", 45, "防水音柱"),
    ("T-904", 120, "大功率防水音柱"), ("T-300", 15, "草地音响"),
]


def seed_speaker_specs(session):
    """幂等写入喇叭功率规格（逆向自 itc 点位表）。"""
    for model, w, cat in _SPEAKERS:
        if not session.query(SpeakerSpec).filter_by(model=model).first():
            session.add(SpeakerSpec(model=model, power_w=w, category=cat))
    session.commit()
