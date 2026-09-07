"""产品选型 Agent：匹配常规配置模板 + 编排完整设备清单（主设备+配件辅材），写入共享 BOM 与项目记忆。"""

from app.agents.base_agent import BaseAgent
from app.agents.registry import register


class ProductSelectionAgent(BaseAgent):
    name = "product_selection"
    description = "匹配配置模板并编排设备清单"

    async def analyze(self, context) -> None:
        if not isinstance(context.slots, dict) or not context.slots.get("systems"):
            raise ValueError("需求槽位未规范化（缺少 systems），需先执行 requirement_analysis")
        if context.session is None:
            raise ValueError("缺少数据库会话（context.session）")

    async def execute(self, context) -> None:
        from app.db.memory import remember
        from app.db.template_store import find_config_template
        from app.engines.composer import compose_devices

        slots = context.slots
        session = context.session
        tpl = find_config_template(
            session,
            area=int(float(slots.get("area") or 0)),
            scene=slots.get("scene") or "",
            systems=slots.get("systems") or [],
            config_level=slots.get("config_level") or "",
            brand=slots.get("brand") or "",
        )
        devices = await compose_devices(context.provider, slots, session, tpl)
        context.bom = devices or []
        # 项目记忆：设备规模与系统构成（供后续步骤/会话复用）
        try:
            remember(session, context.project_id, "device_count", len(context.bom))
            remember(session, context.project_id, "system_list", slots.get("systems") or [])
        except Exception:
            pass  # 记忆写入失败不阻塞选型
        context.outputs[self.name] = {
            "device_count": len(context.bom),
            "main_count": sum(1 for d in context.bom if d.get("category") == "主设备"),
            "template_id": tpl.id if tpl else None,
            "template_name": tpl.name if tpl else None,
        }

    async def validate(self, context) -> bool:
        return bool(context.bom)


register(ProductSelectionAgent.name, ProductSelectionAgent)
