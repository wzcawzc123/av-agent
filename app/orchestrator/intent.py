import json
import re

from app.llm.base import ChatMessage
from app.llm.prompts import INTENT_PROMPT


def extract_json(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("无 JSON 内容")
    return json.loads(m.group(0))


async def parse_intent(provider, user_text: str) -> dict:
    resp = await provider.chat(
        [
            ChatMessage("system", INTENT_PROMPT),
            ChatMessage("user", user_text),
        ],
        temperature=0.2,
    )
    slots = extract_json(resp)
    slots.setdefault("area", None)
    slots.setdefault("scene", None)
    slots.setdefault("budget", None)
    slots.setdefault("brand", None)
    slots.setdefault("deliverables", [])
    slots.setdefault("missing", [])
    return slots
