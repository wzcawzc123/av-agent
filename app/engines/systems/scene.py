"""系统场景推断与公共计算。

scene -> systems 的默认映射；席位/信号源/显示端的面积推导规则。
所有引擎输出统一角色行：
{"system": code, "role": role_code, "role_name": 名称, "qty": n, "unit": "只",
 "spec": "", "note": ""}
"""
import math


_SYSTEM_ALIASES = {
    "matrix": "control", "中控": "control", "矩阵": "control",
    "扩声": "prosound", "音响": "prosound",
    "发言": "speech", "话筒": "speech",
    "显示": "display", "大屏": "display",
    "无纸化": "paperless",
    "分布式": "distributed",
    "灯光": "lighting",
    "广播": "broadcast",
    "视频会议": "videoconf", "远程会议": "videoconf",
}


def _norm_system(code: str) -> str:
    code = (code or "").strip().lower()
    if code in _SYSTEM_ALIASES:
        return _SYSTEM_ALIASES[code]
    # 中文名直接映射（如 "灯光系统" -> lighting）
    for name, c in _SYSTEM_ALIASES.items():
        if name in code:
            return c
    return code


def infer_systems(slots: dict) -> list[str]:
    """显式 systems 优先；否则按 scene 推断。返回去重后的 system code 列表。"""
    explicit = slots.get("systems")
    if isinstance(explicit, list) and explicit:
        return list(dict.fromkeys(_norm_system(s) for s in explicit))
    scene = str(slots.get("scene") or "")
    if "广播" in scene or "园区" in scene or "校园" in scene or "医院" in scene or "厂" in scene:
        return ["broadcast"]
    if "指挥" in scene or "监控" in scene:
        return ["display", "control", "distributed"]
    if "展厅" in scene or "展馆" in scene or "博物馆" in scene:
        return ["display", "distributed", "control", "prosound"]
    if "报告厅" in scene or "礼堂" in scene or "剧场" in scene:
        return ["prosound", "speech", "display", "lighting"]
    if "会议室" in scene or "圆桌" in scene or "阶梯" in scene or "培训" in scene:
        return ["prosound", "speech", "display", "paperless"]
    return ["prosound", "speech", "display"]


def resolve_seats(slots: dict) -> dict:
    """返回 {"chairman": int, "delegate": int}；未给席位时按面积推导。"""
    seats = slots.get("seats")
    if isinstance(seats, dict):
        chairman = int(seats.get("chairman") or 1)
        delegate = int(seats.get("delegate") or 0)
        if delegate > 0:
            return {"chairman": chairman, "delegate": delegate}
    area = float(slots.get("area") or 0)
    if area <= 0:
        return {"chairman": 1, "delegate": 6}
    if area <= 80:
        d = 6
    elif area <= 150:
        d = 10
    elif area <= 250:
        d = 16
    else:
        d = int(round(area / 15))
    return {"chairman": 1, "delegate": d}


def resolve_signal_sources(slots: dict) -> int:
    """信号源数量：显式给用显式，否则按面积/场景推导。"""
    n = slots.get("signal_sources")
    if n:
        return int(n)
    scene = str(slots.get("scene") or "")
    area = float(slots.get("area") or 0)
    if "报告厅" in scene or "指挥" in scene:
        return 8
    if area > 200:
        return 8
    return 4


def resolve_displays(slots: dict) -> int:
    """显示端数量：默认 1（主显示），报告厅/指挥中心 2。"""
    n = slots.get("display_count")
    if n:
        return int(n)
    scene = str(slots.get("scene") or "")
    return 2 if ("报告厅" in scene or "指挥" in scene) else 1


def seating_capacity(seats: dict) -> int:
    return int(seats.get("chairman") or 0) + int(seats.get("delegate") or 0)
