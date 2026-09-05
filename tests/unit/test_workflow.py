"""SalesWorkflow 单测：假 Agent（继承 BaseAgent）跑通 run，WorkflowRun/AgentExecutionLog 落库与返回结构。"""
import json

import pytest

from app.agents.base_agent import BaseAgent
from app.agents.registry import register
from app.db.models import AgentExecutionLog, Base, Project, WorkflowRun
from app.db.session import get_engine, get_session
from app.planner.planner import Plan, PlanStep
from app.workflow.workflow import SalesWorkflow, WorkflowContext


class StubAgent(BaseAgent):
    """写入 outputs / files 的假 Agent。"""

    name = "stub"
    description = "测试用假 Agent"
    marker = "stub"

    async def analyze(self, context):
        context.outputs[self.name] = {"analyzed": True}

    async def execute(self, context):
        context.outputs[self.name]["done"] = True
        context.files[self.marker] = f"/tmp/{self.marker}.docx"

    async def validate(self, context):
        return True


class StubAgentB(StubAgent):
    name = "stub_b"
    marker = "doc"


class BoomAgent(BaseAgent):
    """execute 抛异常的假 Agent。"""

    name = "boom"

    async def execute(self, context):
        raise RuntimeError("boom!")


@pytest.fixture()
def db(tmp_path):
    engine = get_engine(f"sqlite:///{tmp_path / 'wf.db'}")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture(autouse=True)
def _register_stubs():
    register("stub", StubAgent)
    register("stub_b", StubAgentB)
    register("boom", BoomAgent)


def _new_project(engine) -> int:
    with get_session(engine) as s:
        p = Project(name="工作流测试项目",
                    requirement_json=json.dumps({"area": 100, "scene": "会议室"}))
        s.add(p)
        s.flush()
        return p.id


def _plan(*steps: PlanStep) -> Plan:
    return Plan(steps=list(steps))


@pytest.mark.asyncio
async def test_run_success_persists_run_and_logs(db):
    project_id = _new_project(db)
    plan = _plan(
        PlanStep(name="stub", agent="stub"),
        PlanStep(name="stub_b", agent="stub_b", depends_on=["stub"]),
    )
    with get_session(db) as s:
        ctx = WorkflowContext(
            project_id=project_id,
            slots={"area": 100, "scene": "会议室"},
            cfg={},
            session=s,
            provider=None,
            plan=plan,
        )
        progress = []
        result = await SalesWorkflow.run(ctx, progress_cb=lambda p, m: progress.append((p, m)))

    # 返回结构与现有 generate_deliverables 一致
    assert set(result) == {"files", "errors", "bom"}
    assert result["files"].get("doc") == "/tmp/doc.docx"
    assert result["errors"] == {}
    assert result["bom"] == []

    # 进度 0 → 100，单调不减
    assert progress and progress[0][0] == 0 and progress[-1][0] == 100
    assert all(isinstance(p, int) and 0 <= p <= 100 for p, _ in progress)
    assert all(a <= b for a, b in zip([p for p, _ in progress], [p for p, _ in progress][1:]))

    # run_id 回写 cfg
    assert ctx.cfg.get("run_id") is not None

    with get_session(db) as s:
        run = s.query(WorkflowRun).filter_by(project_id=project_id).first()
        assert run is not None
        assert run.status == "success"
        assert run.progress == 100
        assert run.plan_json == plan.to_json()
        result_json = json.loads(run.result_json or "{}")
        assert result_json.get("files", {}).get("doc") == "/tmp/doc.docx"

        logs = {lg.step: lg for lg in s.query(AgentExecutionLog)
                .filter_by(run_id=run.id).all()}
        assert set(logs) == {"stub", "stub_b"}
        assert all(lg.status == "success" for lg in logs.values())
        assert logs["stub_b"].agent_name == "stub_b"


@pytest.mark.asyncio
async def test_run_uses_cfg_run_id(db):
    project_id = _new_project(db)
    with get_session(db) as s:
        run = WorkflowRun(project_id=project_id, status="pending", plan_json="[]")
        s.add(run)
        s.flush()
        run_id = run.id
    with get_session(db) as s:
        cfg = {"run_id": run_id}
        ctx = WorkflowContext(project_id=project_id, slots={}, cfg=cfg, session=s,
                              plan=_plan(PlanStep(name="stub", agent="stub")))
        await SalesWorkflow.run(ctx)
        assert ctx.cfg["run_id"] == run_id
    with get_session(db) as s:
        runs = s.query(WorkflowRun).filter_by(project_id=project_id).all()
        assert len(runs) == 1
        assert runs[0].id == run_id
        assert runs[0].status == "success"


@pytest.mark.asyncio
async def test_run_skips_missing_dependency(db):
    project_id = _new_project(db)
    plan = _plan(
        PlanStep(name="stub", agent="stub"),
        PlanStep(name="stub_b", agent="stub_b", depends_on=["ghost_step"]),
    )
    with get_session(db) as s:
        ctx = WorkflowContext(project_id=project_id, slots={}, cfg={}, session=s, plan=plan)
        result = await SalesWorkflow.run(ctx)
    assert result["errors"] == {}
    assert "doc" not in result["files"]  # stub_b 未执行
    with get_session(db) as s:
        run = s.query(WorkflowRun).filter_by(project_id=project_id).order_by(WorkflowRun.id.desc()).first()
        logs = {lg.step: lg for lg in s.query(AgentExecutionLog)
                .filter_by(run_id=run.id).all()}
        assert logs["stub"].status == "success"
        assert logs["stub_b"].status == "skipped"
        assert logs["stub_b"].error == ""


@pytest.mark.asyncio
async def test_run_step_error_is_isolated(db):
    project_id = _new_project(db)
    plan = _plan(
        PlanStep(name="stub", agent="stub"),
        PlanStep(name="boom", agent="boom", depends_on=["stub"]),
    )
    with get_session(db) as s:
        ctx = WorkflowContext(project_id=project_id, slots={}, cfg={}, session=s, plan=plan)
        result = await SalesWorkflow.run(ctx)
    # 失败步骤写 errors，后续无步骤可继续，run 仍正常结束
    assert result["errors"] == {"boom": "boom!"}
    assert result["files"].get("stub") == "/tmp/stub.docx"
    with get_session(db) as s:
        run = s.query(WorkflowRun).filter_by(project_id=project_id).order_by(WorkflowRun.id.desc()).first()
        assert run.status == "failed"
        logs = {lg.step: lg for lg in s.query(AgentExecutionLog)
                .filter_by(run_id=run.id).all()}
        assert logs["stub"].status == "success"
        assert logs["boom"].status == "failed"
        assert logs["boom"].error == "boom!"
        result_json = json.loads(run.result_json or "{}")
        assert result_json.get("errors") == {"boom": "boom!"}
