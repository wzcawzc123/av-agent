import inspect

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import require_token
from app.orchestrator.state_machine import ConversationState
from app.orchestrator.intent import parse_intent
from app.orchestrator.clarify import next_question
from app.orchestrator.confirm import render_summary
from app.llm.registry import get_provider, load_model_config

router = APIRouter(prefix="/api", dependencies=[Depends(require_token)])
_sessions: dict[int, dict] = {}


class ChatIn(BaseModel):
    text: str
    project_id: int | None = None


def get_session_slots(project_id: int) -> dict:
    return _sessions.get(project_id, {}).get("slots", {})


async def _get_provider(cfg):
    p = get_provider(cfg)
    if inspect.isawaitable(p):
        return await p
    return p


@router.post("/chat")
async def chat(body: ChatIn):
    pid = body.project_id or 0
    sess = _sessions.setdefault(pid, {"state": ConversationState(), "slots": {}})
    st, slots = sess["state"], sess["slots"]
    if st.status == "IDLE":
        st.transition("COLLECTING")

    # 引擎意图直通：命中会议/广播/LED/偏离表时无需模型配置，直接执行并返回
    from app.engines.intent.detect import detect_engine_intent
    from app.engines.intent.runner import engine_summary, run_engine

    intent = detect_engine_intent(body.text)
    if intent:
        result = run_engine(intent["engine"], intent["params"])
        return {
            "reply": engine_summary(intent["engine"], result),
            "project_id": pid,
            "status": st.status,
            "engine": intent["engine"],
            "files": [result["file"]],
        }

    cfg = load_model_config()
    if not cfg.get("provider") or not cfg.get("api_key"):
        return {
            "reply": "尚未配置模型。请点击右上角 ⚙️ 选择提供商并填写 API Key 后重试。",
            "project_id": pid,
            "status": st.status,
            "need_config": True,
        }
    provider = await _get_provider(cfg)
    try:
        new_slots = await parse_intent(provider, body.text)
    except Exception:
        return {
            "reply": "调用模型失败，请检查 API Key 与网络后重试；也可以在工具箱中直接使用会议/广播/LED/偏离表引擎。",
            "project_id": pid,
            "status": st.status,
            "need_config": True,
            "engine_error": True,
        }
    for k, v in new_slots.items():
        if k != "missing" and v not in (None, [], ""):
            slots[k] = v
    q = next_question(new_slots)
    if q is None and not new_slots.get("missing"):
        st.transition("CONFIRMING")
        return {"reply": render_summary(slots), "project_id": pid, "status": st.status}
    return {"reply": q, "project_id": pid, "status": st.status}
