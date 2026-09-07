"""Agent 模式工具循环端点：模型可自主多轮调用工具完成需求（ETA-2 Agent Loop 的轻量移植）。

协议化工具调用：模型需要调用工具时输出一行 JSON（{"tool":..., "args":{...}}），
后端执行并把结果回填上下文，直到模型给出最终回复；轮次上限防失控。
"""

from __future__ import annotations

import json
import os
import time
from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.api.deps import require_token
from app.config import settings
from app.db.session import get_session
from app.db.models import ChatMessage, Project, Product
from app.llm.base import ChatMessage as LLMMessage
from app.llm.prompts import AGENT_TOOL_PROMPT
from app.llm.registry import load_model_config, get_provider

router = APIRouter(prefix="/api", dependencies=[Depends(require_token)])

MAX_TOOL_ROUNDS = 6
MEMORY_FILE = os.path.join(settings.DATA_DIR, "MEMORY.md")


class AgentChatIn(BaseModel):
    text: str
    project_id: Optional[int] = None


# ---------- 记忆 ----------

def _memory_read(max_chars: int = 3000) -> str:
    try:
        if os.path.exists(MEMORY_FILE):
            with open(MEMORY_FILE, encoding="utf-8") as f:
                content = f.read().strip()
            if content:
                return content[:max_chars]
    except Exception:
        pass
    return "（暂无记忆）"


def _memory_write(content: str) -> str:
    try:
        os.makedirs(settings.DATA_DIR, exist_ok=True)
        entry = content.strip()[:2000]
        if not entry:
            return "内容为空，未写入"
        with open(MEMORY_FILE, "a", encoding="utf-8") as f:
            f.write(f"- {entry}\n")
        return "已写入记忆"
    except Exception as e:
        return f"记忆写入失败：{e}"


# ---------- 工具 ----------

def _tool_products(q: str = "", brand: str = "") -> str:
    """智能匹配优先：自然语言查询（如'300W 功放 8Ω'）走 rapidfuzz 匹配，带分数；否则 LIKE 兜底。"""
    if q:
        try:
            from app.catalog.matcher import match_products

            with get_session() as s:
                matches = match_products(s, q, limit=5)
            if matches:
                lines = []
                for m in matches:
                    p = m["product"]
                    lines.append(
                        f"- {p['name']} | 型号 {p['model']} | {p['brand']} | 市场价 {p['market_price']}"
                        f"（匹配 {m['score']:.0f} 分：{m['reason']}）"
                    )
                return "\n".join(lines)
        except Exception:
            pass  # 匹配失败退回 LIKE
    from sqlalchemy import or_

    with get_session() as s:
        query = s.query(Product)
        if q:
            like = f"%{q}%"
            query = query.filter(or_(Product.name.like(like), Product.model.like(like),
                                     Product.brand.like(like)))
        if brand:
            query = query.filter(Product.brand == brand)
        rows = query.order_by(Product.id.desc()).limit(10).all()
        if not rows:
            return "产品库无匹配（可上传产品 Excel 后重试）"
        lines = [
            f"- {prod.name} | 型号 {prod.model} | {prod.brand} | {prod.category} | 市场价 {prod.market_price}"
            for prod in rows
        ]
        return "\n".join(lines)


def _tool_projects() -> str:
    with get_session() as s:
        rows = s.query(Project).order_by(Project.id.desc()).limit(20).all()
        if not rows:
            return "暂无项目"
        return "\n".join(f"- ID {proj.id} | {proj.name} | 状态 {proj.status}" for proj in rows)


def _tool_project_files(project_id: int) -> str:
    project_dir = os.path.join(settings.OUTPUT_DIR, f"proj_{project_id}")
    if not os.path.isdir(project_dir):
        return f"项目 {project_id} 暂无产出文件"
    files = sorted(os.listdir(project_dir))
    return "\n".join(f"- {f}" for f in files) if files else f"项目 {project_id} 暂无产出文件"


def _tool_generate(project_id: int) -> str:
    """需求完整则提交生成任务并等待完成（最长约 3 分钟）。"""
    from app.orchestrator.clarify import missing_required
    from app.tasks.queue import submit_task, get_task

    with get_session() as s:
        p = s.get(Project, project_id)
        if p is None:
            return f"项目 {project_id} 不存在"
        slots = json.loads(p.requirement_json or "{}")
    missing = missing_required(slots)
    if missing:
        return f"需求不完整：{missing}，请先向客户确认后再生成"
    deliverables = slots.get("deliverables") or ["doc", "excel"]
    if not isinstance(deliverables, list) or not deliverables:
        deliverables = ["doc", "excel"]
    cfg = {
        "deliverables": [d for d in deliverables if d] or ["doc", "excel"],
        "project_dir": os.path.join(settings.OUTPUT_DIR, f"proj_{project_id}"),
        "template_paths": {},
        "project_id": project_id,
    }
    task_id = submit_task(project_id, cfg, slots)
    deadline = time.time() + 180
    while time.time() < deadline:
        t = get_task(task_id)
        if t is None:
            return "任务丢失，请重试"
        if t.status == "success":
            result = t.result or {}
            files = result.get("files") or {}
            lines = ["生成完成："]
            for kind, path in files.items():
                lines.append(f"- {kind}: {os.path.basename(path)}")
            errors = result.get("errors") or {}
            for kind, msg in errors.items():
                lines.append(f"- {kind} 失败：{msg}")
            return "\n".join(lines)
        if t.status == "failed":
            return f"生成失败：{t.message or '未知错误'}"
        time.sleep(1)
    return "生成仍在进行中（超过 3 分钟），可稍后查看项目产出文件"


