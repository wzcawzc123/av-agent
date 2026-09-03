"""可选 LLM 语义增强：对 medium/low 匹配做二次判断；无 key/异常自动降级为原结果。"""
import asyncio
import json
import re

from app.llm.base import ChatMessage
from app.llm.prompts import DEV_ENHANCE_PROMPT


async def _judge_with_provider(tender: str, matched_param: str) -> tuple[str, str]:
    """真实通道：读取已配置的模型，判断式提示词，解析置信度 JSON。"""
    from app.llm.registry import get_provider, load_model_config

    cfg = load_model_config()
    provider = await get_provider(cfg)
    prompt = DEV_ENHANCE_PROMPT.format(tender=tender, param=matched_param)
    raw = await provider.chat([ChatMessage(role="user", content=prompt)], temperature=0)
    text = raw.strip().strip("`")
    if text.startswith("json"):
        text = text[4:].strip()
    m = re.search(r"\{.*\}", text, re.S)
    data = json.loads(m.group(0)) if m else {}
    conf = str(data.get("confidence", "medium")).strip().lower()
    return (conf if conf in ("high", "medium", "low") else "medium", str(data.get("note", "")))


def _llm_judge(tender: str, matched_param: str):
    """同步包装：无配置/调用失败时抛异常，由上层降级。"""
    return asyncio.run(_judge_with_provider(tender, matched_param))


def enhance_with_llm(results, tender_items, llm_enabled=True, session=None):
    if not llm_enabled:
        return results
    try:
        out = []
        for i, r in enumerate(results):
            if r.confidence in ("medium", "low") and r.matched_param:
                conf, _ = _llm_judge(tender_items[i], r.matched_param)
                if conf in ("high", "medium", "low"):
                    r.confidence = conf
            out.append(r)
        return out
    except Exception:
        return results  # 任何异常降级为原结果
