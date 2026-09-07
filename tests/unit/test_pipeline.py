import json

import pytest

from app.db.session import get_engine, get_session
from app.db.models import Base, ConfigTemplate
from app.generators.pipeline import generate_deliverables


class FakeProvider:
    name = "fake"

    def __init__(self, resp):
        self.resp = resp

    async def chat(self, messages, temperature=0.7):
        return self.resp


@pytest.mark.asyncio
async def test_generate_deliverables_doc(tmp_path):
    engine = get_engine(f"sqlite:///{tmp_path}/t.db")
    Base.metadata.create_all(engine)
    with get_session(engine) as s:
        s.add(ConfigTemplate(name="100平", area=100, scene="会议室",
                             config_json=json.dumps({"devices": []})))
        s.commit()
        prov = FakeProvider(json.dumps({"devices": [{"type": "音箱", "spec": "8寸", "qty": 2}], "notes": ""}))
        project_dir = tmp_path / "proj"
        project_dir.mkdir()
        slots = {"area": 100, "scene": "会议室", "deliverables": ["doc"]}
        progress = []
        result = await generate_deliverables(
            {"deliverables": ["doc"], "project_dir": str(project_dir), "template_paths": {}},
            prov, slots, s, lambda p, m: progress.append((p, m)))
        assert "doc" in result["files"]
        assert any(p > 0 for p, _ in progress)
