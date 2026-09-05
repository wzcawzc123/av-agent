"""Planner 单测：计划步骤结构 / depends_on / JSON 序列化（纯确定性，不调 LLM）。"""
import json

from app.planner.planner import Plan, PlanStep, Planner

FULL_ORDER = [
    "requirement_analysis",
    "product_selection",
    "solution_design",
    "bom_generation",
    "quotation",
    "document_generation",
]


def _names(plan: Plan) -> list[str]:
    return [s.name for s in plan.steps]


def _depends_on(plan: Plan, name: str) -> list[str]:
    return next(s for s in plan.steps if s.name == name).depends_on


def test_plan_step_defaults():
    s = PlanStep(name="requirement_analysis", agent="requirement_analysis")
    assert s.params == {}
    assert s.depends_on == []


def test_create_plan_always_has_basic_steps():
    for deliverables in ([], ["doc"], ["excel"], ["ppt"], ["doc", "excel", "ppt"]):
        p = Planner.create_plan({}, deliverables)
        names = _names(p)
        assert names[0] == "requirement_analysis"
        assert names[1] == "product_selection"
        # step.name 与 step.agent 均为注册名
        assert all(s.name == s.agent for s in p.steps)
        assert all(s.name in FULL_ORDER for s in p.steps)


def test_create_plan_doc_adds_solution_design():
    p = Planner.create_plan({}, ["doc"])
    names = _names(p)
    assert "solution_design" in names
    assert _depends_on(p, "solution_design") == ["product_selection"]
    assert "bom_generation" not in names
    assert "quotation" not in names
    assert "document_generation" not in names


def test_create_plan_excel_adds_bom_and_quotation():
    p = Planner.create_plan({}, ["excel"])
    names = _names(p)
    assert "bom_generation" in names
    assert _depends_on(p, "bom_generation") == ["product_selection"]
    assert "quotation" in names
    assert _depends_on(p, "quotation") == ["bom_generation"]
    assert names.index("bom_generation") < names.index("quotation")
    assert "solution_design" not in names
    assert "document_generation" not in names


def test_create_plan_empty_deliverables_defaults_to_excel():
    p = Planner.create_plan({}, [])
    names = _names(p)
    assert "bom_generation" in names
    assert "quotation" in names


def test_create_plan_ppt_doc_gen_depends_on_solution():
    p = Planner.create_plan({}, ["ppt"])
    names = _names(p)
    assert "solution_design" in names
    assert "document_generation" in names
    assert _depends_on(p, "document_generation") == ["solution_design"]
    assert "bom_generation" not in names


def test_create_plan_pdf_excel_doc_gen_depends_on_bom():
    p = Planner.create_plan({}, ["pdf", "excel"])
    names = _names(p)
    assert "solution_design" not in names
    assert "document_generation" in names
    assert _depends_on(p, "document_generation") == ["bom_generation"]


def test_create_plan_full_set_order():
    p = Planner.create_plan({}, ["doc", "excel", "ppt", "pdf", "deviation"])
    assert _names(p) == FULL_ORDER
    assert _depends_on(p, "document_generation") == ["solution_design"]


def test_plan_json_roundtrip():
    p = Planner.create_plan({"scene": "会议室", "area": 100}, ["doc", "excel"])
    raw = json.loads(p.to_json())
    assert isinstance(raw, dict) and "steps" in raw
    p2 = Plan.from_json(p.to_json())
    assert isinstance(p2, Plan)
    assert p2.steps == p.steps
    assert all(isinstance(s, PlanStep) for s in p2.steps)
    # 序列化往返后 depends_on 仍保留
    assert _depends_on(p2, "quotation") == ["bom_generation"]
