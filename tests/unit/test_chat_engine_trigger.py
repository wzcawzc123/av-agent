"""/api/chat 触发引擎：无需配置模型，返回 engine 结果与文件。"""
import pytest
from fastapi.testclient import TestClient

from app.config import settings


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "ACCESS_TOKEN", "t")
    monkeypatch.setattr(settings, "DB_PATH", str(tmp_path / "c.db"))
    monkeypatch.setattr(settings, "OUTPUT_DIR", str(tmp_path / "out"))
    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))  # 隔离 model.json/providers.json
    from app.llm import registry as llm_registry
    llm_registry.CONFIG_PATH = None  # 重置路径缓存
    from app.db.models import Base
    from app.db.session import get_engine
    Base.metadata.create_all(get_engine())
    from app.main import app
    with TestClient(app) as c:
        yield c


def test_chat_triggers_meeting_without_model(client):
    r = client.post("/api/chat", json={"text": "会议清单 12-10-5-0-0-1-2-"},
                    headers={"X-Access-Token": "t"})
    assert r.status_code == 200
    data = r.json()
    assert data.get("engine") == "meeting"
    assert "会议设备清单" in data["reply"]
    assert "meeting_" in data["files"][0] and data["files"][0].endswith(".xlsx")


def test_chat_triggers_broadcast(client):
    r = client.post("/api/chat", json={"text": "广播系统 1F大厅 24只T-601 12只T-105"},
                    headers={"X-Access-Token": "t"})
    data = r.json()
    assert data.get("engine") == "broadcast"
    assert "功放" in data["reply"]


def test_chat_plain_message_falls_back_to_collecting(client):
    """非引擎消息且未配置模型 → 提示配置。"""
    r = client.post("/api/chat", json={"text": "你好"},
                    headers={"X-Access-Token": "t"})
    data = r.json()
    assert data.get("engine") is None
    assert data.get("need_config") is True


def test_chat_llm_error_returns_guidance(client, monkeypatch):
    """LLM 调用失败返回友好引导而非 500。"""
    monkeypatch.setattr("app.api.routes_chat.load_model_config",
                        lambda: {"provider": "deepseek", "api_key": "sk-bad"})

    async def boom(cfg):
        raise RuntimeError("401")

    monkeypatch.setattr("app.api.routes_chat.get_provider", lambda cfg: type("P", (), {"name": "f", "chat": boom})())
    r = client.post("/api/chat", json={"text": "100平会议室方案"},
                    headers={"X-Access-Token": "t"})
    assert r.status_code == 200
    data = r.json()
    assert data.get("engine_error") is True
    assert "模型" in data["reply"]
