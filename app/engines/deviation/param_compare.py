"""偏离表参数级比对：招标参数 vs 我方产品参数逐项数值比对。

复用 matcher.extract_specs 从文本抽参（功率/阻抗/尺寸/通道/点距），
逐项判断 正偏离 / 满足 / 负偏离；负偏离标注具体项+差值+应对建议。
"""

from __future__ import annotations

from app.catalog.matcher import extract_specs


def compare_params(tender_param: str, bid_param: str) -> dict:
    """返回 {"diff": str, "state": "positive|satisfy|negative", "suggestion": str}。

    无参数可比时返回空 dict（调用方保持原样）。
    """
    t_specs = extract_specs(tender_param or "")
    b_specs = extract_specs(bid_param or "")
    if not t_specs:
        return {}
    findings: list[str] = []
    negative_items: list[str] = []
    for key, tv in t_specs.items():
        bv = b_specs.get(key)
        if bv is None:
            continue
        if key == "pitch_mm":
            # 点距：值越小越清晰，招标要求 P2.5 → 我方 P2 为正偏离
            label = f"点距 P{tv:g}"
            if bv <= tv * 1.05:
                findings.append(f"点距 P{bv:g} ≤ 需求 P{tv:g}（更清晰，正偏离）")
            else:
                findings.append(f"点距 P{bv:g} > 需求 P{tv:g}（清晰度不足）")
                negative_items.append(f"点距（需 P{tv:g}，仅 P{bv:g}）")
        else:
            name = {"power_w": "功率", "impedance": "阻抗", "size_inch": "尺寸",
                    "channels": "通道数"}.get(key, key)
            unit = {"power_w": "W", "impedance": "Ω", "size_inch": "寸",
                    "channels": "路"}.get(key, "")
            if bv >= tv:  # 数值越大越好（功率/尺寸/通道）
                findings.append(f"{name} {bv:g}{unit} ≥ 需求 {tv:g}{unit}（满足/正偏离）")
            elif bv >= tv * 0.9:
                findings.append(f"{name} {bv:g}{unit} 接近需求 {tv:g}{unit}（基本满足）")
            else:
                findings.append(f"{name} {bv:g}{unit} < 需求 {tv:g}{unit}（负偏离）")
                negative_items.append(f"{name}（需 {tv:g}{unit}，仅 {bv:g}{unit}）")
    if not findings:
        return {}
    state = "negative" if negative_items else "positive"
    suggestions = []
    if negative_items:
        suggestions.append("建议更换更高规格型号或提供技术说明")
    return {
        "diff": "；".join(findings),
        "state": state,
        "suggestion": "；".join(suggestions),
    }


def enhance_deviation_rows(rows: list[dict]) -> list[dict]:
    """对偏离表行增强：补参数级比对信息到 note。"""
    out = []
    for r in rows:
        row = dict(r)
        cmp = compare_params(str(r.get("tender_param") or ""), str(r.get("bid_param") or ""))
        if cmp:
            note = str(row.get("note") or "")
            if cmp["state"] == "negative":
                row["deviation"] = "负偏离"
                extra = f"【负偏离】{cmp['diff']}；{cmp['suggestion']}"
            else:
                extra = f"【参数比对】{cmp['diff']}"
            row["note"] = f"{note}；{extra}".strip("；")
        out.append(row)
    return out