def _run_tool(name: str, args: dict) -> str:
    try:
        if name == "av_products":
            return _tool_products(str(args.get("q") or ""), str(args.get("brand") or ""))
        if name == "av_projects":
            return _tool_projects()
        if name == "av_project_files":
            return _tool_project_files(int(args.get("project_id") or 0))
        if name == "av_generate":
            return _tool_generate(int(args.get("project_id") or 0))
        if name == "memory_read":
            return _memory_read()
        if name == "memory_write":
            return _memory_write(str(args.get("content") or ""))
        return f"未知工具：{name}"
    except Exception as e:  # noqa: BLE001
        return f"工具执行失败：{e}"


async def _run_ingest_tool(provider, args: dict) -> str:
    """av_ingest：LLM 智能入库（异步，需复用循环里的 provider）。"""
    path = str(args.get("path") or "").strip()
    target = str(args.get("target") or "auto").strip() or "auto"
    if not path:
        return "请提供本地文件绝对路径（path）。"
    if not os.path.isfile(path):
        return f"文件不存在：{path}（桌面端请提供本机绝对路径）"
    try:
        from app.api.routes_ingest import _ingest

        res = await _ingest(provider, os.path.abspath(path), os.path.basename(path), target)
        if res.get("ok"):
            msg = res.get("message", "入库完成")
            if res.get("title"):
                msg += f"\n识别标题：{res['title']}"
            return msg
        return f"入库失败：{res.get('message')}"
    except Exception as e:  # noqa: BLE001
        return f"入库失败：{e}"


def _parse_tool_call(text: str) -> dict | None:
    """尝试把模型回复解析为工具调用；失败返回 None（视为最终回复）。"""
    stripped = text.strip()
    if not stripped.startswith("{"):
        return None
    try:
        data = json.loads(stripped)
    except Exception:
        return None
    if isinstance(data, dict) and isinstance(data.get("tool"), str) and data["tool"]:
        return data
    return None


def _try_parse_json(text: str) -> dict | None:
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _load_history(project_id: int, limit: int = 16) -> list[LLMMessage]:
    with get_session() as s:
        rows = (
            s.query(ChatMessage)
            .filter_by(project_id=project_id)
            .order_by(ChatMessage.id.desc())
            .limit(limit)
            .all()
        )
    return [LLMMessage(r.role, r.content) for r in reversed(rows)]


def _save_messages(project_id: int, user_text: str, reply_text: str) -> None:
    try:
        with get_session() as s:
            s.add(ChatMessage(project_id=project_id, role="user", content=(user_text or "")[:4000]))
            s.add(ChatMessage(project_id=project_id, role="assistant",
                              content=(reply_text or "")[:20000]))
    except Exception:
        pass


async def _get_provider():
    p = get_provider(load_model_config())
    if hasattr(p, "__await__"):
        return await p
    return p


async def run_agent_loop(provider, system_prompt: str, history: list[LLMMessage],
                         user_text: str, max_rounds: int = MAX_TOOL_ROUNDS) -> tuple[str, list[LLMMessage]]:
    """工具循环：模型可多轮调用工具，返回 (最终回复, 完整消息列表)。"""
    messages: list[LLMMessage] = [LLMMessage("system", system_prompt)]
    messages.extend(history)
    messages.append(LLMMessage("user", user_text))
    for _round in range(max_rounds):
        try:
            resp = await provider.chat(messages, temperature=0.3)
        except Exception as e:  # noqa: BLE001
            return (f"调用模型失败：{e}。请检查「模型提供商」页的 API Key 与网络后重试。", messages)
        call = _parse_tool_call(resp)
        if call is None:
            return resp, messages
        tool_name = call["tool"]
        tool_args = call.get("args") or {}
        messages.append(LLMMessage("assistant", json.dumps(call, ensure_ascii=False)))
        if tool_name == "av_ingest":
            result = await _run_ingest_tool(provider, tool_args)
        else:
            result = _run_tool(tool_name, tool_args)
        messages.append(LLMMessage("user", f"【工具结果 {tool_name}】\n{result}"))
    fallback = ("我已完成多轮工具调用，但需求仍不够清晰。请补充：项目面积、场景、预算、品牌偏好、需要的交付物。")
    return fallback, messages


