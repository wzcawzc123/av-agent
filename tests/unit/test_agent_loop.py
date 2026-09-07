"""C3 Agent 工具循环测试：多轮工具调用、轮次上限、解析边界。"""

import json

import pytest

from app.api.routes_agent import (
    MAX_TOOL_ROUNDS,
    _parse_tool_call,
    _run_tool,
    run_agent_loop,
)
from app.llm.base import ChatMessage


class _FakeProvider:
    """依次返回预设回复；耗尽后返回最终回复。"""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls: list[list[ChatMessage]] = []

    async def chat(self, messages, temperature=0.7):
        self.calls.append(messages)
        if self.responses:
            return self.responses.pop(0)
        return "（最终回复）"


@pytest.mark.asyncio
async def test_agent_loop_runs_tools_then_replies():
    provider = _FakeProvider([
        json.dumps({"tool": "av_projects", "args": {}}, ensure_ascii=False),
        json.dumps({"tool": "av_products", "args": {"q": "会议话筒"}}, ensure_ascii=False),
        "根据检索，会议室推荐使用如下设备……",
    ])
    reply, messages = await run_agent_loop(provider, "sys", [], "帮我看看项目")
    assert reply.startswith("根据检索")
    assert len(provider.calls) == 3
    # 工具结果已回填上下文
    joined = "\n".join(m.content for m in messages)
    assert "【工具结果 av_projects】" in joined
    assert "【工具结果 av_products】" in joined


@pytest.mark.asyncio
async def test_agent_loop_stops_after_max_rounds():
    provider = _FakeProvider([json.dumps({"tool": "av_projects", "args": {}}, ensure_ascii=False)] * 10)
    reply, _messages = await run_agent_loop(provider, "sys", [], "再查一下", max_rounds=MAX_TOOL_ROUNDS)
    assert len(provider.calls) == MAX_TOOL_ROUNDS
    assert "需求仍不够清晰" in reply


@pytest.mark.asyncio
async def test_agent_loop_passes_history():
    provider = _FakeProvider(["直接回答"])
    history = [ChatMessage("user", "之前说过面积100平")]
    reply, messages = await run_agent_loop(provider, "sys", history, "继续")
    assert reply == "直接回答"
    contents = [m.content for m in provider.calls[0]]
    assert "sys" in contents
    assert "之前说过面积100平" in contents
    assert "继续" in contents


def test_parse_tool_call_edge_cases():
    assert _parse_tool_call('{"tool":"av_products","args":{"q":"led"}}') == {
        "tool": "av_products", "args": {"q": "led"}}
    # 带围栏/前缀 → 视为普通回复
    assert _parse_tool_call('```json\n{"tool":"x"}\n```') is None
    assert _parse_tool_call("推荐使用 P2 屏。") is None
    assert _parse_tool_call("{broken json") is None
    assert _parse_tool_call('{"tool":""}') is None


def test_run_tool_unknown_and_errors(tmp_path, monkeypatch):
    import app.api.routes_agent as ra

    monkeypatch.setattr(ra, "MEMORY_FILE", str(tmp_path / "MEMORY.md"))
    assert "未知工具" in _run_tool("nope", {})
    assert "暂无产出文件" in _run_tool("av_project_files", {"project_id": 999999})
    assert "（暂无记忆）" in _run_tool("memory_read", {})
    # memory_write 写入后可读回
    assert "已写入" in _run_tool("memory_write", {"content": "客户偏好惠威"})
    assert "客户偏好惠威" in _run_tool("memory_read", {})
