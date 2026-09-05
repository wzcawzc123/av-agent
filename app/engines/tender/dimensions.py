"""参数维度提取与距离度量。

设计：维度表用「正则条目 + 单位 + 可选上下文关键词」描述，新增维度只需追加条目，
不修改匹配逻辑（品牌无关、维度可扩展）。
"""
import re
from dataclasses import dataclass, field

_NUM = r"(\d+(?:\.\d+)?)"

# 维度条目：(dim, 正则, 单位, 上下文关键词列表或 None, 类型 numeric|range|pair)
# 上下文关键词用于区分同单位不同维度（如 灵敏度 dB vs 信噪比 dB）。
# range 类型统一转为 Hz 存储（单位仅用于换算）。
DIM_ENTRIES: list[tuple[str, str, str, list[str] | None, str]] = [
    ("power", rf"{_NUM}\s*W(?!\d)", "W", None, "numeric"),
    ("impedance", rf"{_NUM}\s*(?:Ω|欧姆?|ohm)(?![\w])", "Ω", None, "numeric"),
    ("freq", rf"{_NUM}\s*Hz\s*(?:[-~—～至])\s*({_NUM})\s*Hz", "Hz", None, "range"),
    ("freq", rf"{_NUM}\s*kHz\s*(?:[-~—～至])\s*({_NUM})\s*kHz", "kHz", None, "range"),
    ("freq", rf"{_NUM}\s*Hz\s*(?:[-~—～至])\s*({_NUM})\s*kHz", "Hz-kHz", None, "range"),
    ("freq", rf"{_NUM}\s*(?:[-~—～至])\s*({_NUM})\s*Hz", "Hz", None, "range"),
    ("freq", rf"{_NUM}\s*(?:[-~—～至])\s*({_NUM})\s*kHz", "kHz", None, "range"),
    ("sens", rf"{_NUM}\s*dB", "dB", ["灵敏度", "sensitivity", "sens"], "numeric"),
    ("ratio", rf"{_NUM}\s*dB", "dB", ["信噪比", "snr", "s/n"], "numeric"),
    ("size", rf"{_NUM}\s*(?:英寸|吋|寸)(?![0-9A-Za-z])", "inch", None, "numeric"),
    ("channels", rf"(\d+)\s*(?:通道|声道|路(?:输出|输入)?)(?![0-9A-Za-z])", "ch", None, "numeric"),
    ("channels", rf"(\d+)\s*ch(?![0-9A-Za-z])", "ch", None, "numeric"),
    ("resolution", rf"(\d{{3,4}})\s*[x×*]\s*(\d{{3,4}})", "px", None, "pair"),
]

_EPS = 1e-6

# 维度权重（匹配距离加权；无共同维度时返回 None 由上层降级）
DIM_WEIGHTS: dict[str, float] = {
    "power": 1.0,
    "impedance": 0.8,
    "channels": 1.2,
    "size": 0.8,
    "freq": 0.7,
    "sens": 0.6,
    "ratio": 0.5,
    "resolution": 0.7,
}


@dataclass
class DimValue:
    """一个参数维度提取值。"""

    value: float
    unit: str
    raw: str


@dataclass
class DimMap:
    """提取结果：dim -> DimValue。"""

    values: dict[str, DimValue] = field(default_factory=dict)

    def get(self, dim: str):
        return self.values.get(dim)

    def dims(self) -> set[str]:
        return set(self.values.keys())

    def __bool__(self):
        return bool(self.values)


def extract_dims(text: str) -> DimMap:
    """从参数文本提取维度。同维度多个值取第一个非零；freq 统一转为 Hz。"""
    out: dict[str, DimValue] = {}
    if not text:
        return DimMap(out)
    lower = text.lower()
    for dim, pattern, unit, ctx, kind in DIM_ENTRIES:
        if dim in out:
            continue  # 已提取（freq range 优先）
        if ctx and not any(c in lower for c in ctx):
            continue
        m = re.search(pattern, text, re.IGNORECASE)
        if not m:
            continue
        if kind == "range":
            lo = float(m.group(1))
            hi = float(m.group(2))
            if unit == "kHz":
                lo, hi = lo * 1000.0, hi * 1000.0
            elif unit == "Hz-kHz":
                hi *= 1000.0
            if lo > hi:
                lo, hi = hi, lo
            out[dim] = DimValue(lo, "Hz", m.group(0))
            out[f"{dim}_hi"] = DimValue(hi, "Hz", m.group(0))
        elif kind == "pair":
            out[dim] = DimValue(float(m.group(1)), "px", m.group(0))
            out[f"{dim}_hi"] = DimValue(float(m.group(2)), "px", m.group(0))
        else:
            val = float(m.group(1))
            if val > 0:
                out[dim] = DimValue(val, unit, m.group(0))
    return DimMap(out)


def _norm_dist(a: float, b: float) -> float:
    return abs(a - b) / max(abs(a), abs(b), _EPS)


def _range_dist(lo1: float, hi1: float, lo2: float, hi2: float) -> float:
    """频响范围距离：归一化的端点差之和。"""
    span = max(hi1, hi2) - min(lo1, lo2)
    if span <= _EPS:
        return 0.0
    return (abs(lo1 - lo2) + abs(hi1 - hi2)) / span


def dim_distance(dim: str, a: DimValue, b: DimValue) -> float:
    """单个维度距离（0=完全一致，越大差异越大）。"""
    if dim.endswith("_hi") or dim in ("freq", "resolution"):
        return _norm_dist(a.value, b.value)
    return _norm_dist(a.value, b.value)


def match_distance(tender: DimMap, prod: DimMap) -> tuple[float | None, set[str], set[str]]:
    """加权距离：返回 (距离, 共同维度, 招标有而产品无的维度缺口)。None 表示无共同维度。"""
    common = tender.dims() & prod.dims()
    if not common:
        return None, set(), tender.dims() - prod.dims()
    gaps = tender.dims() - prod.dims()
    wsum = 0.0
    acc = 0.0
    for dim in common:
        w = DIM_WEIGHTS.get(dim.rstrip("_hi"), 1.0)
        acc += dim_distance(dim, tender.get(dim), prod.get(dim)) * w
        wsum += w
    return (acc / wsum, common, gaps)
