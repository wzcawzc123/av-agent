"""BOM 生成 Agent：把设备清单落成设计方案清单 Excel，并回写 Project.bom_json。"""
import json
import os
from datetime import date

from app.agents.base_agent import BaseAgent
from app.agents.registry import register


class BomGenerationAgent(BaseAgent):
    name = "bom_generation"
    description = "生成设计方案清单 Excel 并持久化 BOM"

    async def analyze(self, context) -> None:
        if not context.bom:
            raise ValueError("设备清单为空，无法生成 BOM（需先执行 product_selection）")
        if context.session is None:
            raise ValueError("缺少数据库会话（context.session）")

    async def execute(self, context) -> None:
        from app.db.models import Project
        from app.generators.excel_generator import build_design_sheet

        slots = context.slots
        project_dir = context.cfg.get("project_dir") or ""
        if not project_dir:
            from app.config import settings
            project_dir = f"{settings.OUTPUT_DIR}/proj_{context.project_id}"
        os.makedirs(project_dir, exist_ok=True)
        tpl_paths = dict(context.cfg.get("template_paths") or {})
        out = os.path.join(project_dir, "设计方案清单.xlsx")
        build_design_sheet(
            out,
            {"项目名称": slots.get("scene") or "音视频方案",
             "方案日期": date.today().isoformat()},
            context.bom,
            tpl_paths.get("excel"),
        )
        context.files["excel"] = out
        # 持久化 BOM 到项目（工作流结束后 queue 层也会回写 result["bom"]，此处先落库）
        p = context.session.get(Project, context.project_id)
        if p is not None:
            p.bom_json = json.dumps(context.bom, ensure_ascii=False)
        context.outputs[self.name] = {"file": out, "device_count": len(context.bom)}

    async def validate(self, context) -> bool:
        return bool(context.files.get("excel"))


register(BomGenerationAgent.name, BomGenerationAgent)
