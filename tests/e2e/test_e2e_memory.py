"""记忆全链路 E2E：写入 MEMORY.md → 专家对话/Agent 对话都收到记忆注入。"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "ACCESS_TOKEN", "test-token")
    # 隔离记忆文件
    import app.api.routes_agent as ra

    monkeypatch.setattr(ra, "MEMORY_FILE", str(tmp_path / "MEMORY.md"))
    with TestClient(app) as c:
        yield c


def _auth(client):
    return {"X-Access-Token": "test-token"}


class _CaptureProvider:
    """记录最近一次调用的消息列表（system + user）。"""

    def __init__(self):
        self.messages = []
        self.calls = 0

    async def chat(self, messages, temperature=0.7):
        self.calls += 1
        self.messages = messages
        return '{"area": 100, "scene": "会议室", "budget": "5万", "brand": "惠威", "deliverables": ["doc"]}'

    def text(self):
        return "\n".join(m.content for m in self.messages)


def _write_memory(client, content):
    import app.api.routes_agent as ra

    with open(ra.MEMORY_FILE, "w", encoding="utf-8") as f:
        f.write(content)


def test_expert_chat_receives_memory(client, monkeypatch):
    provider = _CaptureProvider()
    monkeypatch.setattr("app.api.routes_chat.get_provider", lambda cfg: provider)
    monkeypatch.setattr("app.api.routes_chat.load_model_config",
                        lambda: {"provider": "deepseek", "api_key": "sk-test"})
    _write_memory(client, "客户偏好惠威，预算通常 5-10 万")
    r = client.post("/api/chat", json={"text": "100平会议室方案"}, headers=_auth(client))
    assert r.status_code == 200
    assert "客户偏好惠威" in provider.text()
    assert "【跨会话记忆】" in provider.text()


def test_expert_chat_without_memory(client, monkeypatch):
    provider = _CaptureProvider()
    monkeypatch.setattr("app.api.routes_chat.get_provider", lambda cfg: provider)
    monkeypatch.setattr("app.api.routes_chat.load_model_config",
                        lambda: {"provider": "deepseek", "api_key": "sk-test"})
    r = client.post("/api/chat", json={"text": "100平会议室方案"}, headers=_auth(client))
    assert r.status_code == 200
    assert "【跨会话记忆】" not in provider.text()


def test_agent_chat_receives_memory_in_system_prompt(client, monkeypatch):
    provider = _CaptureProvider()
    monkeypatch.setattr("app.api.routes_agent.get_provider", lambda cfg: provider)
    monkeypatch.setattr("app.api.routes_agent.load_model_config",
                        lambda: {"provider": "deepseek", "api_key": "sk-test"})
    _write_memory(client, "客户常用 MAXHUB 会议平板")
    r = client.post("/api/agent/chat", json={"text": "推荐显示设备"}, headers=_auth(client))
    assert r.status_code == 200
    sys_text = "".join(m.content for m in provider.messages if m.role == "system")
    assert "客户常用 MAXHUB" in sys_text
    assert "【跨会话记忆】" in sys_text
