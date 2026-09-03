import math

_POWER_PER_M2_DEFAULT = 300  # W/m²


def _count(want_mm: float, module_mm: float, mode: str) -> int:
    if mode == "向上":
        return math.ceil(want_mm / module_mm)
    if mode == "向下":
        return math.floor(want_mm / module_mm)
    return round(want_mm / module_mm)


def calc_layout(want_w_m, want_h_m, panel, round_mode="就近", power_per_m2=None):
    """意向尺寸 → 模组排布 → 实际尺寸/分辨率/功耗/电缆线径。"""
    power_per_m2 = power_per_m2 or _POWER_PER_M2_DEFAULT
    cw = _count(want_w_m * 1000, panel.module_w_mm, round_mode)
    ch = _count(want_h_m * 1000, panel.module_h_mm, round_mode)
    aw = cw * panel.module_w_mm / 1000
    ah = ch * panel.module_h_mm / 1000
    res_w = cw * panel.res_w
    res_h = ch * panel.res_h
    power_kw = aw * ah * power_per_m2 * 1.3 / 1000
    cable_mm2 = math.ceil(power_kw * 1000 / 38)
    return {
        "count_w": cw, "count_h": ch,
        "actual_w_m": aw, "actual_h_m": ah,
        "res_w": res_w, "res_h": res_h,
        "total_pixels_wan": res_w * res_h / 10000,
        "power_kw": round(power_kw, 2),
        "cable_mm2": cable_mm2,
    }
