from app.db.models import SelectionRule

# (scene, area_min, area_max, config_level, device_role, model, qty, unit)
# 型号取自产品库实际存在值（MAXHUB 音响/功放/处理器/调音台/显示）
_INIT = [
    ("圆桌", 0, 9999, "中配", "主音箱", "MH-VS08", 2, "只"),
    ("圆桌", 0, 9999, "中配", "功放", "MH-L240", 1, "台"),
    ("圆桌", 0, 9999, "中配", "处理器", "MH-MA0808", 1, "台"),
    ("圆桌", 0, 9999, "中配", "调音台", "MH-V5-MIX1004", 1, "台"),
    ("圆桌", 0, 9999, "中配", "显示", "EG65MZ", 1, "台"),
    ("阶梯", 0, 9999, "中配", "主音箱", "MH-VS10", 4, "只"),
    ("阶梯", 0, 9999, "中配", "功放", "MH-L240", 1, "台"),
    ("阶梯", 0, 9999, "中配", "处理器", "MH-MA0808", 1, "台"),
    ("阶梯", 0, 9999, "中配", "调音台", "MH-V5-MIX1004", 1, "台"),
    ("阶梯", 0, 9999, "中配", "显示", "EG75MZ", 1, "台"),
    ("报告厅", 0, 9999, "中配", "主音箱", "MH-VS12", 4, "只"),
    ("报告厅", 0, 9999, "中配", "功放", "MH-L440", 1, "台"),
    ("报告厅", 0, 9999, "中配", "处理器", "MH-MA1616", 1, "台"),
    ("报告厅", 0, 9999, "中配", "调音台", "MH-V5-MIX1812", 1, "台"),
    ("报告厅", 0, 9999, "中配", "显示", "EG86MZ", 2, "台"),
]


def seed_selection_rules(session):
    """幂等写入/升级选型规则种子：同一 (scene, config, role) 已存在则更新型号，否则插入。"""
    for (scene, amin, amax, lvl, role, model, qty, unit) in _INIT:
        row = session.query(SelectionRule).filter_by(
            scene=scene, config_level=lvl, device_role=role).first()
        if row:
            row.model, row.qty, row.unit, row.area_min, row.area_max = model, qty, unit, amin, amax
        else:
            session.add(SelectionRule(scene=scene, area_min=amin, area_max=amax,
                                      config_level=lvl, device_role=role,
                                      model=model, qty=qty, unit=unit))
    session.commit()
