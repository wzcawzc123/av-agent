"""设备清单编排器：确定性引擎 + 配置模板基底 + 品牌约束回填 + LLM 配件辅材增强。

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

_MAIN_CATS = ("主设备", "主要设备")


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


def _same_role(a: str, b: str) -> bool:
    a, b = (a or "").strip(), (b or "").strip()
    if not a or not b:
        return False
    if a == b:
        return True
    return (len(a) >= 2 and len(b) >= 2) and (a in b or b in a)


def _tpl_rows(config_template) -> tuple[list[dict], list[dict]]:
    """取出配置模板 config_json 里的 BOM 行（兼容 rows / devices 键），拆成(主设备, 配件)。"""
    if config_template is None:
        return [], []
    try:
        cfg = json.loads(config_template.config_json or "{}")
    except (TypeError, ValueError):
        cfg = {}
    raw = cfg.get("rows")
    if not isinstance(raw, list):
        raw = cfg.get("devices") or []
    if not isinstance(raw, list):
        raw = []
    main, acc = [], []
    for r in raw:
        if not isinstance(r, dict):
            continue
        (main if r.get("category") in _MAIN_CATS else acc).append(r)
    return main, acc


def _tpl_row_to_device(r: dict, category: str = "主设备") -> dict:
    """模板 BOM 行 → 设备行（沿用模板已选定的品牌/型号/价格，不重复回填）。"""
    price = float(r.get("market_price") or r.get("base_price") or r.get("price") or 0)
    note = r.get("note") or ""
    if category == "主设备" and not (r.get("model") or r.get("brand")):
        note = (note + "；" if note else "") + "沿用模板配置（待选型）"
    system = r.get("system", "") if category == "主设备" else ""
    return {
        "category": category,
        "system": system,
        "system_name": _ROLE_NAMES.get(system, "") if category == "主设备" else "配件辅材",
        "type": r.get("type") or r.get("role_name") or "",
        "spec": r.get("spec", ""),
        "brand": r.get("brand", ""),
        "model": r.get("model", ""),
        "qty": int(float(r.get("qty") or 1)),
        "unit": r.get("unit") or ("台" if category == "主设备" else "项"),
        "base_price": price,
        "market_price": price,
        "note": note,
    }


def _covered_by_template(tpl_main: list[dict], row: dict) -> bool:
    """模板主设备行是否已覆盖该引擎角色行（同系统 + 角色名宽松相等）。"""
    sys_code = row.get("system", "")
    role_name = row.get("role_name") or row.get("role", "")
    for t in tpl_main:
        if sys_code and t.get("system") and t.get("system") != sys_code:
            continue
        if _same_role(t.get("type"), role_name):
            return True
    return False


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


def _compose_from_template(slots: dict, session, tpl_main: list[dict]) -> list[dict]:
    """模板主设备行作基底：需求系统缺角色用引擎生成后照常品牌回填。"""
    devices = [_tpl_row_to_device(r) for r in tpl_main]
    brand_c = parse_brand_constraints(slots.get("brand"))
    missing: list[dict] = []
    for sys in infer_systems(slots):
        builder = SYSTEM_BUILDERS.get(sys)
        if not builder:
            continue
        for row in builder(slots):
            if not _covered_by_template(tpl_main, row):
                missing.append(row)
    if missing:
        devices += backfill(missing, session, brand_c)
    return devices


async def compose_devices(provider, slots: dict, session, config_template=None) -> list[dict]:
    """完整设备清单：模板基底 / 引擎 + 品牌回填 + 配件辅材。

    - 传入 config_template 且其 rows 含主设备行：模板主设备为基底，缺失角色引擎补齐并
      品牌回填，配件沿用模板登记行，不再重复调 LLM（同类项目复用承诺成立）；
    - 无模板或模板无主设备行：引擎生成 + LLM 配件辅材增强。
    - provider 为 None 时仍返回主设备清单（无模型可用）。
    """
    tpl_main, tpl_acc = _tpl_rows(config_template)
    if tpl_main:
        devices = _compose_from_template(slots, session, tpl_main)
        devices += [_tpl_row_to_device(r, "配件辅材") for r in tpl_acc]
        return devices

    brand_c = parse_brand_constraints(slots.get("brand"))
    rows = build_rows_for_systems(slots)
    devices = backfill(rows, session, brand_c)
    if provider is not None:
        devices += await llm_accessories(provider, slots, devices)
    return devices
