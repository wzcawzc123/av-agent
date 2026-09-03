import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings
from app.llm import provider_store
from app.api import routes_settings as rs


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "ACCESS_TOKEN", "test-token")
    monkeypatch.setattr(provider_store, "STORE_PATH", str(tmp_path / "providers.json"))
    monkeypatch.setattr(rs, "_UPDATE_CFG_PATH", tmp_path / "update.json")
    with TestClient(app) as c:
        yield c


def _auth(client):
    return {"X-Access-Token": "test-token"}


class _FakeResp:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class _FakeClient:
    def __init__(self, payload, status=200):
        self._payload = payload
        self._status = status
        self.sent = {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get(self, url, headers=None):
        self.sent = {"url": url, "headers": headers}
        return _FakeResp(self._payload, self._status)


def test_update_config_roundtrip(client):
    r = client.get("/api/update/config", headers=_auth(client))
    assert r.status_code == 200
    assert r.json()["check_url"].startswith("https://api.github.com/repos/")
    assert r.json()["has_token"] is False

    r = client.put("/api/update/config", json={
        "check_url": "https://api.github.com/repos/wzcawzc123/av-agent/releases/latest",
        "token": "ghp_secret",
    }, headers=_auth(client))
    assert r.status_code == 200

    r = client.get("/api/update/config", headers=_auth(client))
    assert r.json()["has_token"] is True


def test_check_update_no_update(client, monkeypatch):
    payload = {"tag_name": "v1.0.0", "body": "无更新", "published_at": "2024-01-01T00:00:00Z"}
    monkeypatch.setattr(rs._httpx, "AsyncClient", lambda *a, **k: _FakeClient(payload))
    r = client.get("/api/update/check", headers=_auth(client))
    assert r.status_code == 200
    data = r.json()
    assert data["current_version"] == "1.0.0"
    assert data["has_update"] is False


def test_check_update_finds_new_release(client, monkeypatch):
    payload = {
        "tag_name": "v1.1.0",
        "body": "新增功能",
        "published_at": "2025-02-02T00:00:00Z",
        "html_url": "https://github.com/wzcawzc123/av-agent/releases/tag/v1.1.0",
        "assets": [{"name": "AVAgent.exe", "browser_download_url": "https://github.com/wzcawzc123/av-agent/releases/download/v1.1.0/AVAgent.exe"}],
    }
    monkeypatch.setattr(rs._httpx, "AsyncClient", lambda *a, **k: _FakeClient(payload))
    r = client.get("/api/update/check", headers=_auth(client))
    assert r.status_code == 200
    data = r.json()
    assert data["has_update"] is True
    assert data["latest_version"] == "1.1.0"
    assert data["download_url"].endswith("AVAgent.exe")
    assert data["notes"] == "新增功能"
