from fastapi.testclient import TestClient

from app.main import app


def test_index_served():
    with TestClient(app) as c:
        r = c.get("/")
        assert r.status_code == 200
        assert "chat-app" in r.text
