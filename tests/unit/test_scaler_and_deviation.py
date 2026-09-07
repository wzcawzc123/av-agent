"""缩放规则 + 偏离参数级比对测试。"""


from app.catalog.scaler import apply_scale_rules, _parse_qty_rule
from app.engines.deviation.param_compare import compare_params, enhance_deviation_rows


# ---------- 缩放规则 ----------

def test_parse_qty_rule():
    assert _parse_qty_rule("数量=面积/50，取整") == 50.0
    assert _parse_qty_rule("按每20㎡一只") is None


def test_apply_explicit_rule():
    rows = [{"type": "专业音箱", "qty": 2, "unit": "只"}]
    rules = [{"role": "专业音箱", "rule": "数量=面积/50，取整"}]
    out = apply_scale_rules(rows, rules, tpl_area=100, target_area=600)
    assert out[0]["qty"] == 12  # 600/50
    assert "缩放" in out[0]["note"]


def test_apply_linear_without_rule():
    rows = [{"type": "功放", "qty": 2, "unit": "台"},
            {"type": "调音台", "qty": 1, "unit": "台", "nonlinear": True}]
    out = apply_scale_rules(rows, [], tpl_area=100, target_area=300)
    assert out[0]["qty"] == 6   # 2 × 3
    assert out[1]["qty"] == 1   # nonlinear 不缩放


def test_apply_same_area_no_change():
    rows = [{"type": "音箱", "qty": 4}]
    out = apply_scale_rules(rows, [], tpl_area=100, target_area=100)
    assert out[0]["qty"] == 4


# ---------- 偏离参数级比对 ----------

def test_compare_negative_with_suggestion():
    r = compare_params("专业功放 600W 8Ω", "2*400W数字功放 8Ω")
    assert r["state"] == "negative"
    assert "功率" in r["diff"] and "600" in r["diff"] and "400" in r["diff"]
    assert "更换更高规格" in r["suggestion"]


def test_compare_positive():
    r = compare_params("P2.5 LED屏", "P1.9")
    assert r["state"] == "positive"
    assert "更清晰" in r["diff"]


def test_compare_no_params_returns_empty():
    assert compare_params("专业音箱", "") == {}


def test_enhance_rows_marks_negative():
    rows = [{"device": "功放", "tender_param": "600W", "bid_param": "400W",
             "deviation": "", "note": "high"}]
    out = enhance_deviation_rows(rows)
    assert out[0]["deviation"] == "负偏离"
    assert "【负偏离】" in out[0]["note"]
    assert "应对" in out[0]["note"] or "建议" in out[0]["note"]
