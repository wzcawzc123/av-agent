from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.security.auth import verify_token, require_token_router


def test_verify_token():
    assert verify_token("correct-token", "correct-token") is True
    assert verify_token("wrong", "correct-token") is False


def test_require_token_dependency(monkeypatch):
    monkeypatch.setattr("app.security.auth.settings.ACCESS_TOKEN", "t")
    app = FastAPI()
    app.include_router(require_token_router())
    client = TestClient(app)
    r = client.get("/api/health", headers={"X-Access-Token": "t"})
    assert r.status_code == 200
    r2 = client.get("/api/health", headers={"X-Access-Token": "bad"})
    assert r2.status_code == 401
