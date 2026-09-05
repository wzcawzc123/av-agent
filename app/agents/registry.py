"""Agent 注册表：name → Agent 类，模块 import 时自动注册（文件底部导入具体 Agent 触发）。"""
from app.agents.base_agent import BaseAgent

AGENT_REGISTRY: dict[str, type[BaseAgent]] = {}


def register(name: str, cls: type[BaseAgent]) -> None:
    AGENT_REGISTRY[name] = cls


def get_agent(name: str) -> BaseAgent:
    """按注册名返回 Agent 实例；未知名字抛 KeyError 并附带可用列表。"""
    if name not in AGENT_REGISTRY:
        raise KeyError(f"未知 Agent: {name}（可用: {list_agents()}）")
    return AGENT_REGISTRY[name]()


def list_agents() -> list[str]:
    return sorted(AGENT_REGISTRY)


# 具体 Agent 模块导入即自动注册（依赖其底部 register 调用）
from app.agents import (  # noqa: E402
    bom_generation,
    document_generation,
    product_selection,
    quotation,
    requirement_analysis,
    solution_design,
)
