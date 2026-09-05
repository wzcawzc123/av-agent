"""Agent 注册表单测：6 个具体 Agent 自动注册 + BaseAgent 生命周期默认行为。"""
import pytest

import app.agents  # noqa: F401  包导入触发具体 Agent 模块自动注册
from app.agents.base_agent import BaseAgent
from app.agents.registry import AGENT_REGISTRY, get_agent, list_agents, register

EXPECTED_AGENTS = [
    "requirement_analysis",
    "product_selection",
    "solution_design",
    "bom_generation",
    "quotation",
    "document_generation",
]


def test_registry_contains_six_agents():
    assert set(EXPECTED_AGENTS) <= set(AGENT_REGISTRY)


def test_list_agents_returns_names():
    names = list_agents()
    assert isinstance(names, list)
    assert set(EXPECTED_AGENTS) <= set(names)


def test_get_agent_returns_instance():
    agent = get_agent("requirement_analysis")
    assert isinstance(agent, BaseAgent)
    assert agent.name == "requirement_analysis"


def test_get_agent_unknown_raises_keyerror_with_available():
    with pytest.raises(KeyError) as ei:
        get_agent("no_such_agent")
    msg = " ".join(str(a) for a in ei.value.args)
    assert "no_such_agent" in msg
    assert "requirement_analysis" in msg  # 错误信息带可用 Agent 列表


def test_register_custom_agent():
    class MyAgent(BaseAgent):
        name = "my_agent"
        description = "测试自定义 Agent"

    register("my_agent", MyAgent)
    try:
        assert "my_agent" in AGENT_REGISTRY
        got = get_agent("my_agent")
        assert got.name == "my_agent"
        assert isinstance(got, MyAgent)
    finally:
        AGENT_REGISTRY.pop("my_agent", None)


def test_base_agent_defaults():
    agent = BaseAgent()
    assert agent.name == "base"
    assert agent.description == ""
    assert agent.depends_on == []


@pytest.mark.asyncio
async def test_base_agent_lifecycle_defaults():
    agent = BaseAgent()
    assert await agent.analyze({}) is None  # 默认 pass
    assert await agent.validate({}) is True
    with pytest.raises(NotImplementedError):
        await agent.execute({})
