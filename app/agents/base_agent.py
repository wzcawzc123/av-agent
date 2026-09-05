"""Agent 生命周期基类：analyze（前置检查）→ execute（核心执行）→ validate（产出校验）。

具体 Agent 只需覆写需要的生命周期方法；name/description 用于注册与工作流日志。
depends_on 声明步骤级依赖（由 Workflow 层在计划层面判定，Agent 自身不做）。
"""


class BaseAgent:
    name: str = "base"
    description: str = ""
    depends_on: list[str] = []

    async def analyze(self, context) -> None:
        """执行前检查与数据准备；前置条件不满足时抛异常终止本步骤。默认无操作。"""
        return None

    async def execute(self, context) -> None:
        """核心执行逻辑：产出写入 context.outputs/files/bom 等共享状态。"""
        raise NotImplementedError

    async def validate(self, context) -> bool:
        """执行后校验产出是否完整；返回 False 由 Workflow 层记为失败。默认通过。"""
        return True
