"""配置模板智能上传 E2E：上传 100 平会议室配置表 → LLM 解析(mock) → ConfigTemplate 落库 → 可按面积场景匹配。"""

import io

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


class _CfgProvider:
    name = "fake"

    async def chat(self, messages, temperature=0.7):
        return ('{"area":100,"scene":"会议室","config_level":"中配",'
                '"systems":["prosound","speech","display"],'
                '"rows":[{"system":"prosound","type":"专业音箱","spec":"8寸 壁挂","qty":2,"unit":"只"},'
                '{"system":"speech","type":"手拉手发言主机","spec":"支持20席","qty":1,"unit":"台"},'
                '{"system":"display","type":"会议一体机","spec":"86寸","qty":1,"unit":"台"}]}')


def test_ingest_config_template_then_match(client, monkeypatch, tmp_path):
    from openpyxl import Workbook

    monkeypatch.setattr("app.llm.registry.get_provider", lambda cfg: _CfgProvider())
    monkeypatch.setattr("app.llm.registry.load_model_config",
                        lambda: {"provider": "deepseek", "api_key": "sk-test"})

    wb = Workbook()
    ws = wb.active
    ws.append(["系统", "设备", "规格", "数量", "单位"])
    ws.append(["扩声", "专业音箱", "8寸 壁挂", 2, "只"])
    ws.append(["发言", "手拉手主机", "支持20席", 1, "台"])
    ws.append(["显示", "会议一体机", "86寸", 1, "台"])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    r = client.post(
        "/api/templates/ingest",
        files={"file": ("100平会议室配置.xlsx", buf,
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"name": "", "area": "0", "scene": "", "config_level": ""},
        headers=_auth(client),
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["ok"] is True, data
    assert data["scene"] == "会议室"
    assert data["area"] == 100
    assert data["rows"] == 3

    # 新入库模板自身 rows 完整
    from app.db.session import get_session
    from app.db.models import ConfigTemplate
    import json as _json

    with get_session() as s:
        tpl = s.get(ConfigTemplate, data["id"])
        assert tpl is not None
        cfg = _json.loads(tpl.config_json or "{}")
        assert len(cfg.get("rows", [])) == 3

    # 可按面积+场景匹配到配置模板（存在即可，具体命中的可能是历史模板）
    from app.db.template_store import find_config_template

    with get_session() as s:
        matched = find_config_template(s, area=100, scene="会议室")
        assert matched is not None
        assert matched.area == 100


def test_ingest_config_rejects_when_no_model(client, monkeypatch):
    monkeypatch.setattr("app.llm.registry.load_model_config", lambda: {})
    r = client.post(
        "/api/templates/ingest",
        files={"file": ("a.xlsx", b"x", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"name": "", "area": "0", "scene": "", "config_level": ""},
        headers=_auth(client),
    )
    assert r.status_code == 200
    assert r.json()["need_config"] is True
