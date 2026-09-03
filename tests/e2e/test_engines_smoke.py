"""端到端冒烟：四引擎真实 DB 生成到 tmp 输出，断言文件存在且非空。"""
import os

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.db.models import Base, Product
from app.db.session import get_engine, get_session


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "ACCESS_TOKEN", "test-token")
    monkeypatch.setattr(settings, "DB_PATH", str(tmp_path / "smoke.db"))
    monkeypatch.setattr(settings, "OUTPUT_DIR", str(tmp_path / "output"))
    from app.main import app
    with TestClient(app) as c:
        yield c


def _auth():
    return {"X-Access-Token": "test-token"}


def test_full_pipeline_smoke(client, tmp_path):
    # 1) 会议
    r = client.post("/api/engines/meeting", json={"code": "12-10-5-0-0-1-2-", "header": {}},
                    headers=_auth())
    assert r.status_code == 200
    meeting_file = r.json()["file"]
    assert os.path.isfile(meeting_file) and os.path.getsize(meeting_file) > 0

    # 2) 广播
    r = client.post("/api/engines/broadcast",
                    json={"zones": [{"zone": "1F大厅", "T-601": 24, "T-105": 12},
                                    {"zone": "2F走廊", "T-105": 8}], "header": {}},
                    headers=_auth())
    assert r.status_code == 200
    bc = r.json()
    assert os.path.isfile(bc["file"]) and os.path.getsize(bc["file"]) > 0
    assert len(bc["zones_with_power"]) == 2
    assert bc["zones_with_power"][0]["amplifier"]  # 有选型结果

    # 3) LED
    r = client.post("/api/engines/led",
                    json={"want_w_m": 6, "want_h_m": 3.5, "model": "TV-PH250-YZ",
                          "round_mode": "就近", "header": {}},
                    headers=_auth())
    assert r.status_code == 200
    led = r.json()
    assert os.path.isfile(led["file"]) and os.path.getsize(led["file"]) > 0
    assert led["layout"]["count_w"] == 24

    # 4) 偏离表（需要产品库数据）
    engine = get_engine()
    Base.metadata.create_all(engine)
    with get_session(engine) as s:
        s.add(Product(name="全频音箱", model="TK-L208", brand="itc",
                      description="1.8寸全频音箱\n2.阻抗8Ω"))
        s.add(Product(name="功放", model="TA-2900", brand="itc", description="2×900W功放"))
    r = client.post("/api/engines/deviation",
                    json={"tender_items": ["1、8寸全频音箱", "2、阻抗8Ω", "3、900W功放"],
                          "models": ["TK-L208", "TA-2900"], "llm_enabled": False},
                    headers=_auth())
    assert r.status_code == 200
    dev = r.json()
    assert os.path.isfile(dev["file"]) and os.path.getsize(dev["file"]) > 0
    assert len(dev["results"]) == 3
