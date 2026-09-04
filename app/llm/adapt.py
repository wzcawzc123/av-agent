import json

from app.llm.base import ChatMessage
from app.llm.prompts import ADAPT_PROMPT
from app.orchestrator.intent import extract_json


def _validate(result: dict) -> dict:
    devices = result.get("devices")
    if not isinstance(devices, list) or not devices:
        raise ValueError("适配结果缺少 devices")
    for d in devices:
        if not d.get("type") or d.get("qty") in (None, ""):
            raise ValueError(f"设备项缺字段: {d}")
        d.setdefault("category", "主设备")
        d.setdefault("spec", "")
        d.setdefault("brand", "")
        d.setdefault("model", "")
        d.setdefault("unit", "只" if d.get("category") == "配件辅材" else "台")
        d.setdefault("base_price", 0)
        d.setdefault("market_price", 0)
        d.setdefault("note", "")
        try:
            d["qty"] = int(float(d["qty"]))
        except (TypeError, ValueError):
            d["qty"] = 1
    # 主设备在前，配件辅材在后
    devices.sort(key=lambda x: 0 if x.get("category") == "主设备" else 1)
    result.setdefault("notes", "")
    return result


def _fill_prices(devices: list[dict], products: list[dict]) -> None:
    """价格缺失时尝试用产品库匹配（按 spec 关键词或 type 关键词）。"""
    if not products:
        return
    for d in devices:
        if d.get("base_price") and d.get("market_price"):
            continue
        spec = (d.get("spec") or "").strip()
        best = None
        for p in products:
            name = f"{p.get('name', '')} {p.get('model', '')}"
            if spec and spec in name or (not spec and d.get("type") in name):
                best = p
                break
        if best is None and spec:
            for p in products:
                if spec[:2] in f"{p.get('name', '')} {p.get('model', '')}":
                    best = p
                    break
        if best:
            d.setdefault("model", best.get("model", ""))
            d.setdefault("base_price", best.get("base_price", 0))
            d.setdefault("market_price", best.get("market_price", 0))


async def adapt_template(provider, slots: dict, config_template, products: list[dict], session) -> dict:
    tpl_json = json.dumps(
        json.loads(config_template.config_json) if config_template else {"devices": []},
        ensure_ascii=False,
    )
    product_summary = json.dumps(products[:50], ensure_ascii=False)
    user_msg = (
        f"项目需求：{json.dumps(slots, ensure_ascii=False)}\n"
        f"常规配置模板：{tpl_json}\n"
        f"产品库（名称/型号/底价/市场价）：{product_summary}"
    )
    resp = await provider.chat(
        [
            ChatMessage("system", ADAPT_PROMPT),
            ChatMessage("user", user_msg),
        ],
        temperature=0.2,
    )
    result = _validate(extract_json(resp))
    _fill_prices(result["devices"], products)
    return result
