import inspect
import json

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import require_token
from app.orchestrator.state_machine import ConversationState
from app.orchestrator.intent import parse_intent
from app.orchestrator.clarify import next_question
from app.orchestrator.confirm import render_summary
from app.llm.registry import get_provider, load_model_config
from app.db.session import get_session
from app.db.models import Project

router = APIRouter(prefix="/api", dependencies=[Depends(require_token)])
_sessions: dict[int, dict] = {}


class ChatIn(BaseModel):
    text: str
    project_id: int | None = None


def get_session_slots(project_id: int) -> dict:
    return _sessions.get(project_id, {}).get("slots", {})


def _load_or_create_session(pid: int) -> tuple[int, dict]:
    """从 DB 恢复或创建项目会话，返回 (真实 pid, session dict)。"""
    if pid in _sessions:
        return pid, _sessions[pid]
    with get_session() as s:
        p = s.query(Project).filter_by(id=pid).first() if pid else None
        if p is None:
            p = Project(name="音视频方案项目", requirement_json="{}", status="IDLE")
            s.add(p)
            s.flush()
            pid = p.id
        slots = {}
        try:
            slots = json.loads(p.requirement_json or "{}")
        except Exception:
            slots = {}
        valid = ("IDLE", "COLLECTING", "CONFIRMING", "GENERATING", "DELIVERED")
        st = ConversationState(p.status if p.status in valid else "IDLE")
        sess = {"state": st, "slots": slots}
        _sessions[pid] = sess
        return pid, sess


def _persist(pid: int, sess: dict):
    """把槽位与状态写回 DB，避免服务重启丢失。"""
    try:
        with get_session() as s:
            p = s.query(Project).filter_by(id=pid).first()
            if p:
                p.requirement_json = json.dumps(sess["slots"], ensure_ascii=False)
                p.status = sess["state"].status
    except Exception:
        pass

async def _get_provider(cfg):
    p = get_provider(cfg)
    if inspect.isawaitable(p):
        return await p
    return p


@router.post("/chat")
async def chat(body: ChatIn):
    pid = body.project_id or 0
    pid, sess = _load_or_create_session(pid)
    st, slots = sess["state"], sess["slots"]
    if st.status == "IDLE":
        st.transition("COLLECTING")

    # 引擎意图直通：命中会议/广播/LED/偏离表时无需模型配置，直接执行并返回
    from app.engines.intent.detect import detect_engine_intent, should_use_generic_flow
    from app.engines.intent.runner import engine_summary, run_engine

    intent = detect_engine_intent(body.text) if not should_use_generic_flow(body.text) else None
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
        new_slots = await parse_intent(provider, body.text, known=slots)
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
    q = next_question(slots)
    if q is None:
        st.transition("CONFIRMING")
    _persist(pid, sess)
    if q is None:
        return {"reply": render_summary(slots), "project_id": pid, "status": st.status}
    return {"reply": q, "project_id": pid, "status": st.status}
