"""引擎 API：deviation / meeting / broadcast / led 四个生成端点 + 引擎注册入口"""
import pytest
from fastapi.testclient import TestClient

from app.config import settings


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "ACCESS_TOKEN", "test-token")
    monkeypatch.setattr(settings, "DB_PATH", str(tmp_path / "avagent.db"))
    monkeypatch.setattr(settings, "OUTPUT_DIR", str(tmp_path / "output"))
    from app.main import app
    with TestClient(app) as c:
        yield c


def _auth():
    return {"X-Access-Token": "test-token"}


def test_list_engines(client):
    from app.engines import list_engines
    names = list_engines()
    assert {"deviation", "meeting", "broadcast", "led"} <= set(names)


def test_engine_meeting_endpoint(client):
    r = client.post("/api/engines/meeting", json={"code": "1-10-5-", "header": {}},
                    headers=_auth())
    assert r.status_code == 200
    data = r.json()
    assert "file" in data and len(data["rows"]) >= 5
    assert data["rows"][0]["price"] == 0


def test_engine_deviation_endpoint(client, monkeypatch):
    from app.db.session import get_engine, get_session
    from app.db.models import Base, Product
    engine = get_engine()
    Base.metadata.create_all(engine)
    with get_session(engine) as s:
        s.add(Product(name="矩阵", model="DS-8004", brand="itc",
                      description="1.支持HDMI1.4\n2.双向串口控制"))
    r = client.post("/api/engines/deviation",
                    json={"tender_items": ["1、支持HDMI输入接口", "2、支持双向串口控制"],
                          "models": ["DS-8004"], "llm_enabled": False},
                    headers=_auth())
    assert r.status_code == 200
    data = r.json()
    assert data["low_confidence"] == 0


def test_engine_broadcast_endpoint(client):
    r = client.post("/api/engines/broadcast",
                    json={"zones": [{"zone": "分区1", "MH-C8A": 12, "MH-V5-PAS04C": 6}],
                          "header": {}},
                    headers=_auth())
    assert r.status_code == 200
    data = r.json()
    assert data["zones_with_power"][0]["power_w"] == (12 * 80 + 6 * 30) * 1.5
    assert data["zones_with_power"][0]["amplifier"]


def test_engine_led_endpoint(client):
    r = client.post("/api/engines/led",
                    json={"want_w_m": 6, "want_h_m": 4, "model": "TV-PH250-YZ",
                          "round_mode": "就近", "header": {}},
                    headers=_auth())
    assert r.status_code == 200
    data = r.json()
    assert data["layout"]["count_w"] == 24 and data["layout"]["count_h"] == 16


def test_engine_meeting_structured_fields(client):
    """结构化字段直接调会议引擎（无需编码）。"""
    r = client.post("/api/engines/meeting",
                    json={"length_m": 12, "width_m": 10, "height_m": 5,
                          "scene": "圆桌", "config": "中配", "mic": "2", "antenna": "1",
                          "header": {}},
                    headers=_auth())
    assert r.status_code == 200
    data = r.json()
    assert data["code"] == "12-10-5-0-0-1-2-0-2-1-"
    roles = {row["role"] for row in data["rows"]}
    assert "无线会议主机" in roles and "天线分配器" in roles


def test_engine_meeting_code_still_works(client):
    """编码直传仍兼容。"""
    r = client.post("/api/engines/meeting",
                    json={"code": "12-10-5-0-0-2-3-"}, headers=_auth())
    assert r.status_code == 200
    assert r.json()["code"] == "12-10-5-0-0-2-3-"
