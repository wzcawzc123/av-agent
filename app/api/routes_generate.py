import json
import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from app.api.deps import require_token
from app.api.routes_chat import get_session_slots
from app.tasks.queue import submit_task, get_task, subscribe

router = APIRouter(prefix="/api", dependencies=[Depends(require_token)])


class GenerateIn(BaseModel):
    project_id: int


@router.post("/generate")
def generate(body: GenerateIn):
    from app.config import settings

    slots = get_session_slots(body.project_id)
    project_dir = f"{settings.OUTPUT_DIR}/proj_{body.project_id}"
    cfg = {
        "deliverables": slots.get("deliverables", ["doc"]),
        "project_dir": project_dir,
        "template_paths": {},
    }
    task_id = submit_task(body.project_id, cfg, slots)
    return {"task_id": task_id}


@router.get("/tasks/{task_id}")
def task_status(task_id: str):
    t = get_task(task_id)
    if not t:
        return {"error": "任务不存在"}
    return {"id": t.id, "status": t.status, "progress": t.progress,
            "message": t.message, "result": t.result}


@router.get("/tasks/{task_id}/stream")
async def task_stream(task_id: str):
    t = get_task(task_id)
    if not t:
        return {"error": "任务不存在"}

    async def gen():
        async for event in subscribe(t.project_id):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.get("/download")
def download(path: str):
    from app.config import settings

    real = os.path.realpath(path)
    out_dir = os.path.realpath(settings.OUTPUT_DIR)
    if not real.startswith(out_dir + os.sep) or not os.path.isfile(real):
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(real, filename=os.path.basename(real))


# ---- 方案工具引擎端点 ----

class EngineDeviationIn(BaseModel):
    tender_items: list[str]
    models: list[str] = []
    llm_enabled: bool = False


class EngineMeetingIn(BaseModel):
    code: str = ""
    length_m: float = 0
    width_m: float = 0
    height_m: float = 0
    scene: str = "圆桌"  # 圆桌/阶梯/报告厅
    config: str = "中配"  # 高配/中配/低配
    mic: str = "0"       # 0无 1无线手持 2无线会议 3数字会议
    antenna: str = "0"   # 0无 1天线
    header: dict = {}


class EngineBroadcastIn(BaseModel):
    zones: list[dict]
    header: dict = {}


class EngineLedIn(BaseModel):
    want_w_m: float
    want_h_m: float
    model: str
    round_mode: str = "就近"
    header: dict = {}


@router.post("/engines/deviation")
def engine_deviation(body: EngineDeviationIn):
    from app.config import settings
    from app.db.session import get_engine, get_session
    from app.engines.deviation.db_bridge import build_candidates_from_db
    from app.engines.deviation.llm_enhance import enhance_with_llm
    from app.engines.deviation.matcher import match_tender_to_product
    from app.generators.excel_generator import build_deviation_sheet

    with get_session(get_engine()) as s:
        cands = build_candidates_from_db(s, body.models)
    results = match_tender_to_product(body.tender_items, cands)
    results = enhance_with_llm(results, body.tender_items, llm_enabled=body.llm_enabled)
    os.makedirs(f"{settings.OUTPUT_DIR}/engines", exist_ok=True)
    out = f"{settings.OUTPUT_DIR}/engines/deviation.xlsx"
    rows = [{"device": r.model, "tender_param": t, "bid_param": r.matched_param,
             "deviation": "" if r.confidence != "low" else "待人工确认",
             "note": r.confidence}
            for t, r in zip(body.tender_items, results)]
    build_deviation_sheet(out, {}, rows)
    low = sum(1 for r in results if r.confidence == "low")
    return {"file": out, "results": [vars(r) for r in results], "low_confidence": low}




_SCENE_TO_NUM = {"圆桌": "1", "阶梯": "2", "报告厅": "3"}
_CONFIG_TO_NUM = {"高配": "1", "中配": "2", "低配": "3"}


