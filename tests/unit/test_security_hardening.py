"""安全加固回归：路径遍历 / 反代免口令 / 密钥加密存储 / 事件 task_id。"""
import io
import json

import pytest
from starlette.requests import Request

from app.llm import provider_store
from app.llm.provider_store import ProviderSetting
from app.security import crypto


def _mk_request(host: str, headers: list | None = None) -> Request:
    scope = {"type": "http", "client": (host, 12345), "headers": headers or []}
    return Request(scope)


# ---- H2：反代场景本机免口令失效 ----

def test_local_bypass_disabled_behind_proxy():
    from app.security.auth import _is_local_request

    assert _is_local_request(_mk_request("127.0.0.1")) is True
    assert _is_local_request(
        _mk_request("127.0.0.1", [(b"x-forwarded-for", b"1.2.3.4")])) is False
    assert _is_local_request(
        _mk_request("127.0.0.1", [(b"x-real-ip", b"1.2.3.4")])) is False


# ---- M1：api_key 落盘加密 ----

def test_secret_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(crypto, "KEY_PATH", str(tmp_path / "master.key"))
    enc = crypto.encrypt_secret("sk-topsecret")
    assert enc.startswith("enc:") and "sk-topsecret" not in enc
    assert crypto.decrypt_secret(enc) == "sk-topsecret"
    # 旧明文兼容：不带前缀原样返回
    assert crypto.decrypt_secret("sk-plain-old") == "sk-plain-old"
    assert crypto.encrypt_secret("") == "" and crypto.decrypt_secret("") == ""


def test_provider_store_encrypts_api_key_on_disk(tmp_path, monkeypatch):
    monkeypatch.setattr(crypto, "KEY_PATH", str(tmp_path / "master.key"))
    monkeypatch.setattr(provider_store, "STORE_PATH", str(tmp_path / "providers.json"))
    provider_store.save_all([ProviderSetting(id="c1", name="C1", api_key="sk-abc")])
    raw = json.loads((tmp_path / "providers.json").read_text(encoding="utf-8"))
    stored_key = raw["providers"][0]["api_key"]
    assert stored_key.startswith("enc:") and "sk-abc" not in stored_key
    loaded = provider_store.load_all()
    assert loaded[0].api_key == "sk-abc"


def test_provider_store_reads_legacy_plaintext(tmp_path, monkeypatch):
    monkeypatch.setattr(crypto, "KEY_PATH", str(tmp_path / "master.key"))
    monkeypatch.setattr(provider_store, "STORE_PATH", str(tmp_path / "providers.json"))
    (tmp_path / "providers.json").write_text(json.dumps(
        {"providers": [{"id": "old", "name": "Old", "api_key": "sk-legacy"}]}), encoding="utf-8")
    assert provider_store.load_all()[0].api_key == "sk-legacy"


def test_model_config_encrypted_on_disk(tmp_path, monkeypatch):
    import app.llm.registry as reg

    monkeypatch.setattr(crypto, "KEY_PATH", str(tmp_path / "master.key"))
    monkeypatch.setattr(reg, "CONFIG_PATH", str(tmp_path / "model.json"))
    reg.save_model_config({"provider": "deepseek", "api_key": "sk-m", "model": "m1"})
    raw = json.loads((tmp_path / "model.json").read_text(encoding="utf-8"))
    assert raw["api_key"].startswith("enc:")
    assert reg.load_model_config()["api_key"] == "sk-m"


# ---- M1 配套：GET /settings/model 不回传明文 key ----

def test_settings_model_get_masks_key(client, tmp_path, monkeypatch):
    import app.llm.registry as reg

    monkeypatch.setattr(crypto, "KEY_PATH", str(tmp_path / "master.key"))
    monkeypatch.setattr(reg, "CONFIG_PATH", str(tmp_path / "model.json"))
    reg.save_model_config({"provider": "deepseek", "api_key": "sk-1234567890ab"})
    r = client.get("/api/settings/model", headers={"X-Access-Token": "t"})
    body = r.json()
    assert body["api_key"] != "sk-1234567890ab"
    assert "******" in body["api_key"] and body["has_api_key"] is True


# ---- M4：任务事件携带 task_id ----

def test_notify_includes_task_id():
    from app.tasks import queue

    captured = []
    q = type("Q", (), {"put_nowait": lambda self, e: captured.append(e)})()
    queue._watchers.setdefault(42, []).append(q)
    try:
        queue._notify(42, {"type": "progress", "percent": 10, "message": "m"}, task_id="tid-1")
        queue._notify(42, {"type": "progress", "percent": 20, "message": "m"})
    finally:
        queue._watchers[42].remove(q)
    assert captured[0]["task_id"] == "tid-1"
    assert "task_id" not in captured[1]


# ---- H1：产品导入路径遍历防护 ----

def test_products_upload_path_traversal_blocked(client, tmp_path, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setattr(settings, "DB_PATH", str(tmp_path / "p.db"))
    monkeypatch.setattr(settings, "OUTPUT_DIR", str(tmp_path / "out"))
    from app.db.models import Base
    from app.db.session import get_engine
    Base.metadata.create_all(get_engine())

    # 构造最小合法 xlsx，文件名带路径穿越
    from openpyxl import Workbook
    buf = io.BytesIO()
    wb = Workbook()
    ws = wb.active
    ws.append(["设备名称", "品牌", "型号", "底价", "市场价"])
    ws.append(["音箱", "itc", "T-601", 100, 200])
    wb.save(buf)
    buf.seek(0)

    r = client.post("/api/products",
                    files={"file": ("../../evil.xlsx", buf, "application/vnd.ms-excel")},
                    headers={"X-Access-Token": "t"})
    assert r.status_code == 200
    # 穿越目标位置不得生成文件；实际落盘在 uploads 内
    assert not (tmp_path / "evil.xlsx").exists()
    uploads = tmp_path / "uploads"
    assert uploads.is_dir() and list(uploads.iterdir())


@pytest.fixture
def client(monkeypatch, tmp_path):
    from app.config import settings

    monkeypatch.setattr(settings, "ACCESS_TOKEN", "t")
    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:
        yield c
