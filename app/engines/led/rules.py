from app.db.models import LedPanelSpec

_PANELS = [
    ("TV-PH250-YZ", 250, 250, 64, 64, "常规室内屏"),
    ("TV-PH200-YZ", 200, 200, 80, 80, "常规室内屏"),
    ("TV-PH150-YZ", 150, 150, 106, 106, "常规室内屏"),
    ("TV-PH100-YZ", 100, 100, 160, 160, "常规室内屏"),
]


def seed_led_specs(session):
    """幂等写入屏体/模组规格（逆向自 itc 常见屏表）。"""
    for model, mw, mh, rw, rh, typ in _PANELS:
        if not session.query(LedPanelSpec).filter_by(model=model).first():
            session.add(LedPanelSpec(model=model, module_w_mm=mw, module_h_mm=mh,
                                     res_w=rw, res_h=rh, type=typ))
    session.commit()
