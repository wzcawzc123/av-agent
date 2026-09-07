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
from app.db.models import ChatMessage, Project

router = APIRouter(prefix="/api", dependencies=[Depends(require_token)])
_sessions: dict[int, dict] = {}
_MAX_SESSIONS = 200  # 内存会话上限：超出淘汰最旧一半（槽位 DB 有兜底，可无损重建）


def _evict_sessions_if_needed():
    if len(_sessions) > _MAX_SESSIONS:
        for pid in list(_sessions.keys())[: _MAX_SESSIONS // 2]:
            _sessions.pop(pid, None)


class ChatIn(BaseModel):
    text: str
    project_id: int | None = None


def get_session_slots(project_id: int) -> dict:
    return _sessions.get(project_id, {}).get("slots", {})


def _save_messages(project_id: int, user_text: str, reply_text: str) -> None:
    """A10：对话消息历史逐条落库（user/assistant）；失败静默不影响主流程。"""
    try:
        with get_session() as s:
            s.add(ChatMessage(project_id=project_id, role="user",
                              content=(user_text or "")[:4000]))
            s.add(ChatMessage(project_id=project_id, role="assistant",
                              content=(reply_text or "")[:20000]))
    except Exception:
        pass


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
        _evict_sessions_if_needed()
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
        from fastapi.concurrency import run_in_threadpool

        result = await run_in_threadpool(run_engine, intent["engine"], intent["params"])
        reply = {
            "reply": engine_summary(intent["engine"], result),
            "project_id": pid,
            "status": st.status,
            "engine": intent["engine"],
            "files": [result["file"]],
        }
        _save_messages(pid, body.text, reply["reply"])
        return reply

    cfg = load_model_config()
    if not cfg.get("provider") or not cfg.get("api_key"):
        reply = {
            "reply": "尚未配置模型。请点击右上角 ⚙️ 选择提供商并填写 API Key 后重试。",
            "project_id": pid,
            "status": st.status,
            "need_config": True,
        }
        _save_messages(pid, body.text, reply["reply"])
        return reply
    provider = await _get_provider(cfg)
    try:
        # 知识库检索：注入相关文档片段辅助意图解析
        context_docs = []
        if body.text:
            try:
                from app.db.session import get_session
                from app.knowledge.retriever import retrieve
                with get_session() as _ks:
                    context_docs = retrieve(_ks, body.text, top_k=3)
            except Exception:
                pass
        # 全局长期记忆注入（data/MEMORY.md，跨会话客户偏好）
        try:
            from app.api.routes_agent import _memory_read

            memory_note = _memory_read(max_chars=1200)
            if memory_note and "暂无记忆" not in memory_note:
                context_docs = (context_docs or []) + [
                    {"title": "跨会话记忆", "excerpt": memory_note}
                ]
        except Exception:
            pass
        new_slots = await parse_intent(provider, body.text, known=slots,
                                       context_docs=context_docs or None)
    except Exception:
        reply = {
            "reply": "调用模型失败，请检查 API Key 与网络后重试；也可以在工具箱中直接使用会议/广播/LED/偏离表引擎。",
            "project_id": pid,
            "status": st.status,
            "need_config": True,
            "engine_error": True,
        }
        _save_messages(pid, body.text, reply["reply"])
        return reply
    for k, v in new_slots.items():
        if k != "missing" and v not in (None, [], ""):
            slots[k] = v
    q = next_question(slots)
    if q is None:
        st.transition("CONFIRMING")
    _persist(pid, sess)
    if q is None:
        reply = {"reply": render_summary(slots), "project_id": pid, "status": st.status}
    else:
        reply = {"reply": q, "project_id": pid, "status": st.status}
    _save_messages(pid, body.text, reply["reply"])
    return reply
