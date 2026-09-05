import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(settings, "ACCESS_TOKEN", "test-token")
    with TestClient(app) as c:
        yield c


def _auth():
    return {"X-Access-Token": "test-token"}


def test_generate_rejected_when_requirement_incomplete(client, monkeypatch):
    """需求未完整（槽位为空）时，/api/generate 应拒绝，防止绕过聊天流程浪费 token。"""
    monkeypatch.setattr("app.api.routes_generate.get_session_slots", lambda pid: {})
    r = client.post("/api/generate", json={"project_id": 1}, headers=_auth())
    assert r.status_code == 422
    assert "需求未完整" in r.json()["detail"]


def test_generate_allowed_when_requirement_complete(client, monkeypatch):
    """关键槽位齐全时允许提交生成。"""
    slots = {"area": 100, "scene": "会议室", "budget": "5万",
             "brand": "惠威", "deliverables": ["excel"]}
    monkeypatch.setattr("app.api.routes_generate.get_session_slots", lambda pid: slots)
    monkeypatch.setattr("app.api.routes_generate.submit_task", lambda pid, cfg, s: "task-1")
    r = client.post("/api/generate", json={"project_id": 1}, headers=_auth())
    assert r.status_code == 200
    assert r.json()["task_id"] == "task-1"
