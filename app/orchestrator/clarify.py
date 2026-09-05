QUESTIONS = {
    "area": "项目面积大概多少平方米？",
    "scene": "主要用途/场景是什么（会议室、展厅、报告厅…）？",
    "budget": "客户预算大概多少？",
    "brand": "有没有品牌偏好？",
    "deliverables": "需要哪些交付物？文字方案 / 偏离表 / 设计方案清单Excel表 / PPT 都可以选。",
}

_REQUIRED = ("area", "scene", "budget", "brand", "deliverables")


def _is_empty(val) -> bool:
    """判断槽位值是否为空/未提供/无意义，用于需求完整性门控。"""
    if val is None:
        return True
    if isinstance(val, str):
        s = val.strip()
        return not s or s in ("未提供", "无", "未知", "null", "none", "0")
    if isinstance(val, (list, dict)):
        return len(val) == 0
    if isinstance(val, (int, float)):
        return val == 0
    return False


def next_question(slots: dict) -> str | None:
    """基于槽位实际值判断缺口，不再依赖 LLM 返回的 missing 数组。

    缺任何一个关键字段（面积/场景/预算/品牌/交付物）就回问客户，
    避免在需求不明确时进入生成、浪费 token 且产出缺字段的清单。
    """
    for key in _REQUIRED:
        if _is_empty(slots.get(key)):
            return QUESTIONS[key]
    return None
