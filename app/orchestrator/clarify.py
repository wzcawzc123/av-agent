QUESTIONS = {
    "area": "项目面积大概多少平方米？",
    "scene": "主要用途/场景是什么（会议室、展厅、报告厅…）？",
    "budget": "客户预算大概多少？",
    "brand": "有没有品牌偏好？",
    "deliverables": "需要哪些交付物？文字方案 / 偏离表 / 设计方案清单Excel表 / PPT 都可以选。",
}

_REQUIRED = ("area", "scene", "budget", "brand", "deliverables")


def next_question(slots: dict) -> str | None:
    """基于累积槽位判断缺口；slots 即为已合并的会话槽位。"""
    missing = set(slots.get("missing", []))
    for key in _REQUIRED:
        if key in missing:
            return QUESTIONS[key]
    return None
