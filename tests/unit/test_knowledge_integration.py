"""知识库接入 chat 流程：parse_intent context_docs 参数传递验证。"""
import json
import asyncio


def test_parse_intent_injects_context_docs(monkeypatch):
    """parse_intent 接收 context_docs 后，参考文档标题出现在 user prompt 中。"""
    import app.orchestrator.intent as mod

    captured = {}

    class FakeProvider:
        async def chat(self, messages, **kw):
            captured["user_text"] = messages[-1].content
            return '{"missing": []}'

    monkeypatch.setattr(mod, "extract_json", lambda s: json.loads(s))

    docs = [
        {"title": "天花音箱规范", "excerpt": "推荐 MH-C6A 用于60㎡以下会议室"},
        {"title": "功放选型指南", "excerpt": "MH-L240 额定400W×2"},
    ]
    asyncio.run(
        mod.parse_intent(FakeProvider(), "60平会议室清单", context_docs=docs)
    )
    assert "参考文档" in captured["user_text"]
    assert "天花音箱规范" in captured["user_text"]
    assert "MH-C6A" in captured["user_text"]


def test_parse_intent_without_context_docs(monkeypatch):
    """无 context_docs 时 prompt 仅含用户输入，不含参考文档标记。"""
    import app.orchestrator.intent as mod

    captured = {}

    class FakeProvider:
        async def chat(self, messages, **kw):
            captured["user_text"] = messages[-1].content
            return '{"missing": []}'

    monkeypatch.setattr(mod, "extract_json", lambda s: json.loads(s))

    asyncio.run(
        mod.parse_intent(FakeProvider(), "100平会议室方案",
                         known={"scene": "会议室"})
    )
    assert "参考文档" not in captured["user_text"]
    assert "已确认信息" in captured["user_text"]
