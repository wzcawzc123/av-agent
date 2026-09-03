from app.db.models import SelectionRule

_INIT = [
    ("圆桌", 0, 9999, "中配", "主音箱", "TK-L208", 4, "只"),
    ("圆桌", 0, 9999, "中配", "功放", "TA-2900", 1, "台"),
    ("圆桌", 0, 9999, "中配", "处理器", "TS-P440", 1, "台"),
    ("圆桌", 0, 9999, "中配", "调音台", "TS-24PD-8", 1, "台"),
    ("圆桌", 0, 9999, "中配", "显示", "TV-86810", 1, "台"),
    ("阶梯", 0, 9999, "中配", "主音箱", "TK-L208", 4, "只"),
    ("阶梯", 0, 9999, "中配", "功放", "TA-2900", 1, "台"),
    ("阶梯", 0, 9999, "中配", "处理器", "TS-P440", 1, "台"),
    ("阶梯", 0, 9999, "中配", "调音台", "TS-24PD-8", 1, "台"),
    ("阶梯", 0, 9999, "中配", "显示", "TV-8105", 1, "台"),
    ("报告厅", 0, 9999, "中配", "主音箱", "LA-2100K", 2, "只"),
    ("报告厅", 0, 9999, "中配", "功放", "TA-2900", 1, "台"),
    ("报告厅", 0, 9999, "中配", "处理器", "TS-P440", 1, "台"),
    ("报告厅", 0, 9999, "中配", "调音台", "TS-24PD-8", 1, "台"),
    ("报告厅", 0, 9999, "中配", "显示", "TV-810SP", 1, "台"),
]


def seed_selection_rules(session):
    """幂等写入选型规则种子（场景×配置→设备角色→型号数量）。"""
    for (scene, amin, amax, lvl, role, model, qty, unit) in _INIT:
        exists = session.query(SelectionRule).filter_by(
            scene=scene, config_level=lvl, device_role=role, model=model).first()
        if not exists:
            session.add(SelectionRule(scene=scene, area_min=amin, area_max=amax,
                                      config_level=lvl, device_role=role,
                                      model=model, qty=qty, unit=unit))
    session.commit()
