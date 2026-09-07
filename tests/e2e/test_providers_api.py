
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings
from app.llm import provider_store


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "ACCESS_TOKEN", "test-token")
    monkeypatch.setattr(provider_store, "STORE_PATH", str(tmp_path / "providers.json"))
    with TestClient(app) as c:
        yield c


def _auth(client):
    return {"X-Access-Token": "test-token"}


def test_providers_list_includes_builtins(client):
    r = client.get("/api/providers", headers=_auth(client))
    assert r.status_code == 200
    ids = {p["id"] for p in r.json()}
    assert {"openai", "anthropic", "qwen", "deepseek", "kimi", "mimo",
            "minimax", "stepfun", "siliconflow", "openrouter", "glm", "wenxin", "gemini"} <= ids
    # api_key 掩码返回
    mimo = next(p for p in r.json() if p["id"] == "mimo")
    assert mimo["has_api_key"] is False


def test_create_update_delete_custom_provider(client):
    r = client.post("/api/providers", json={
        "name": "公司中转",
        "base_url": "https://gw.example.com/v1",
        "api_key": "sk-abc",
        "provider_type": "openai_compatible",
        "models": [{"model_id": "gpt-4o-mini", "display_name": "4o mini"}],
    }, headers=_auth(client))
    assert r.status_code == 200
    pid = r.json()["id"]
    assert r.json()["name"] == "公司中转"
    assert r.json()["has_api_key"] is True

    # 更新
    r = client.put(f"/api/providers/{pid}", json={
        "name": "公司中转2", "base_url": "https://gw.example.com/v1", "api_key": "sk-xyz",
        "models": [{"model_id": "gpt-4o", "display_name": "4o"}],
    }, headers=_auth(client))
    assert r.status_code == 200
    assert r.json()["name"] == "公司中转2"
    assert r.json()["models"][0]["model_id"] == "gpt-4o"

    # 复制
    r = client.post(f"/api/providers/{pid}/copy", headers=_auth(client))
    assert r.status_code == 200
    assert r.json()["name"] == "公司中转2 副本"

    # 删除
    r = client.delete(f"/api/providers/{pid}", headers=_auth(client))
    assert r.status_code == 200

    # 内置不可删除
    r = client.delete("/api/providers/deepseek", headers=_auth(client))
    assert r.status_code == 400


def test_model_config_syncs_api_key_to_provider(client, monkeypatch):
    # 先给内置 deepseek 填 key
    r = client.put("/api/settings/model", json={
        "provider": "deepseek", "api_key": "sk-synced", "model": "deepseek-chat",
    }, headers=_auth(client))
    assert r.status_code == 200
    stored = provider_store.get_provider_by_id("deepseek")
    assert stored.api_key == "sk-synced"
