from app.db.models import SelectionRule

# (scene, config_level, device_role, model, qty, unit, mic_level, antenna_level)
# 话筒段：0=无 1=无线手持 2=无线会议 3=数字会议；天线段：0=无 1=分配器+吸顶天线
_BASE_INIT = [
    ("圆桌", "高配", "主音箱", "MH-VS10", 4, "只", None, None),
    ("圆桌", "高配", "功放", "MH-L440", 1, "台", None, None),
    ("圆桌", "高配", "处理器", "MH-MA1616", 1, "台", None, None),
    ("圆桌", "高配", "调音台", "MH-V5-MIX1812", 1, "台", None, None),
    ("圆桌", "高配", "显示", "EG86MZ", 1, "台", None, None),
    ("圆桌", "中配", "主音箱", "MH-VS08", 2, "只", None, None),
    ("圆桌", "中配", "功放", "MH-L240", 1, "台", None, None),
    ("圆桌", "中配", "处理器", "MH-MA0808", 1, "台", None, None),
    ("圆桌", "中配", "调音台", "MH-V5-MIX1004", 1, "台", None, None),
    ("圆桌", "中配", "显示", "EG65MZ", 1, "台", None, None),
    ("圆桌", "低配", "主音箱", "MH-VS08", 2, "只", None, None),
    ("圆桌", "低配", "功放", "MH-L215", 1, "台", None, None),
    ("圆桌", "低配", "处理器", "MH-MA0808", 1, "台", None, None),
    ("圆桌", "低配", "调音台", "MH-V5-MIX0802", 1, "台", None, None),
    ("圆桌", "低配", "显示", "EG65MZ", 1, "台", None, None),

    ("阶梯", "高配", "主音箱", "MH-VS12", 4, "只", None, None),
    ("阶梯", "高配", "功放", "MH-L440", 1, "台", None, None),
    ("阶梯", "高配", "处理器", "MH-MA1616", 1, "台", None, None),
    ("阶梯", "高配", "调音台", "MH-V5-MIX1812", 1, "台", None, None),
    ("阶梯", "高配", "显示", "EG86MZ", 2, "台", None, None),
    ("阶梯", "中配", "主音箱", "MH-VS10", 4, "只", None, None),
    ("阶梯", "中配", "功放", "MH-L240", 1, "台", None, None),
    ("阶梯", "中配", "处理器", "MH-MA0808", 1, "台", None, None),
    ("阶梯", "中配", "调音台", "MH-V5-MIX1004", 1, "台", None, None),
    ("阶梯", "中配", "显示", "EG75MZ", 1, "台", None, None),
    ("阶梯", "低配", "主音箱", "MH-VS10", 2, "只", None, None),
    ("阶梯", "低配", "功放", "MH-L215", 1, "台", None, None),
    ("阶梯", "低配", "处理器", "MH-MA0808", 1, "台", None, None),
    ("阶梯", "低配", "调音台", "MH-V5-MIX1004", 1, "台", None, None),
    ("阶梯", "低配", "显示", "EG65MZ", 1, "台", None, None),
    ("报告厅", "高配", "主音箱", "MH-V5-PAS15", 4, "只", None, None),
    ("报告厅", "高配", "功放", "MH-V5-PA2100", 2, "台", None, None),
    ("报告厅", "高配", "处理器", "MH-MA1616", 1, "台", None, None),
    ("报告厅", "高配", "调音台", "MH-V5-MIX1812", 1, "台", None, None),
    ("报告厅", "高配", "显示", "EG86MZ", 2, "台", None, None),
    ("报告厅", "中配", "主音箱", "MH-VS12", 4, "只", None, None),
    ("报告厅", "中配", "功放", "MH-L440", 1, "台", None, None),
    ("报告厅", "中配", "处理器", "MH-MA1616", 1, "台", None, None),
    ("报告厅", "中配", "调音台", "MH-V5-MIX1812", 1, "台", None, None),
    ("报告厅", "中配", "显示", "EG86MZ", 2, "台", None, None),
    ("报告厅", "低配", "主音箱", "MH-VS12", 2, "只", None, None),
    ("报告厅", "低配", "功放", "MH-L240", 1, "台", None, None),
    ("报告厅", "低配", "处理器", "MH-MA0808", 1, "台", None, None),
    ("报告厅", "低配", "调音台", "MH-V5-MIX1004", 1, "台", None, None),
    ("报告厅", "低配", "显示", "EG75MZ", 1, "台", None, None),
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

# 天线段种子：天线仅配套无线话筒（段1手持/段2无线会议），逗号表示多段适用
_ANT_INIT = [
    ("天线分配器", "MH-BK895", 1, "台", "1,2", "1"),
    ("吸顶天线", "MH-QH10", 2, "只", "1,2", "1"),
]


def _upsert(session, scene, role, model, qty, unit, mic=None, ant=None,
            config_level="中配"):
    row = (session.query(SelectionRule)
           .filter_by(scene=scene, config_level=config_level, device_role=role,
                      mic_level=mic, antenna_level=ant).first())
    if row is None:
        # 旧库兼容：同键但 mic/ant 为 NULL 的旧行就地升级
        row = (session.query(SelectionRule)
               .filter_by(scene=scene, config_level=config_level, device_role=role,
                          mic_level=None, antenna_level=None).first())
        if row:
            row.mic_level, row.antenna_level = mic, ant
    if row:
        row.model, row.qty, row.unit = model, qty, unit
    else:
        session.add(SelectionRule(scene=scene, config_level=config_level,
                                  device_role=role, model=model, qty=qty,
                                  unit=unit, mic_level=mic, antenna_level=ant))


def seed_selection_rules(session):
    """幂等写入/升级选型规则种子：基础三档配置 + 话筒段 + 天线段。"""
    for (scene, cfg, role, model, qty, unit, _m, _a) in _BASE_INIT:
        _upsert(session, scene, role, model, qty, unit, _m, _a, config_level=cfg)
    for scene in ("圆桌", "阶梯", "报告厅"):
        for (role, model, qty, unit, mic) in _MIC_INIT:
            _upsert(session, scene, role, model, qty, unit, mic=mic)
        for (role, model, qty, unit, mic, ant) in _ANT_INIT:
            # 清理历史版本残留的天线规则（mic 约束缺失或错误格式），再写入新格式
            session.query(SelectionRule).filter(
                SelectionRule.scene == scene,
                SelectionRule.config_level == "中配",
                SelectionRule.device_role == role,
                (SelectionRule.mic_level.is_(None)) | (SelectionRule.antenna_level == "1,2"),
            ).delete(synchronize_session=False)
            _upsert(session, scene, role, model, qty, unit, mic=mic, ant=ant)
    session.commit()
