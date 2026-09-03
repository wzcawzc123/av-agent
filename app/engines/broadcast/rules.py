from app.db.models import AmplifierTier, SpeakerSpec

# 喇叭功率表：真实产品库型号（额定功率 W）
_SPEAKERS = [
    ("MH-V5-PAS04C", 30, "4寸天花音箱"), ("PAS71C", 50, "DSP吸顶音箱"),
    ("MH-C6A", 60, "6寸吸顶音箱"), ("PAS71L", 60, "DSP音柱"),
    ("MH-V5-PAS05R", 80, "5寸有源监听"), ("MH-V5-PAS05", 120, "5寸同轴音箱"),
    ("MH-VS06", 120, "6.5寸专业音箱"), ("MH-C8A", 80, "8寸吸顶音箱"),
    ("MH-404L", 200, "4*4寸音柱"), ("MH-VS08", 200, "8寸专业音箱"),
    ("MH-VS10", 250, "10寸专业音箱"), ("MH-604L", 300, "6*4寸音柱"),
    ("MH-VS12", 350, "12寸专业音箱"), ("MH-804L", 400, "8*4寸音柱"),
]

# 产品名称映射（真实产品库名称，用于清单可读性）
_SPEAKER_NAMES = {
    "MH-V5-PAS04C": "4寸铁后桶天花音箱", "PAS71C": "网络音频DSP吸顶音箱",
    "MH-C6A": "6寸铁后桶吸顶音箱", "PAS71L": "网络音频DSP音柱",
    "MH-V5-PAS05R": "5寸有源监听音箱", "MH-V5-PAS05": "会议语音同轴音箱",
    "MH-VS06": "6.5寸多功能专业音箱", "MH-C8A": "8寸铁后桶吸顶音箱",
    "MH-404L": "4*4寸专业线性音柱", "MH-VS08": "8寸多功能专业音箱",
    "MH-VS10": "10寸多功能专业音箱", "MH-604L": "6*4寸专业线性音柱",
    "MH-VS12": "12寸多功能专业音箱", "MH-804L": "8*4寸专业线性音柱",
}

# 功放档位：真实产品库型号（按单通道功率分档）
_AMPLIFIERS = [
    (0, 150, "MH-L215"), (150, 250, "MH-L225"), (250, 400, "MH-L240"),
    (400, 600, "MH-V5-PA260"), (600, 1000, "MH-V5-PA2100"), (1000, 9999, "MH-V5-PA2130"),
]


def _sync(session, model_cls, rows, key_field, fields):
    """同步式种子：按 key_field 升级或插入；不在新表内的旧记录（如 itc T-*）删除。"""
    by_key = {r[key_field]: r for r in rows}
    session.flush()  # 先落库新行，避免与删除/升级混淆
    for old in session.query(model_cls).all():
        k = getattr(old, key_field)
        if k not in by_key:
            session.delete(old)
        else:
            for f in fields:
                setattr(old, f, by_key[k][f])
    existing = {getattr(o, key_field) for o in session.query(model_cls).all()}
    for r in rows:
        if r[key_field] not in existing:
            session.add(model_cls(**r))
    session.commit()


def seed_speaker_specs(session):
    """同步写入喇叭功率规格（型号取自真实产品库；旧 itc 型号自动清理）。"""
    _sync(session, SpeakerSpec,
          [{"model": m, "power_w": w, "category": c} for m, w, c in _SPEAKERS],
          "model", ["power_w", "category"])


def seed_amplifier_tiers(session):
    """同步写入功放功率档位（区域总功率×1.5 后匹配；旧 itc 型号自动清理）。"""
    _sync(session, AmplifierTier,
          [{"min_w": mn, "max_w": mx, "model": m} for mn, mx, m in _AMPLIFIERS],
          "min_w", ["max_w", "model"])
