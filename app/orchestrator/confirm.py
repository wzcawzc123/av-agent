DELIVERABLE_NAMES = {
    "doc": "文字方案(Word)",
    "deviation": "偏离表(Excel)",
    "ppt": "PPT",
    "pdf": "PDF",
}


def render_summary(slots: dict, deliverable_names: dict | None = None) -> str:
    names = deliverable_names or DELIVERABLE_NAMES
    lines = ["已确认以下需求，请确认后开始生成：", ""]
    lines.append(f"- 面积：{slots.get('area', '未提供')}")
    lines.append(f"- 场景：{slots.get('scene', '未提供')}")
    lines.append(f"- 预算：{slots.get('budget', '未提供')}")
    lines.append(f"- 品牌：{slots.get('brand', '未提供')}")
    dels = [names.get(d, d) for d in slots.get("deliverables", [])]
    lines.append(f"- 交付物：{', '.join(dels) if dels else '未选择'}")
    return "\n".join(lines)
