"""LLM 精修层：对规则匹配的 partial 行二次判断、冗余(extra)冗余检测。

无模型配置 / 调用失败时自动降级为规则结果，不阻塞主流程。
"""
from __future__ import annotations

import asyncio
import json
import re

from app.engines.tender.model import TenderMatchRow
from app.llm.base import ChatMessage
from app.llm.prompts import TENDER_REFINE_PROMPT


def _rows_payload(rows: list[TenderMatchRow]) -> list[dict]:
    return [
        {
            "idx": r.source_idx,
            "name": r.name,
            "brand": r.brand,
            "model": r.model,
            "qty": r.qty,
            "status": r.status,
            "matched_model": r.matched_model,
            "score": round(r.score, 4),
            "remark": r.remark,
        }
        for r in rows
    ]


async def _refine_with_provider(payload: list[dict]) -> dict:
    from app.llm.registry import get_provider, load_model_config

    cfg = load_model_config()
    provider = await get_provider(cfg)
    prompt = TENDER_REFINE_PROMPT + "\n招标匹配行：\n" + json.dumps(payload, ensure_ascii=False)
    raw = await provider.chat([ChatMessage(role="user", content=prompt)], temperature=0)
    text = raw.strip().strip("`")
    if text.startswith("json"):
        text = text[4:].strip()
    m = re.search(r"\{.*\}", text, re.S)
    return json.loads(m.group(0)) if m else {}


def _call_llm(payload: list[dict]) -> dict:
    """同步包装；失败抛异常由上层降级。"""
    return asyncio.run(_refine_with_provider(payload))


def refine_rows(rows: list[TenderMatchRow], llm_enabled: bool = True) -> list[TenderMatchRow]:
    """对 partial 行做二次判断：keep 确认 / replace 换型 / new 转新增。"""
    partials = [r for r in rows if r.status == "partial"]
    if not llm_enabled or not partials:
        return rows
    try:
        data = _call_llm(_rows_payload(rows))
        decisions = {int(p["idx"]): p for p in data.get("partials", []) if isinstance(p, dict)}
        for r in rows:
            d = decisions.get(r.source_idx)
            if not d:
                continue
            decision = str(d.get("decision", "")).strip().lower()
            note = str(d.get("note", "")).strip()
            if decision == "keep":
                r.status = "matched"
                r.remark = (r.remark + "；" if r.remark else "") + ("LLM 确认可用" + (f"：{note}" if note else ""))
            elif decision == "new":
                r.status = "new"
                r.remark = (r.remark + "；" if r.remark else "") + ("LLM 建议新增设备" + (f"：{note}" if note else ""))
            elif decision == "replace" and d.get("model"):
                r.remark = (r.remark + "；" if r.remark else "") + f"LLM 建议换型 {d.get('model')}" + (f"：{note}" if note else "")
    except Exception:
        pass  # 降级为规则结果
    return rows


def flag_extras(rows: list[TenderMatchRow], llm_enabled: bool = True) -> list[TenderMatchRow]:
    """标记冗余(extra)行：功能已被本项目其他设备覆盖。"""
    if not llm_enabled or len(rows) < 2:
        return rows
    try:
        data = _call_llm(_rows_payload(rows))
        extras = {int(i) for i in data.get("extras", []) if isinstance(i, (int, float))}
        for r in rows:
            if r.source_idx in extras and r.status not in ("merged", "new"):
                r.status = "extra"
                r.remark = (r.remark + "；" if r.remark else "") + "LLM 判定为冗余项，可剔除"
    except Exception:
        pass
    return rows