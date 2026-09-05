"""招标改单端到端测试：上传→匹配→快照→编辑→确认。"""
import io

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "ACCESS_TOKEN", "test-token")
    with TestClient(app) as c:
        yield c


def _auth():
    return {"X-Access-Token": "test-token"}


def _make_excel() -> bytes:
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "设备清单"
    headers = ["序号", "设备名称", "品牌", "型号", "技术参数", "数量", "单位"]
    ws.append(headers)
    rows = [
        [1, "专业音箱", "惠威", "LX12", "12英寸 400W", "4", "只"],
        [2, "功率放大器", "惠威", "LA600", "2×600W", "2", "台"],
        [3, "调音台", "雅马哈", "MG16", "16通道", "1", "台"],
        [4, "投影机", "索尼", "EX570", "4200流明", "1", "台"],
        [5, "音频处理器", "Bose", "ControlSpace", "8进8出", "1", "台"],
    ]
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _upload_tender(client):
    excel = _make_excel()
    r = client.post(
        "/api/tender/upload",
        data={"project_id": "1"},
        files={"file": ("test_tender.xlsx", io.BytesIO(excel), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=_auth(),
    )
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert "snapshot" in data
    assert data["project_id"] == 1
    assert isinstance(data["items"], list)
    assert len(data["items"]) > 0
    for item in data["items"]:
        assert "idx" in item
        assert "name" in item
        assert "status" in item
        assert "score" in item
    return data


def test_tender_upload_and_match(client):
    """上传招标文件，解析匹配后返回快照与行数据。"""
    _upload_tender(client)


def test_tender_snapshots(client):
    data = _upload_tender(client)
    snap = data["snapshot"]
    # 列表快照
    r = client.get("/api/tender/1/snapshots", headers=_auth())
    assert r.status_code == 200
    snaps = r.json()
    assert any(s["snapshot"] == snap for s in snaps["snapshots"])
    # 读取快照行
    r = client.get(f"/api/tender/1/snapshots/{snap}", headers=_auth())
    assert r.status_code == 200
    rows = r.json()
    assert len(rows["rows"]) == len(data["items"])


def test_tender_edit_and_confirm(client):
    data = _upload_tender(client)
    snap = data["snapshot"]
    items = data["items"]
    # 编辑第一行
    idx = items[0]["idx"]
    r = client.put(
        f"/api/tender/1/rows/{idx}",
        json={"brand": "惠威", "model": "LX12-PRO", "status": "matched", "remark": "test"},
        headers={"Content-Type": "application/json", ** _auth()},
    )
    assert r.status_code == 200
    # 确认改单
    r = client.post(
        "/api/tender/1/confirm",
        json={"project_id": 1, "snapshot": snap},
        headers={"Content-Type": "application/json", ** _auth()},
    )
    assert r.status_code == 200
    bom = r.json()
    assert "rows" in bom
    assert isinstance(bom["rows"], list)
