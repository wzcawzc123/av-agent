"""智能入库 E2E：上传真实 Excel → LLM 分类/提取（mock）→ 产品入库 → 可检索。"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.config import settings


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(settings, "ACCESS_TOKEN", "test-token")
    with TestClient(app) as c:
        yield c


def _auth(client):
    return {"X-Access-Token": "test-token"}


class _IngestProvider:
    """按调用内容区分：分类 → 提取；model 由测试传入保证唯一。"""

    name = "fake"

    def __init__(self, model: str):
        self.model = model

    async def chat(self, messages, temperature=0.7):
        user = messages[-1].content if messages else ""
        if "文件内容" in user or "文件名" in user:
            return '{"type":"products","title":"测试产品清单","summary":"会议设备","confidence":0.95}'
        return '{"products": [{"name":"智能会议一体机","model":"%s","brand":"测试品牌",' \
               '"category":"会议平板","market_price":"¥18,500","base_price":"15000",' \
               '"params":{"屏幕":"75寸"}}]}' % self.model


def test_ingest_upload_products_then_searchable(client, monkeypatch):
    import io
    import uuid

    from openpyxl import Workbook

    model = f"E2E-{uuid.uuid4().hex[:6].upper()}"
    monkeypatch.setattr("app.api.routes_ingest.get_provider", lambda cfg: _IngestProvider(model))
    monkeypatch.setattr("app.api.routes_ingest.load_model_config",
                        lambda: {"provider": "deepseek", "api_key": "sk-test"})

    wb = Workbook()
    ws = wb.active
    ws.append(["产品名称", "型号", "品牌", "市场价"])
    ws.append(["智能会议一体机", model, "测试品牌", 18500])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    r = client.post(
        "/api/ingest",
        files={"file": ("产品清单.xlsx", buf, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"target": "auto"},
        headers=_auth(client),
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["ok"] is True, data
    assert data["type"] == "products"
    assert data["added"] == 1
    # 入库后可检索
    prods = client.get("/api/products", params={"q": model}, headers=_auth(client)).json()
    assert any(p["model"] == model for p in prods)
    # 幂等：重复上传跳过
    buf.seek(0)
    r2 = client.post(
        "/api/ingest",
        files={"file": ("产品清单.xlsx", buf, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"target": "auto"},
        headers=_auth(client),
    )
    data2 = r2.json()
    assert data2["skipped"] == 1


def test_ingest_rejects_unsupported_type(client, monkeypatch):
    r = client.post(
        "/api/ingest",
        files={"file": ("a.zip", b"x", "application/zip")},
        data={"target": "auto"},
        headers=_auth(client),
    )
    assert r.status_code == 400
    assert "不支持" in r.json()["detail"]
