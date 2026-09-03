import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "ACCESS_TOKEN", "test-token")
    with TestClient(app) as c:
        yield c


def _auth(client):
    return {"X-Access-Token": "test-token"}


def test_health_no_auth(client):
    r = client.get("/api/health")
    assert r.status_code == 200


def test_chat_flow(client, monkeypatch):
    class FakeProvider:
        name = "fake"

        async def chat(self, messages, temperature=0.7):
            return '{"area": 100, "scene": "会议室", "budget": null, "brand": null, "deliverables": ["doc"], "missing": ["budget"]}'

    monkeypatch.setattr("app.api.routes_chat.get_provider", lambda cfg: FakeProvider())
    r = client.post("/api/chat", json={"text": "100平会议室方案"}, headers=_auth(client))
    assert r.status_code == 200
    data = r.json()
    assert data["status"] in ("COLLECTING", "CONFIRMING")
    assert "预算" in data["reply"]


def test_settings_model_roundtrip(client, monkeypatch, tmp_path):
    import app.llm.registry as reg

    monkeypatch.setattr(reg, "CONFIG_PATH", str(tmp_path / "model.json"))
    r = client.put("/api/settings/model",
                   json={"provider": "deepseek", "api_key": "sk-x", "model": "deepseek-chat"},
                   headers=_auth(client))
    assert r.status_code == 200
    r2 = client.get("/api/settings/model", headers=_auth(client))
    assert r2.json()["provider"] == "deepseek"
