from app.db.models import SelectionRule

# 面积分档（对应 100平/200平/300平 成套方案口径）
# (scene, area_min, area_max, config_level, device_role, model, qty, unit)
_BASE_INIT = [
    ("圆桌", 0, 150, "中配", "主音箱", "MH-VS08", 2, "只"),
    ("圆桌", 150, 250, "中配", "主音箱", "MH-VS10", 4, "只"),
    ("圆桌", 250, 9999, "中配", "主音箱", "MH-VS12", 6, "只"),
    ("圆桌", 0, 9999, "中配", "功放", "MH-L240", 1, "台"),
    ("圆桌", 0, 9999, "中配", "处理器", "MH-MA0808", 1, "台"),
    ("圆桌", 0, 9999, "中配", "调音台", "MH-V5-MIX1004", 1, "台"),
    ("圆桌", 0, 9999, "中配", "显示", "EG65MZ", 1, "台"),
    ("圆桌", 0, 150, "高配", "主音箱", "MH-VS10", 2, "只"),
    ("圆桌", 150, 250, "高配", "主音箱", "MH-VS10", 4, "只"),
    ("圆桌", 250, 9999, "高配", "主音箱", "MH-VS12", 6, "只"),
    ("圆桌", 0, 9999, "高配", "功放", "MH-L440", 1, "台"),
    ("圆桌", 0, 9999, "高配", "处理器", "MH-MA1616", 1, "台"),
    ("圆桌", 0, 9999, "高配", "调音台", "MH-V5-MIX1812", 1, "台"),
    ("圆桌", 0, 9999, "高配", "显示", "EG86MZ", 1, "台"),
    ("圆桌", 0, 150, "低配", "主音箱", "MH-VS06", 2, "只"),
    ("圆桌", 150, 250, "低配", "主音箱", "MH-VS08", 4, "只"),
    ("圆桌", 250, 9999, "低配", "主音箱", "MH-VS10", 4, "只"),
    ("圆桌", 0, 9999, "低配", "功放", "MH-L215", 1, "台"),
    ("圆桌", 0, 9999, "低配", "处理器", "MH-MA0808", 1, "台"),
    ("圆桌", 0, 9999, "低配", "调音台", "MH-V5-MIX0802", 1, "台"),
    ("圆桌", 0, 9999, "低配", "显示", "EG65MZ", 1, "台"),
    ("阶梯", 0, 150, "中配", "主音箱", "MH-VS10", 4, "只"),
    ("阶梯", 150, 250, "中配", "主音箱", "MH-VS12", 4, "只"),
    ("阶梯", 250, 9999, "中配", "主音箱", "MH-VS12", 6, "只"),
    ("阶梯", 0, 9999, "中配", "功放", "MH-L240", 1, "台"),
    ("阶梯", 0, 9999, "中配", "处理器", "MH-MA0808", 1, "台"),
    ("阶梯", 0, 9999, "中配", "调音台", "MH-V5-MIX1004", 1, "台"),
    ("阶梯", 0, 9999, "中配", "显示", "EG75MZ", 1, "台"),
    ("阶梯", 0, 150, "高配", "主音箱", "MH-VS12", 4, "只"),
    ("阶梯", 150, 250, "高配", "主音箱", "MH-VS12", 6, "只"),
    ("阶梯", 250, 9999, "高配", "主音箱", "MH-VS12", 8, "只"),
    ("阶梯", 0, 9999, "高配", "功放", "MH-L440", 1, "台"),
    ("阶梯", 0, 9999, "高配", "处理器", "MH-MA1616", 1, "台"),
    ("阶梯", 0, 9999, "高配", "调音台", "MH-V5-MIX1812", 1, "台"),
    ("阶梯", 0, 9999, "高配", "显示", "EG86MZ", 2, "台"),
    ("阶梯", 0, 150, "低配", "主音箱", "MH-VS08", 4, "只"),
    ("阶梯", 150, 250, "低配", "主音箱", "MH-VS10", 4, "只"),
    ("阶梯", 250, 9999, "低配", "主音箱", "MH-VS10", 6, "只"),
    ("阶梯", 0, 9999, "低配", "功放", "MH-L215", 1, "台"),
    ("阶梯", 0, 9999, "低配", "处理器", "MH-MA0808", 1, "台"),
    ("阶梯", 0, 9999, "低配", "调音台", "MH-V5-MIX1004", 1, "台"),
    ("阶梯", 0, 9999, "低配", "显示", "EG65MZ", 1, "台"),

("报告厅", 0, 150, "中配", "主音箱", "MH-VS12", 4, "只"),
("报告厅", 150, 250, "中配", "主音箱", "MH-VS12", 6, "只"),
("报告厅", 250, 9999, "中配", "主音箱", "MH-VS12", 8, "只"),
("报告厅", 0, 9999, "中配", "功放", "MH-L440", 1, "台"),
("报告厅", 0, 9999, "中配", "处理器", "MH-MA1616", 1, "台"),
("报告厅", 0, 9999, "中配", "调音台", "MH-V5-MIX1812", 1, "台"),
("报告厅", 0, 9999, "中配", "显示", "EG86MZ", 2, "台"),
("报告厅", 0, 150, "高配", "主音箱", "MH-V5-PAS15", 4, "只"),
("报告厅", 150, 250, "高配", "主音箱", "MH-V5-PAS15", 6, "只"),
("报告厅", 250, 9999, "高配", "主音箱", "MH-V5-PAS15", 8, "只"),
("报告厅", 0, 9999, "高配", "功放", "MH-V5-PA2100", 2, "台"),
("报告厅", 0, 9999, "高配", "处理器", "MH-MA1616", 1, "台"),
("报告厅", 0, 9999, "高配", "调音台", "MH-V5-MIX1812", 1, "台"),
("报告厅", 0, 9999, "高配", "显示", "EG86MZ", 2, "台"),
("报告厅", 0, 150, "低配", "主音箱", "MH-VS12", 2, "只"),
("报告厅", 150, 250, "低配", "主音箱", "MH-VS12", 4, "只"),
("报告厅", 250, 9999, "低配", "主音箱", "MH-VS12", 6, "只"),
("报告厅", 0, 9999, "低配", "功放", "MH-L240", 1, "台"),
("报告厅", 0, 9999, "低配", "处理器", "MH-MA0808", 1, "台"),
("报告厅", 0, 9999, "低配", "调音台", "MH-V5-MIX1004", 1, "台"),
("报告厅", 0, 9999, "低配", "显示", "EG75MZ", 1, "台"),
]

