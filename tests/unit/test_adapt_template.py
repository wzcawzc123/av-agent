import json

import pytest

from app.db.session import get_engine, get_session
from app.db.models import Base, Product, ConfigTemplate
from app.llm.adapt import adapt_template


class FakeProvider:
    name = "fake"

    def __init__(self, resp):
        self.resp = resp

    async def chat(self, messages, temperature=0.7):
        return self.resp


@pytest.mark.asyncio
async def test_adapt_returns_devices(tmp_path):
    engine = get_engine(f"sqlite:///{tmp_path}/t.db")
    Base.metadata.create_all(engine)
    with get_session(engine) as s:
        s.add(Product(name="8寸音箱", model="AV-8A", low_price=800, market_price=1200, category="音箱"))
        s.add(ConfigTemplate(name="100平", area=100, scene="会议室",
                             config_json=json.dumps({"devices": [{"type": "音箱", "spec": "8寸", "qty": 2}]})))
        s.commit()
        resp = json.dumps({"devices": [{"type": "音箱", "spec": "8寸", "qty": 2}], "notes": "ok"})
        result = await adapt_template(FakeProvider(resp), {"area": 100}, None, [], s)
        assert len(result["devices"]) == 1
        assert result["devices"][0]["qty"] == 2


@pytest.mark.asyncio
async def test_adapt_invalid_json_raises(tmp_path):
    engine = get_engine(f"sqlite:///{tmp_path}/t.db")
    Base.metadata.create_all(engine)
    with get_session(engine) as s:
        with pytest.raises(Exception):
            await adapt_template(FakeProvider("not json"), {"area": 100}, None, [], s)
