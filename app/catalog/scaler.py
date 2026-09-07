"""配置模板面积缩放规则应用。

模板采集时 LLM 提取 scale_rules（如"音箱数量=面积/50 只，取整"）。
推理时按目标面积 vs 模板面积差应用：有显式规则的按规则计算，无规则的按面积比例线性缩放。
"""

from __future__ import annotations

import json
import re


def _load_rules(raw) -> list[dict]:
    if isinstance(raw, list):
        return [r for r in raw if isinstance(r, dict)]
    try:
        data = json.loads(raw or "[]")
        return [r for r in data if isinstance(r, dict)]
    except Exception:
        return []


def _parse_qty_rule(rule_text: str) -> float | None:
    """解析 '数量=面积/N' 或 '数量=面积/N,取整' → N。"""
    m = re.search(r"数量\s*=\s*面积\s*/\s*(\d+(?:\.\d+)?)", rule_text or "")
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return None
    return None


def apply_scale_rules(rows: list[dict], scale_rules, tpl_area: float, target_area: float) -> list[dict]:
    """按面积差缩放模板 BOM 行数量；返回新列表（不修改入参）。"""
    if not rows or target_area <= 0:
        return rows
    rules = _load_rules(scale_rules)
    tpl_area = float(tpl_area or target_area)
    ratio = target_area / tpl_area
    out = []
    for r in rows:
        row = dict(r)
        rule = None
        for cand in rules:
            key = str(cand.get("role") or cand.get("type") or "")
            if key and (key in str(row.get("type") or "") or key in str(row.get("role") or "")):
                rule = cand
                break
        if rule:
            per = _parse_qty_rule(str(rule.get("rule") or ""))
            if per:
                row["qty"] = max(1, round(target_area / per))
                note = str(row.get("note") or "")
                tip = f"按面积 {target_area:.0f}㎡ 缩放"
                row["note"] = f"{note}；{tip}".strip("；")
        elif not row.get("nonlinear"):
            old_qty = float(row.get("qty") or 1)
            new_qty = max(1, round(old_qty * ratio))
            if new_qty != old_qty:
                row["qty"] = new_qty
        out.append(row)
    return out
