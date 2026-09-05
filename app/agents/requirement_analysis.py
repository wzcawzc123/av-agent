"""需求分析 Agent：规范化槽位（默认值/席位/信号源/显示端），并按场景推断系统集合。"""
from app.agents.base_agent import BaseAgent
from app.agents.registry import register
from app.engines.systems.scene import (
    infer_systems,
    resolve_displays,
    resolve_seats,
    resolve_signal_sources,
)

_SYSTEM_CN = {
    "prosound": "专业扩声", "speech": "会议发言", "display": "显示系统",
    "paperless": "无纸化会议", "control": "中控矩阵", "distributed": "分布式",
    "lighting": "灯光系统", "broadcast": "公共广播", "videoconf": "视频会议",
}


class RequirementAnalysisAgent(BaseAgent):
    name = "requirement_analysis"
    description = "规范化需求槽位并推断系统集合"

    async def analyze(self, context) -> None:
        if not isinstance(context.slots, dict):
            raise ValueError("需求槽位缺失（context.slots 必须为 dict）")
        if context.session is None:
            raise ValueError("缺少数据库会话（context.session）")

    async def execute(self, context) -> None:
        slots = dict(context.slots)
        # 项目记忆：读取历史上下文，未明确的槽位从记忆回填（与 product_selection 的写入闭环）
        memory = {}
        try:
            from app.db.memory import recall

            memory = recall(context.session, context.project_id) or {}
            for k in ("brand", "config_level", "scene", "budget", "area"):
                if not slots.get(k):
                    v = memory.get(k)
                    if v not in (None, "", "无"):
                        slots[k] = v
        except Exception:
            memory = {}
        # 兜底默认值：config_level / brand / budget
        slots.setdefault("config_level", "中配")
        slots.setdefault("brand", slots.get("brand") or "无")
        slots.setdefault("budget", slots.get("budget") or "不限")
        # 系统集合：显式 systems 优先，否则按场景推断
        if not slots.get("systems"):
            slots["systems"] = infer_systems(slots)
        # 结构槽位：席位 / 信号源 / 显示端
        if not slots.get("seats"):
            slots["seats"] = resolve_seats(slots)
        if not slots.get("signal_sources"):
            slots["signal_sources"] = resolve_signal_sources(slots)
        if not slots.get("display_count"):
            slots["display_count"] = resolve_displays(slots)
        # 交付物：槽位未给时取 cfg 默认（excel）
        if not slots.get("deliverables"):
            slots["deliverables"] = context.cfg.get("deliverables") or ["excel"]
        context.slots.update(slots)
        systems = slots["systems"]
        context.outputs[self.name] = {
            "scene": slots.get("scene") or "",
            "area": slots.get("area") or 0,
            "systems": systems,
            "systems_name": [_SYSTEM_CN.get(s, s) for s in systems],
            "seats": slots["seats"],
            "config_level": slots["config_level"],
            "brand": slots.get("brand") or "",
            "deliverables": slots.get("deliverables"),
            "memory_recalled": bool(memory),
        }

    async def validate(self, context) -> bool:
        out = context.outputs.get(self.name)
        return bool(out and out.get("systems"))


register(RequirementAnalysisAgent.name, RequirementAnalysisAgent)
