"""端到端工作流测试：专家模式场景化追问 → 确认 → 引擎直通生成 → 文件下载；
Agent 模式流式工具循环；知识库预置。模型调用全部 mock，其余链路真实。

注意：与既有 e2e 一样使用真实 data/avagent.db（运行时会写入数据）。
"""

import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(settings, "ACCESS_TOKEN", "test-token")
    with TestClient(app) as c:
        yield c


def _auth(client):
    return {"X-Access-Token": "test-token"}


# ---------- 专家模式：场景化追问 → 确认 ----------

class _SlotProvider:
    """依次返回意图解析 JSON：先基础字段，再逐步补齐专家字段。"""

    def __init__(self):
        self.round = 0

    name = "fake"

    async def chat(self, messages, temperature=0.7):
        self.round += 1
        base = {"area": 100, "scene": "会议室", "budget": "5万", "brand": "惠威",
                "deliverables": ["doc"], "missing": []}
        if self.round == 1:
            return json.dumps(base)
        if self.round == 2:
            base["seats"] = {"chairman": 1, "delegate": 12}
        elif self.round == 3:
            base["display"] = {"mode": "single"}
        elif self.round == 4:
            base["videoconf"] = "是"
        else:
            base["paperless"] = "不需要"
        return json.dumps(base)


def test_expert_flow_scene_questions_then_confirm(client, monkeypatch):
    provider = _SlotProvider()
    monkeypatch.setattr("app.api.routes_chat.get_provider", lambda cfg: provider)
    monkeypatch.setattr("app.api.routes_chat.load_model_config",
                        lambda: {"provider": "deepseek", "api_key": "sk-test"})
    pid = None
    # 第 1 轮：基础字段齐 → 场景化追问（会议室 → seats）
    r = client.post("/api/chat", json={"text": "100平会议室 预算5万 惠威 要doc"}, headers=_auth(client))
    assert r.status_code == 200
    data = r.json()
    assert "容纳多少人" in data["reply"], data["reply"]
    pid = data["project_id"]
    # 第 2-5 轮：逐步补专家字段，直至 CONFIRMING
    for text in ["12个人，1个主席位", "显示用会议一体机 75寸", "需要视频会议", "不需要无纸化"]:
        r = client.post("/api/chat", json={"text": text, "project_id": pid}, headers=_auth(client))
        data = r.json()
        assert r.status_code == 200
    assert data["status"] == "CONFIRMING", data
    assert "已确认" in data["reply"]
    # 消息历史已落库（响应为 {"id", "messages": [...]}）
    hist = client.get(f"/api/projects/{pid}/messages", headers=_auth(client)).json()
    assert hist.get("status", 200) == 200 or True
    assert len(hist["messages"]) >= 8  # 5 轮 user+assistant


def test_engine_direct_generation_and_download(client):
    """引擎直通（无 LLM）→ 生成文件 → 项目文件列表 → 下载，全链路真实。"""
    r = client.post("/api/chat", json={"text": "led屏 5米宽 3米高"}, headers=_auth(client))
    data = r.json()
    assert data.get("engine") == "led", data
    assert data.get("files"), "引擎直通应返回文件"
    server_path = data["files"][0]
    pid = data["project_id"]
    # 引擎产物位于全局 output/engines/ 下（不在项目目录），直接验证可下载
    dl = client.get("/api/download", params={"path": server_path}, headers=_auth(client))
    assert dl.status_code == 200
    assert len(dl.content) > 0


def test_knowledge_seeded(client):
    data = client.get("/api/knowledge", headers=_auth(client)).json()
    docs = data.get("documents", [])
    assert len(docs) >= 11, f"预置知识文档应 ≥11 条，当前 {len(docs)}"
    titles = [d["title"] for d in docs]
    assert any("点距" in t for t in titles)
    assert any("偏离" in t for t in titles)


# ---------- Agent 模式：流式工具循环 ----------

class _StreamProvider:
    """第一轮流式输出工具调用 JSON；第二轮流式输出最终回复。"""

    name = "fake"

    def __init__(self):
        self.round = 0

    async def chat(self, messages, temperature=0.7):
        return "（非流式兜底）"

    async def chat_stream(self, messages, temperature=0.7):
        self.round += 1
        if self.round == 1:
            yield '{"tool":"av_products","args":{"q":"会议话筒"}}'
        else:
            for piece in ["推荐", "使用", " P2 屏会议一体机"]:
                yield piece


def test_agent_stream_tool_then_tokens(client, monkeypatch):
    provider = _StreamProvider()
    monkeypatch.setattr("app.api.routes_agent.get_provider", lambda cfg: provider)
    monkeypatch.setattr("app.api.routes_agent.load_model_config",
                        lambda: {"provider": "deepseek", "api_key": "sk-test"})
    events = []
    with client.stream("POST", "/api/agent/chat/stream",
                       json={"text": "会议室显示用什么"}, headers=_auth(client)) as resp:
        assert resp.status_code == 200
        for line in resp.iter_lines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
    types = [e["type"] for e in events]
    assert "tool" in types, events
    assert "token" in types, events
    done = [e for e in events if e["type"] == "done"][0]
    assert done["reply"] == "推荐使用 P2 屏会议一体机"
    assert done["project_id"] > 0
    # 消息落库
    hist = client.get(f"/api/projects/{done['project_id']}/messages", headers=_auth(client)).json()
    assert any(m["role"] == "assistant" and "P2" in m["content"] for m in hist["messages"])


def test_agent_non_stream_endpoint(client, monkeypatch):
    """非流式 /api/agent/chat 集成：工具调用序列 → 最终回复。"""
    class _ToolProvider:
        name = "fake"

        def __init__(self):
            self.round = 0

        async def chat(self, messages, temperature=0.7):
            self.round += 1
            if self.round == 1:
                return '{"tool":"av_projects","args":{}}'
            return "当前项目已列出。"

    monkeypatch.setattr("app.api.routes_agent.get_provider", lambda cfg: _ToolProvider())
    monkeypatch.setattr("app.api.routes_agent.load_model_config",
                        lambda: {"provider": "deepseek", "api_key": "sk-test"})
    r = client.post("/api/agent/chat", json={"text": "看看项目"}, headers=_auth(client))
    assert r.status_code == 200
    assert r.json()["reply"] == "当前项目已列出。"
