import json
import re

from app.llm.base import ChatMessage
from app.llm.prompts import INTENT_PROMPT


def extract_json(text: str) -> dict:
    if not text:
        raise ValueError("无 JSON 内容")
    text = text.strip()
    # 去掉 markdown 代码围栏
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    # 1) 先尝试整体解析
    try:
        return json.loads(text)
    except Exception:
        pass
    # 2) 找到最外层 {...}（从第一个 { 到最后一个 }）
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("无 JSON 内容")
    candidate = text[start:end + 1]
    cleaned = re.sub(r",\s*([}\]])", r"\1", candidate)  # 去除尾随逗号
    for s in (cleaned, candidate, candidate[:-1].rstrip(",;") + "}"):
        try:
            return json.loads(s)
        except Exception:
            continue
    raise ValueError(f"JSON 解析失败: {candidate[:200]}")


async def parse_intent(provider, user_text: str, known: dict | None = None,
                       context_docs: list[dict] | None = None,
                       memory_note: str | None = None) -> dict:
    ctx = f"【已确认信息】{known}\n" if known else ""
    if context_docs:
        refs = "\n".join(
            f"- {d['title']}：{(d.get('excerpt') or '')[:150]}" for d in context_docs[:3]
        )
        ctx = f"【参考文档】\n{refs}\n{ctx}"
    # 跨会话记忆独立注入（不占参考文档名额，不受 top-3 截断影响）
    if memory_note:
        ctx = f"【跨会话记忆】客户偏好与既定事实：\n{memory_note[:1200]}\n{ctx}"
    resp = await provider.chat(
        [
            ChatMessage("system", INTENT_PROMPT),
            ChatMessage("user", f"{ctx}用户最新输入：{user_text}"),
        ],
        temperature=0.2,
    )
    slots = extract_json(resp)
    for key in ("area", "scene", "budget", "brand", "systems", "room", "seats",
                "config_level", "display", "signal_sources", "videoconf",
                "paperless", "lighting", "interact", "distributed"):
        slots.setdefault(key, None)
    slots.setdefault("deliverables", [])
    slots.setdefault("missing", [])
    return slots
