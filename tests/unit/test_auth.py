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


def test_require_token_local_host_bypass(monkeypatch):
    """本机（127.0.0.1）访问免口令，即使不带 token 也应放行；局域网 IP 才校验。"""
    from app.security.auth import _is_local_request
    from starlette.requests import Request

    def mk(host):
        return Request({"type": "http", "client": (host, 12345)})

    assert _is_local_request(mk("127.0.0.1")) is True
    assert _is_local_request(mk("::1")) is True
    assert _is_local_request(mk("localhost")) is True
    assert _is_local_request(mk("192.168.1.5")) is False
    assert _is_local_request(mk("10.0.0.3")) is False