def _build_meeting_code(b: "EngineMeetingIn") -> str:
    """结构化参数 → itc 编码：长-宽-高-0-0-类型-配置-0-话筒-天线-"""
    return (f"{b.length_m or 0:.0f}-{b.width_m or 0:.0f}-{b.height_m or 0:.0f}-"
            f"0-0-{_SCENE_TO_NUM.get(b.scene, '1')}-{_CONFIG_TO_NUM.get(b.config, '2')}-"
            f"0-{b.mic or '0'}-{b.antenna or '0'}-")

@router.post("/engines/meeting")
def engine_meeting(body: EngineMeetingIn):
    from app.config import settings
    from app.db.session import get_engine, get_session
    from app.engines.meeting.codec import parse_code
    from app.engines.meeting.rules import seed_selection_rules
    from app.engines.meeting.selector import select_devices
    from app.generators.excel_generator import build_meeting_list

    os.makedirs(f"{settings.OUTPUT_DIR}/engines", exist_ok=True)
    code = body.code.strip() if body.code and body.code.strip() else _build_meeting_code(body)
    with get_session(get_engine()) as s:
        seed_selection_rules(s)
        rows = select_devices(s, parse_code(code))
    out = f"{settings.OUTPUT_DIR}/engines/meeting.xlsx"
    build_meeting_list(out, body.header, rows)
    return {"file": out, "rows": rows, "code": code}


@router.post("/engines/broadcast")
def engine_broadcast(body: EngineBroadcastIn):
    from app.config import settings
    from app.db.models import AmplifierTier, SpeakerSpec
    from app.db.session import get_engine, get_session
    from app.engines.broadcast.calculator import compute_zone_power, select_amplifier
    from app.engines.broadcast.rules import seed_amplifier_tiers, seed_speaker_specs
    from app.generators.excel_generator import build_broadcast_list

    os.makedirs(f"{settings.OUTPUT_DIR}/engines", exist_ok=True)
    with get_session(get_engine()) as s:
        seed_speaker_specs(s)
        seed_amplifier_tiers(s)
        specs = {sp.model: sp.power_w for sp in s.query(SpeakerSpec).all()}
        tiers = s.query(AmplifierTier).all()
    zones_with_power = []
    for z in body.zones:
        z = dict(z)
        zone_speakers = {k: v for k, v in z.items() if k not in ("zone", "power_w", "amplifier")}
        power = compute_zone_power(zone_speakers, specs) * 1.5  # 1.5 倍余量
        z["power_w"] = round(power, 2)
        z["amplifier"] = select_amplifier(power, tiers)
        zones_with_power.append(z)
    rows = [{"name": model, "model": model, "qty": qty, "unit": "只"}
            for z in body.zones for model, qty in z.items()
            if model not in ("zone", "power_w", "amplifier")]
    out = f"{settings.OUTPUT_DIR}/engines/broadcast.xlsx"
    build_broadcast_list(out, body.header, zones_with_power, rows)
    return {"file": out, "zones_with_power": zones_with_power, "rows": rows}


@router.post("/engines/led")
def engine_led(body: EngineLedIn):
    from fastapi import HTTPException

    from app.config import settings
    from app.db.models import LedPanelSpec
    from app.db.session import get_engine, get_session
    from app.engines.led.layout import calc_layout
    from app.engines.led.rules import seed_led_specs
    from app.generators.excel_generator import build_led_list

    os.makedirs(f"{settings.OUTPUT_DIR}/engines", exist_ok=True)
    with get_session(get_engine()) as s:
        seed_led_specs(s)
        panel = s.query(LedPanelSpec).filter_by(model=body.model).first()
    if not panel:
        raise HTTPException(status_code=404, detail=f"屏体规格不存在: {body.model}")
    layout = calc_layout(body.want_w_m, body.want_h_m, panel, body.round_mode)
    rows = [{"name": f"{body.model}模组", "model": body.model,
             "qty": layout["count_w"] * layout["count_h"], "unit": "块"}]
    out = f"{settings.OUTPUT_DIR}/engines/led.xlsx"
    build_led_list(out, body.header, layout, rows)
    return {"file": out, "layout": layout, "rows": rows}
