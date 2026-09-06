"""引擎执行 runner：chat 与 /api/engines/* 端点共用，输出到 OUTPUT_DIR/engines/。"""
import os
import uuid

from app.config import settings
from app.db.session import get_engine, get_session


def _out_dir() -> str:
    d = f"{settings.OUTPUT_DIR}/engines"
    os.makedirs(d, exist_ok=True)
    return d



def run_meeting(params: dict) -> dict:
    from app.engines.meeting.codec import parse_code
    from app.engines.meeting.rules import seed_selection_rules
    from app.engines.meeting.selector import select_devices
    from app.generators.excel_generator import build_meeting_list

    out = f"{_out_dir()}/meeting_{uuid.uuid4().hex[:8]}.xlsx"
    with get_session(get_engine()) as s:
        seed_selection_rules(s)
        rows = select_devices(s, parse_code(params.get("code", "")))
    build_meeting_list(out, params.get("header") or {}, rows)
    return {"file": out, "rows": rows}


def run_broadcast(params: dict) -> dict:
    from app.db.models import AmplifierTier, SpeakerSpec
    from app.engines.broadcast.calculator import compute_zone_power, select_amplifier
    from app.engines.broadcast.rules import seed_amplifier_tiers, seed_speaker_specs
    from app.generators.excel_generator import build_broadcast_list

    out = f"{_out_dir()}/broadcast_{uuid.uuid4().hex[:8]}.xlsx"
    with get_session(get_engine()) as s:
        seed_speaker_specs(s)
        seed_amplifier_tiers(s)
        specs = {sp.model: sp.power_w for sp in s.query(SpeakerSpec).all()}
        tiers = s.query(AmplifierTier).all()
    zones_with_power = []
    for z in params.get("zones", []):
        z = dict(z)
        speaker_zone = {k: v for k, v in z.items() if k not in ("zone", "power_w", "amplifier")}
        power = compute_zone_power(speaker_zone, specs) * 1.5
        z["power_w"] = round(power, 2)
        z["amplifier"] = select_amplifier(power, tiers)
        zones_with_power.append(z)
    rows = [{"name": model, "model": model, "qty": qty, "unit": "只"}
            for z in params.get("zones", []) for model, qty in z.items()
            if model not in ("zone", "power_w", "amplifier")]
    build_broadcast_list(out, params.get("header") or {}, zones_with_power, rows)
    return {"file": out, "zones_with_power": zones_with_power, "rows": rows}


def run_led(params: dict) -> dict:
    from fastapi import HTTPException

    from app.db.models import LedPanelSpec
    from app.engines.led.layout import calc_layout
    from app.engines.led.rules import seed_led_specs
    from app.generators.excel_generator import build_led_list

    out = f"{_out_dir()}/led_{uuid.uuid4().hex[:8]}.xlsx"
    with get_session(get_engine()) as s:
        seed_led_specs(s)
        panel = s.query(LedPanelSpec).filter_by(model=params.get("model", "")).first()
    if not panel:
        raise HTTPException(status_code=404, detail=f"屏体规格不存在: {params.get('model')}")
    layout = calc_layout(params["want_w_m"], params["want_h_m"], panel,
                         params.get("round_mode", "就近"))
    rows = [{"name": f"{params.get('model')}模组", "model": params.get("model"),
             "qty": layout["count_w"] * layout["count_h"], "unit": "块"}]
    build_led_list(out, params.get("header") or {}, layout, rows)
    return {"file": out, "layout": layout, "rows": rows}


def run_deviation(params: dict) -> dict:
    from app.engines.deviation.db_bridge import build_candidates_from_db
    from app.engines.deviation.llm_enhance import enhance_with_llm
    from app.engines.deviation.matcher import match_tender_to_product
    from app.generators.excel_generator import build_deviation_sheet

    out = f"{_out_dir()}/deviation_{uuid.uuid4().hex[:8]}.xlsx"
    with get_session(get_engine()) as s:
        cands = build_candidates_from_db(s, params.get("models", []))
    results = match_tender_to_product(params.get("tender_items", []), cands)
    results = enhance_with_llm(results, params.get("tender_items", []),
                               llm_enabled=params.get("llm_enabled", False))
    rows = [{"device": r.model, "tender_param": t, "bid_param": r.matched_param,
             "deviation": "" if r.confidence != "low" else "待人工确认", "note": r.confidence}
            for t, r in zip(params.get("tender_items", []), results)]
    build_deviation_sheet(out, params.get("header") or {}, rows)
    low = sum(1 for r in results if r.confidence == "low")
    return {"file": out, "results": [vars(r) for r in results], "low_confidence": low}


def _summary_meeting(result: dict) -> str:
    lines = [f"{r['seq']}. {r['name']} {r['model']} ×{r['qty']}{r['unit']}"
             for r in result["rows"]]
    return "会议设备清单（Excel 已生成）：\n" + "\n".join(lines)


def _summary_broadcast(result: dict) -> str:
    lines = [f"{z['zone']}：{z['power_w']}W → 功放 {z['amplifier']}"
             for z in result["zones_with_power"]]
    return "广播分区计算（×1.5 余量）：\n" + "\n".join(lines)


def _summary_led(result: dict) -> str:
    l = result["layout"]
    return (f"LED 排布：{l['count_w']}×{l['count_h']} 块 → 实际 "
            f"{l['actual_w_m']}m × {l['actual_h_m']}m，分辨率 {l['res_w']}×{l['res_h']}，"
            f"功耗 {l['power_kw']}kW，电缆 {l['cable_mm2']}mm²")


def _summary_deviation(result: dict) -> str:
    low = result.get("low_confidence", 0)
    return (f"偏离表已生成：{len(result['results'])} 条，低置信度 {low} 条"
            + ("（已标「待人工确认」）" if low else ""))


from app.engines import register_engine  # noqa: E402

register_engine("meeting", run_meeting, _summary_meeting)
register_engine("broadcast", run_broadcast, _summary_broadcast)
register_engine("led", run_led, _summary_led)
register_engine("deviation", run_deviation, _summary_deviation)


def run_engine(engine: str, params: dict) -> dict:
    from app.engines import get_runner

    fn = get_runner(engine)
    if not fn:
        raise ValueError(f"未知引擎: {engine}")
    return fn(params)


def engine_summary(engine: str, result: dict) -> str:
    """执行结果 → 对话回复摘要。"""
    from app.engines import get_summarizer

    fn = get_summarizer(engine)
    return fn(result) if fn else "已生成"
