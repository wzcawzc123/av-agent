"""需求完整性门控与场景化专家追问。

两段式追问：
1. 基础字段（面积/场景/预算/品牌/交付物）缺失 → 按固定顺序追问；
2. 基础字段齐备后，按场景匹配专家追问队列（每项只问一次），补足
   影响系统选型的关键参数（席位/层高/显示/视频会议/灯光…），
   避免基础字段齐全就立刻生成、产出千篇一律的清单。
"""

QUESTIONS = {
    "area": "项目面积大概多少平方米？这决定显示与扩声的规模。",
    "scene": "主要用途/场景是什么（会议室、报告厅、展厅、指挥中心…）？",
    "budget": "客户预算大概多少？",
    "brand": "有没有品牌偏好（如扩声用惠威、显示用 MAXHUB）？没有就说「无」。",
    "deliverables": "需要哪些交付物？文字方案(Word) / 偏离表(Excel) / 设计方案清单(Excel) / PPT / PDF 都可以选。",
}

_REQUIRED = ("area", "scene", "budget", "brand", "deliverables")

# 场景关键词 -> 专家追问队列（有序，问完一个再问下一个；每个字段仅追问一次）
SCENE_QUESTIONS = [
    (
        ("会议室", "圆桌", "阶梯", "培训"),
        [
            ("seats", "会议室大概容纳多少人？有没有主席位？"),
            ("display", "显示用什么？LED 屏 / 投影 / 会议一体机，大概多大？"),
            ("videoconf", "是否需要接入视频会议（远程参会）？"),
            ("paperless", "是否需要无纸化会议系统？"),
        ],
    ),
    (
        ("报告厅", "礼堂", "剧场", "多功能厅"),
        [
            ("seats", "报告厅大概有多少个座位？"),
            ("room.height", "层高大概多少米？（影响扩声配置与屏幕尺寸）"),
            ("lighting", "是否需要舞台灯光？"),
        ],
    ),
    (
        ("展厅", "展馆", "博物馆", "展台"),
        [
            ("display", "显示用 LED 还是拼接屏？大概尺寸（宽×高米）与点距要求？"),
            ("signal_sources", "需要接入多少路信号源（电脑/播放器/摄像头…）？"),
            ("interact", "是否需要互动功能（触摸/体感/播控）？"),
        ],
    ),
    (
        ("指挥中心", "监控", "调度"),
        [
            ("display", "显示用拼接屏吗？大概多少块 / 多大尺寸？"),
            ("distributed", "是否需要分布式坐席/异地调度（KVM）？"),
            ("seats", "工位大概多少个？"),
        ],
    ),
]

# 显式否定/占位词视为"已提供"（避免死循环追问）
_NEGATION = ("无", "没有", "不需要", "不用", "否", "false", "none")
_EXPLICIT_EMPTY = ("未提供", "未知", "null", "0")
# 这几个字段不允许用"无"糊弄过去（核心信息必须明确）
_STRICT_KEYS = ("area", "scene", "budget")


def _is_empty(key: str, val) -> bool:
    """判断槽位值是否为空；key 用于区分字段的"显式否定"语义。"""
    if val is None:
        return True
    if isinstance(val, str):
        s = val.strip().lower()
        if not s:
            return True
        if s in _EXPLICIT_EMPTY:
            return True
        if s in _NEGATION:
            # 品牌/交付物/专家开关字段的"无/不需要"视为已提供；
            # 面积/场景/预算必须给真实值。
            return key in _STRICT_KEYS
        return False
    if isinstance(val, (list, dict)):
        return len(val) == 0
    if isinstance(val, (int, float)):
        return val == 0
    return False


def _get_nested(slots: dict, path: str):
    """按点号路径取槽位值（如 room.height），缺失返回 None。"""
    cur = slots
    for part in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def next_question(slots: dict) -> str | None:
    """两段式追问：基础字段 → 场景专家字段。返回缺失项问题或 None（可确认）。"""
    return missing_required(slots) or _expert_question(slots)


def missing_required(slots: dict) -> str | None:
    """只检查基础字段（面积/场景/预算/品牌/交付物），供生成门控使用。

    专家字段属于"尽力补充"，不强制——用户跳过专家追问也能生成，
    只是清单参数可能不如补齐后准确。
    """
    for key in _REQUIRED:
        if _is_empty(key, slots.get(key)):
            return QUESTIONS[key]
    return None


def _expert_question(slots: dict) -> str | None:
    """基础字段齐备后，按场景匹配专家追问队列。"""
    scene = str(slots.get("scene") or "")
    for scene_keys, questions in SCENE_QUESTIONS:
        if any(k in scene for k in scene_keys):
            for key, question in questions:
                if _is_empty(key, _get_nested(slots, key)):
                    return question
            break
    return None
