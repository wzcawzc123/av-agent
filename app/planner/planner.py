"""Planner：把确认后的需求拆成确定性计划步骤（纯逻辑，不调 LLM）。

步骤与 Agent 一一对应（name == agent 均为注册名）：
requirement_analysis → product_selection → solution_design → bom_generation → quotation → document_generation
"""
import json
from dataclasses import dataclass, field


@dataclass
class PlanStep:
    name: str
    agent: str
    params: dict = field(default_factory=dict)
    depends_on: list = field(default_factory=list)


@dataclass
class Plan:
    steps: list = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps({"steps": [s.__dict__ for s in self.steps]}, ensure_ascii=False)

    @classmethod
    def from_json(cls, s: str) -> "Plan":
        data = json.loads(s or "{}")
        if isinstance(data, dict):
            data = data.get("steps", [])
        return cls(steps=[PlanStep(**item) for item in data])


class Planner:
    @staticmethod
    def create_plan(requirement: dict, deliverables: list[str]) -> Plan:
        deliverables = deliverables or []
        steps = [
            PlanStep(name="requirement_analysis", agent="requirement_analysis"),
            PlanStep(name="product_selection", agent="product_selection"),
        ]
        if "doc" in deliverables or "ppt" in deliverables:
            steps.append(PlanStep(name="solution_design", agent="solution_design",
                                  depends_on=["product_selection"]))
        if "excel" in deliverables or not deliverables:
            steps.append(PlanStep(name="bom_generation", agent="bom_generation",
                                  depends_on=["product_selection"]))
            steps.append(PlanStep(name="quotation", agent="quotation",
                                  depends_on=["bom_generation"]))
        if any(d in deliverables for d in ("ppt", "pdf", "deviation")):
            # 依赖只指向计划中实际存在的步骤，避免文档生成被跳过
            if "doc" in deliverables or "ppt" in deliverables:
                dep = ["solution_design"]
            elif "excel" in deliverables or not deliverables:
                dep = ["bom_generation"]
            else:
                dep = ["product_selection"]
            steps.append(PlanStep(name="document_generation", agent="document_generation",
                                  depends_on=dep))
        return Plan(steps=steps)
