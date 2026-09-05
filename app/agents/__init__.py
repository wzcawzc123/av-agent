"""AV-Agent v3.0 Agent Runtime：生命周期基类 + 注册表 + 6 个具体 Agent。

导入本包即完成全部 Agent 注册（模块 import 时自动注册）。
"""
from app.agents.base_agent import BaseAgent
from app.agents.registry import AGENT_REGISTRY, get_agent, list_agents, register

__all__ = ["BaseAgent", "AGENT_REGISTRY", "get_agent", "list_agents", "register"]
