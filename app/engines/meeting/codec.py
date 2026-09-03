from dataclasses import dataclass, field

SCENE_MAP = {"1": "圆桌", "2": "阶梯", "3": "报告厅"}
CONFIG_MAP = {"1": "高配", "2": "中配", "3": "低配"}


@dataclass
class MeetingParams:
    scene: str = "圆桌"
    length_m: float = 0
    width_m: float = 0
    height_m: float = 0
    stage_w: float = 0
    stage_d: float = 0
    config: str = "中配"
    extra: dict = field(default_factory=dict)

    @property
    def area(self) -> float:
        return self.length_m * self.width_m


def _seg(parts, i, default="0"):
    return parts[i] if i < len(parts) and parts[i] else default


def parse_code(code: str) -> MeetingParams:
    """itc 编码：0长 1宽 2高 3舞台宽 4舞台深 5类型 6音响配置 7特殊 8话筒 9天线；段缺失取 0。"""
    parts = code.split("-")
    p = MeetingParams(
        scene=SCENE_MAP.get(_seg(parts, 5), "圆桌"),
        length_m=float(_seg(parts, 0) or 0),
        width_m=float(_seg(parts, 1) or 0),
        height_m=float(_seg(parts, 2) or 0),
        stage_w=float(_seg(parts, 3) or 0),
        stage_d=float(_seg(parts, 4) or 0),
        config=CONFIG_MAP.get(_seg(parts, 6), "中配"),
    )
    p.extra = {"音响配置": _seg(parts, 6), "特殊音响配置": _seg(parts, 7),
               "话筒配置": _seg(parts, 8), "天线": _seg(parts, 9)}
    return p