async def run_agent_loop_stream(provider, system_prompt: str, history: list[LLMMessage],
                                user_text: str, max_rounds: int = MAX_TOOL_ROUNDS):
    """流式工具循环：最终回复逐段 yield token 事件；工具调用不流式。

    事件：{"type":"token","text":...} / {"type":"tool","name":...,"result":...}
          / {"type":"done","reply":...}
    """
    messages: list[LLMMessage] = [LLMMessage("system", system_prompt)]
    messages.extend(history)
    messages.append(LLMMessage("user", user_text))
    for _round in range(max_rounds):
        buf = ""
        decided: Optional[str] = None  # "reply" | "tool"
        try:
            async for delta in provider.chat_stream(messages, temperature=0.3):
                buf += delta
                if decided is None:
                    stripped = buf.lstrip()
                    if stripped.startswith("{"):
                        parsed = _try_parse_json(stripped)
                        if parsed is not None and isinstance(parsed.get("tool"), str) and parsed["tool"]:
                            decided = "tool"
                        elif len(stripped) > 4096:
                            decided = "reply"
                            yield {"type": "token", "text": buf}
                    else:
                        decided = "reply"
                        yield {"type": "token", "text": buf}
                else:
                    yield {"type": "token", "text": delta}
        except Exception as e:  # noqa: BLE001
            yield {"type": "done", "reply": f"调用模型失败：{e}。请检查「模型提供商」页的 API Key 与网络后重试。"}
            return
        if decided == "tool":
            call = _parse_tool_call(buf)
            if call is None:
                # 解析失败：把缓冲当作回复收尾
                yield {"type": "done", "reply": buf}
                return
            tool_name = call["tool"]
            tool_args = call.get("args") or {}
            messages.append(LLMMessage("assistant", json.dumps(call, ensure_ascii=False)))
            if tool_name == "av_ingest":
                result = await _run_ingest_tool(provider, tool_args)
            else:
                result = _run_tool(tool_name, tool_args)
            messages.append(LLMMessage("user", f"【工具结果 {tool_name}】\n{result}"))
            yield {"type": "tool", "name": tool_name, "result": result[:400]}
            continue
        yield {"type": "done", "reply": buf}
        return
    fallback = ("我已完成多轮工具调用，但需求仍不够清晰。请补充：项目面积、场景、预算、品牌偏好、需要的交付物。")
    yield {"type": "done", "reply": fallback}


@router.post("/agent/chat")
async def agent_chat(body: AgentChatIn):
    cfg = load_model_config()
    if not cfg.get("provider") or not cfg.get("api_key"):
        return {"reply": "尚未配置模型。请先到「模型提供商」页选择提供商并填写 API Key。",
                "project_id": body.project_id or 0, "need_config": True}
    # 会话载体：项目
    with get_session() as s:
        p = None
        if body.project_id:
            p = s.get(Project, body.project_id)
        if p is None:
            p = Project(name="Agent 会话", requirement_json="{}", status="IDLE")
            s.add(p)
            s.flush()
            body.project_id = p.id

    provider = await _get_provider()
    memory = _memory_read()
    system_prompt = AGENT_TOOL_PROMPT + f"\n\n【跨会话记忆】\n{memory}"
    final_reply, _messages = await run_agent_loop(
        provider, system_prompt, _load_history(body.project_id), body.text,
    )
    _save_messages(body.project_id, body.text, final_reply)
    return {"reply": final_reply, "project_id": body.project_id}


@router.post("/agent/chat/stream")
async def agent_chat_stream(body: AgentChatIn):
    """Agent 模式流式对话：SSE token 流（工具调用不流式，最终回复逐段输出）。"""
    cfg = load_model_config()
    if not cfg.get("provider") or not cfg.get("api_key"):
        return {"reply": "尚未配置模型。请先到「模型提供商」页选择提供商并填写 API Key。",
                "project_id": body.project_id or 0, "need_config": True}
    with get_session() as s:
        p = None
        if body.project_id:
            p = s.get(Project, body.project_id)
        if p is None:
            p = Project(name="Agent 会话", requirement_json="{}", status="IDLE")
            s.add(p)
            s.flush()
            body.project_id = p.id
    provider = await _get_provider()
    memory = _memory_read()
    system_prompt = AGENT_TOOL_PROMPT + f"\n\n【跨会话记忆】\n{memory}"
    history = _load_history(body.project_id)

    async def gen():
        reply = ""
        async for event in run_agent_loop_stream(provider, system_prompt, history, body.text):
            if event.get("type") == "done":
                reply = event.get("reply", "")
                event = {**event, "project_id": body.project_id}
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        if reply:
            _save_messages(body.project_id, body.text, reply)

    return StreamingResponse(gen(), media_type="text/event-stream")
