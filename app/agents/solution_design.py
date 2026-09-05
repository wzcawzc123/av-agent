"""方案设计 Agent：按品牌×场景选 Word 模板，LLM 生成方案正文；无模型时确定性降级填充。"""
import os

from app.agents.base_agent import BaseAgent
from app.agents.registry import register

_SYSTEM_CN = {
    "prosound": "专业扩声", "speech": "会议发言", "display": "显示系统",
    "paperless": "无纸化会议", "control": "中控矩阵", "distributed": "分布式",
    "lighting": "灯光系统", "broadcast": "公共广播", "videoconf": "视频会议",
}


def _fallback_overview(slots: dict) -> str:
    name = slots.get("scene") or "音视频"
    parts = [f"{name}项目"]
    if slots.get("area"):
        parts.append(f"面积约{slots['area']}㎡")
    if slots.get("seats"):
        s = slots["seats"]
        parts.append(f"共{s.get('chairman', 0) + s.get('delegate', 0)}个发言席位")
    if slots.get("systems"):
        parts.append("涵盖系统：" + "、".join(_SYSTEM_CN.get(x, str(x)) for x in slots["systems"]))
    if slots.get("brand"):
        parts.append(f"品牌要求：{slots['brand']}")
    return "；".join(parts) + "。"


def _fallback_body(slots: dict, devices: list[dict]) -> str:
    """无 LLM 时的确定性方案正文：按系统分组罗列设备与项目概况。"""
    lines = [f"# {slots.get('scene') or '音视频'}项目设计方案", "",
             "## 一、项目概况", _fallback_overview(slots), "",
             "## 二、系统设计"]
    by_system: dict[str, list[dict]] = {}
    for d in devices:
        by_system.setdefault(d.get("system") or "", []).append(d)
    for code, devs in by_system.items():
        lines.append(f"### {_SYSTEM_CN.get(code, code)}")
        for d in devs:
            spec = d.get("spec") or ""
            lines.append(f"- {d.get('type', '')} {spec} × {d.get('qty', 1)}{d.get('unit', '')}"
                         f"（{d.get('brand', '')} {d.get('model', '')}）")
        lines.append("")
    lines += ["## 三、设备清单说明",
              f"本项目共配置 {len(devices)} 项设备（详见设计方案清单 Excel）。",
              "",
              "## 四、施工与布线建议",
              "- 设备安装前完成现场勘查，确认承重、供电与信号线路由；",
              "- 音频线缆与强电保持间距，信号线屏蔽层单端接地；",
              "- 机柜内设备预留散热与理线空间，粘贴标签便于维护。",
              "",
              "## 五、售后服务",
              "- 提供设备调试与操作培训，质保期内免费上门服务；",
              "- 7×24 小时响应，常用备件本地储备。",
              ""]
    return "\n".join(lines)


class SolutionDesignAgent(BaseAgent):
    name = "solution_design"
    description = "生成 Word 方案文档"

    async def analyze(self, context) -> None:
        if "doc" not in (context.cfg.get("deliverables") or []):
            self._active = False  # 仅在 deliverables 含 doc 时执行（计划侧已限定，此处双保险）
            return
        if context.session is None:
            raise ValueError("缺少数据库会话（context.session）")
        self._active = True

    async def execute(self, context) -> None:
        if not getattr(self, "_active", True):
            return
        from app.db.template_store import find_doc_template
        from app.generators.word_generator import build_doc_from_llm, fill_docx_template

        slots = context.slots
        project_dir = context.cfg.get("project_dir") or ""
        if not project_dir:
            from app.config import settings
            project_dir = f"{settings.OUTPUT_DIR}/proj_{context.project_id}"
        os.makedirs(project_dir, exist_ok=True)
        tpl_paths = dict(context.cfg.get("template_paths") or {})
        doc_tpl = find_doc_template(session=context.session, scene=slots.get("scene") or "",
                                    brand=slots.get("brand") or "")
        if doc_tpl:
            tpl_paths.setdefault(doc_tpl.type, doc_tpl.file_path)
        out = os.path.join(project_dir, "方案.docx")
        devices = context.bom or []
        mode = "llm"
        if context.provider is None:
            # 无模型可用：确定性填充方案正文，不阻塞流程
            fill_docx_template(
                tpl_paths.get("doc"),
                {"项目名称": slots.get("scene") or "音视频方案",
                 "项目概述": _fallback_overview(slots),
                 "方案正文": _fallback_body(slots, devices)},
                out,
            )
            mode = "fallback"
        else:
            await build_doc_from_llm(context.provider, slots, devices, tpl_paths.get("doc"), out)
        context.files["doc"] = out
        context.outputs[self.name] = {"file": out, "mode": mode, "device_count": len(devices)}

    async def validate(self, context) -> bool:
        if not getattr(self, "_active", True):
            return True
        return bool(context.files.get("doc"))


register(SolutionDesignAgent.name, SolutionDesignAgent)