# 话筒段种子：1=无线手持 2=无线会议 3=数字会议（三场景通用）
_MIC_INIT = [
    ("无线手持", "MH-U1902MS", 1, "套", "1"),
    ("无线会议主机", "MH-V5-MC5900M", 1, "台", "2"),
    ("无线主席", "MH-V5-MC5840C", 1, "台", "2"),
    ("无线代表", "MH-V5-MC5840D", 4, "台", "2"),
    ("数字会议主机", "MH-V5-MC6500M", 1, "台", "3"),
    ("数字主席", "MH-V5-MC6710C", 1, "台", "3"),
    ("数字代表", "MH-V5-MC6710D", 4, "台", "3"),
]

# 天线段种子：天线仅配套无线话筒（段1手持/段2无线会议）
_ANT_INIT = [
    ("天线分配器", "MH-BK895", 1, "台", "1,2", "1"),
    ("吸顶天线", "MH-QH10", 2, "只", "1,2", "1"),
]


def _upsert(session, scene, amin, amax, role, model, qty, unit, mic=None, ant=None,
            config_level="中配"):
    row = (session.query(SelectionRule)
           .filter_by(scene=scene, config_level=config_level, device_role=role,
                      area_min=amin, area_max=amax, mic_level=mic, antenna_level=ant)
           .first())
    if row is None:
        row = (session.query(SelectionRule)
               .filter_by(scene=scene, config_level=config_level, device_role=role,
                          area_min=amin, area_max=amax, mic_level=None, antenna_level=None)
               .first())
        if row:
            row.mic_level, row.antenna_level = mic, ant
    if row:
        row.model, row.qty, row.unit = model, qty, unit
    else:
        session.add(SelectionRule(scene=scene, config_level=config_level,
                                  device_role=role, model=model, qty=qty,
                                  unit=unit, area_min=amin, area_max=amax,
                                  mic_level=mic, antenna_level=ant))


def seed_selection_rules(session):
    """幂等写入/升级选型规则种子：面积分档基础配置 + 话筒段 + 天线段。"""
    for (scene, amin, amax, cfg, role, model, qty, unit) in _BASE_INIT:
        _upsert(session, scene, amin, amax, role, model, qty, unit, config_level=cfg)
    for scene in ("圆桌", "阶梯", "报告厅"):
        for (role, model, qty, unit, mic) in _MIC_INIT:
            _upsert(session, scene, 0, 9999, role, model, qty, unit, mic=mic)
        for (role, model, qty, unit, mic, ant) in _ANT_INIT:
            session.query(SelectionRule).filter(
                SelectionRule.scene == scene,
                SelectionRule.config_level == "中配",
                SelectionRule.device_role == role,
                (SelectionRule.mic_level.is_(None)) | (SelectionRule.antenna_level == "1,2"),
            ).delete(synchronize_session=False)
            _upsert(session, scene, 0, 9999, role, model, qty, unit, mic=mic, ant=ant)
    # 清理历史版本：仅当 (scene, config, role) 在新种子中已分档（多个面积区间）时，
    # 删除该组合面积 0-9999 的旧规则，避免与分档规则并存导致重复选型。
    from collections import Counter
    key_count = Counter((s, c, r) for (s, a1, a2, c, r, m, q, u) in _BASE_INIT)
    for (scene, cfg, role), cnt in key_count.items():
        if cnt > 1:
            session.query(SelectionRule).filter(
                SelectionRule.scene == scene,
                SelectionRule.config_level == cfg,
                SelectionRule.device_role == role,
                SelectionRule.area_min == 0, SelectionRule.area_max == 9999,
            ).delete(synchronize_session=False)
    session.commit()
