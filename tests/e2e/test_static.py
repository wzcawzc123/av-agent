import json

from fastapi.testclient import TestClient

from app.main import app


def test_index_served():
    with TestClient(app) as c:
        r = c.get("/")
        assert r.status_code == 200
        assert "chat-app" in r.text


def test_pwa_manifest_served():
    with TestClient(app) as c:
        r = c.get("/manifest.json")
        assert r.status_code == 200
        data = r.json()
        assert data["name"].startswith("AV Agent")
        assert data["display"] == "standalone"
        assert any(i["sizes"] == "192x192" for i in data["icons"])


def test_pwa_icons_served():
    with TestClient(app) as c:
        for path in ("/icons/icon-192.png", "/icons/icon-512.png"):
            r = c.get(path)
            assert r.status_code == 200
            assert r.headers["content-type"] == "image/png"
            assert len(r.content) > 100


def test_service_worker_served():
    with TestClient(app) as c:
        r = c.get("/sw.js")
        assert r.status_code == 200
        assert "CACHE_NAME" in r.text


def test_index_links_pwa():
    with TestClient(app) as c:
        r = c.get("/")
        assert 'rel="manifest"' in r.text
        assert "theme-color" in r.text
        assert "isSecureContext" in r.text
