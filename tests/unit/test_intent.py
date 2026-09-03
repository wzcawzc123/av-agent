import pytest
from app.orchestrator.intent import extract_json, parse_intent


def test_extract_json_with_code_fence():
    text = '```json\n{"area": 100}\n```'
    assert extract_json(text) == {"area": 100}


def test_extract_json_plain():
    assert extract_json('{"area": 100, "scene": "会议室"}')["scene"] == "会议室"


@pytest.mark.asyncio
async def test_parse_intent_mock(monkeypatch):
    class FakeProvider:
        name = "fake"

        async def chat(self, messages, temperature=0.7):
            return '{"area": 100, "scene": "会议室", "budget": null, "brand": null, "deliverables": ["doc"], "missing": ["budget"]}'

    slots = await parse_intent(FakeProvider(), "100平会议室方案")
    assert slots["area"] == 100
    assert slots["missing"] == ["budget"]
