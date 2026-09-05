import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "ACCESS_TOKEN", "test-token")
    monkeypatch.setattr(settings, "OUTPUT_DIR", str(tmp_path))
    with TestClient(app) as c:
        yield c


def _auth():
    return {"X-Access-Token": "test-token"}


def test_download_ok(client, tmp_path):
    f = tmp_path / "方案.docx"
    f.write_bytes(b"hello")
    r = client.get("/api/download", params={"path": str(f)}, headers=_auth())
    assert r.status_code == 200
    assert b"hello" in r.content


def test_download_404_when_outside_output_dir(client, tmp_path):
    outside = tmp_path.parent / "outside.docx"
    outside.write_bytes(b"x")
    r = client.get("/api/download", params={"path": str(outside)}, headers=_auth())
    assert r.status_code == 404


def test_download_404_when_missing(client, tmp_path):
    f = tmp_path / "nope.docx"
    r = client.get("/api/download", params={"path": str(f)}, headers=_auth())
    assert r.status_code == 404
