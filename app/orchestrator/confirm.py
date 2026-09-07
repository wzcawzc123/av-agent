DELIVERABLE_NAMES = {
    "doc": "文字方案(Word)",
    "deviation": "偏离表(Excel)",
    "excel": "设计方案清单(Excel)",
    "ppt": "PPT",
    "pdf": "PDF",
}

SYSTEM_NAMES = {
    "prosound": "专业扩声", "speech": "会议发言", "display": "显示系统",
    "paperless": "无纸化会议", "control": "中控矩阵", "distributed": "分布式",
    "lighting": "灯光系统", "broadcast": "公共广播", "videoconf": "视频会议",
}


def render_summary(slots: dict, deliverable_names: dict | None = None) -> str:
    names = deliverable_names or DELIVERABLE_NAMES
    lines = ["已确认以下需求，请确认后开始生成：", ""]
    lines.append(f"- 面积：{slots.get('area', '未提供')}")
    lines.append(f"- 场景：{slots.get('scene', '未提供')}")
    lines.append(f"- 预算：{slots.get('budget', '未提供')}")
    lines.append(f"- 品牌：{slots.get('brand', '未提供')}")
    sys_list = slots.get("systems") or []
    if sys_list:
        names_ = [SYSTEM_NAMES.get(s, s) for s in sys_list]
        lines.append(f"- 系统：{'、'.join(names_)}")
    room = slots.get("room") or {}
    if room:
        parts = [f"{k}{v}米" for k, v in room.items() if v]
        lines.append(f"- 房间：{' x '.join(parts)}")
    seats = slots.get("seats") or {}
    if seats:
        lines.append(f"- 席位：主席 {seats.get('chairman', 0)} + 代表 {seats.get('delegate', 0)}")
    if slots.get("signal_sources"):
        lines.append(f"- 信号源：{slots['signal_sources']} 路")
    disp = slots.get("display") or {}
    if disp:
        lines.append(f"- 显示要求：{disp}")
    for label, key in [("视频会议", "videoconf"), ("无纸化", "paperless"),
                       ("灯光", "lighting"), ("互动", "interact"),
                       ("分布式", "distributed")]:
        if slots.get(key):
            lines.append(f"- {label}：{slots[key]}")
    dels = [names.get(d, d) for d in slots.get("deliverables", [])]
    lines.append(f"- 交付物：{', '.join(dels) if dels else '未选择'}")
    return "\n".join(lines)
