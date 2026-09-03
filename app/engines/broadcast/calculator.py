def compute_zone_power(zone, specs):
    """分区功率 = Σ(喇叭数量 × 单只功率)；未知型号按 0 处理。"""
    return sum(qty * specs.get(model, 0) for model, qty in zone.items())


def select_amplifier(power_w, tiers):
    """按 min_w < power_w <= max_w 匹配功放档位；无匹配返回空串。"""
    for t in sorted(tiers, key=lambda x: x.max_w):
        if t.min_w < power_w <= t.max_w:
            return t.model
    return ""
