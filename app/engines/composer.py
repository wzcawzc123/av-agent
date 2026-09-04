"""设备清单编排器：确定性引擎 + 品牌约束回填 + LLM 配件辅材增强。

这是通用化的核心：模板管结构（系统+角色+数量），产品库管货源（品牌×型号×价格），
LLM 只补充配件辅材与说明，不再自由臆造型号。
"""
import json

from app.catalog import backfill_role, brand_allowed, parse_brand_constraints
from app.engines.systems.engines import SYSTEM_BUILDERS
from app.engines.systems.scene import infer_systems
from app.llm.base import ChatMessage
from app.llm.prompts import ACCESSORY_PROMPT
from app.orchestrator.intent import extract_json

_ROLE_NAMES = {
    "prosound": "专业扩声", "speech": "会议发言", "display": "显示系统",
    "paperless": "无纸化会议", "control": "中控矩阵", "distributed": "分布式",
    "lighting": "灯光系统", "broadcast": "公共广播", "videoconf": "视频会议",
}


def _row_to_device(row: dict, filled: dict | None) -> dict:
    name = (filled or {}).get("name") or row.get("role_name") or row.get("role", "")
    spec = row.get("spec") or ""
    note = row.get("note") or ""
    if filled is None:
        note = (note + "；" if note else "") + "待选型（产品库无匹配型号）"
    return {
        "category": "主设备",
        "system": row.get("system", ""),
        "system_name": _ROLE_NAMES.get(row.get("system", ""), ""),
        "type": row.get("role_name") or row.get("role", ""),
        "spec": spec,
        "brand": (filled or {}).get("brand", ""),
        "model": (filled or {}).get("model", ""),
        "qty": row.get("qty", 1),
        "unit": row.get("unit", "台"),
        "base_price": (filled or {}).get("base_price", 0),
        "market_price": (filled or {}).get("market_price", 0),
        "note": note,
    }


def build_rows_for_systems(slots: dict) -> list[dict]:
    """按需求系统集合生成角色行（确定性，不依赖产品库与 LLM）。"""
    systems = infer_systems(slots)
    rows: list[dict] = []
    for sys in systems:
        builder = SYSTEM_BUILDERS.get(sys)
        if builder:
            rows.extend(builder(slots))
    return rows


def backfill(rows: list[dict], session, brand_c: dict) -> list[dict]:
    """逐角色按 品牌约束 × 系统 × 角色 回填产品型号与价格。

    品牌约束下无对应产品时仍回填通用型号，并在 note 标注品牌回退，避免静默偷换品牌。
    """
    devices = []
    for row in rows:
        system = row.get("system", "")
        allowed = brand_allowed(brand_c, system)
        filled = backfill_role(session, system, row.get("role", ""), allowed)
        dev = _row_to_device(row, filled)
        if allowed and filled and filled.get("brand") not in allowed:
            tip = "（库内无指定品牌对应产品，暂以通用型号占位）"
            dev["note"] = (dev.get("note") or "").rstrip("；;，, ") + tip
        devices.append(dev)
    return devices


async def llm_accessories(provider, slots: dict, main_devices: list[dict]) -> list[dict]:
    """LLM 生成配件辅材（线缆/接头/支架/机柜等），失败时返回空列表不阻塞主流程。"""
    try:
        user_msg = (
            f"项目需求：{json.dumps(slots, ensure_ascii=False)}\n"
            f"主设备清单：{json.dumps(main_devices, ensure_ascii=False)}"
        )
        resp = await provider.chat([
            ChatMessage("system", ACCESSORY_PROMPT),
            ChatMessage("user", user_msg),
        ], temperature=0.2)
        data = extract_json(resp)
        acc = data.get("accessories") or []
        devices = []
        for a in acc:
            if not a.get("type") or not a.get("qty"):
                continue
            devices.append({
                "category": "配件辅材",
                "system": "",
                "system_name": "配件辅材",
                "type": a.get("type", ""),
                "spec": a.get("spec", ""),
                "brand": a.get("brand", ""),
                "model": a.get("model", ""),
                "qty": a.get("qty", 1),
                "unit": a.get("unit", "项"),
                "base_price": a.get("base_price", 0),
                "market_price": a.get("market_price", 0),
                "note": a.get("note", ""),
            })
        return devices
    except Exception:
        return []


async def compose_devices(provider, slots: dict, session, config_template=None) -> list[dict]:
    """完整设备清单：主设备（引擎+品牌回填）+ 配件辅材（LLM 增强）。

    provider 为 None 时仍返回主设备清单（无模型可用）。
    """
    brand_c = parse_brand_constraints(slots.get("brand"))
    rows = build_rows_for_systems(slots)
    devices = backfill(rows, session, brand_c)
    if provider is not None:
        devices += await llm_accessories(provider, slots, devices)
    return devices
