"""记忆注入测试：跨会话记忆独立注入，不受参考文档 top-3 截断影响。"""

import pytest

from app.orchestrator.intent import parse_intent


class _CapturingProvider:
    """记录每次 chat 的 user 消息内容，便于断言注入。"""

    def __init__(self):
        self.last_user = ""
        self.chat_calls = 0

    async def chat(self, messages, temperature=0.7):
        self.chat_calls += 1
        self.last_user = messages[-1].content
        return '{"area": 100, "scene": "会议室", "budget": "5万", "brand": "惠威", "deliverables": ["doc"]}'


@pytest.mark.asyncio
async def test_memory_note_injected():
    provider = _CapturingProvider()
    await parse_intent(provider, "客户说预算收紧", memory_note="客户偏好惠威，预算通常 5-10 万")
    assert "【跨会话记忆】" in provider.last_user
    assert "客户偏好惠威" in provider.last_user


@pytest.mark.asyncio
async def test_memory_note_optional():
    provider = _CapturingProvider()
    await parse_intent(provider, "100平会议室方案")
    assert "【跨会话记忆】" not in provider.last_user


@pytest.mark.asyncio
async def test_memory_not_crowded_out_by_docs():
    """回归：记忆必须与参考文档共存，而不是被 docs 顶掉。"""
    docs = [{"title": f"文档{i}", "excerpt": f"内容{i}"} for i in range(1, 6)]  # 5 条 > top-3
    provider = _CapturingProvider()
    await parse_intent(provider, "查资料", context_docs=docs, memory_note="记忆：客户偏好MAXHUB")
    # 记忆存在
    assert "记忆：客户偏好MAXHUB" in provider.last_user
    # 参考文档只取前 3 条
    assert "文档1" in provider.last_user and "文档3" in provider.last_user
    assert "文档5" not in provider.last_user
    # 记忆在文档之前（优先级更高）
    assert provider.last_user.index("【跨会话记忆】") < provider.last_user.index("【参考文档】")
