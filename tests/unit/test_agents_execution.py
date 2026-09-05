"""Agent 接线行为测试：Solution 落库 + RAG 注入（solution_design）、项目记忆回填（requirement_analysis）。"""
import json
import os

import pytest

from app.db.models import Base, KnowledgeDocument, Project, Solution
from app.db.session import get_engine, get_session
from app.workflow.workflow import WorkflowContext


class FakeProvider:
    """记录最后一次 user 消息，返回固定方案正文。"""

    name = "fake"

    def __init__(self):
        self.last_user = ""

    async def chat(self, messages, temperature=0.5):
        self.last_user = messages[-1].content
        return "# 测试方案\n\n正文内容"


@pytest.fixture()
def db(tmp_path):
    engine = get_engine(f"sqlite:///{tmp_path / 'agents.db'}")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.mark.asyncio
async def test_solution_design_writes_solution_and_injects_rag(db, tmp_path):
    """solution_design：检索知识库并把命中文档注入 LLM prompt，同时落 Solution 记录。"""
    from app.agents.registry import get_agent

    with get_session(db) as s:
        s.add(KnowledgeDocument(title="会议室部署规范", doc_type="faq",
                                excerpt="会议室音箱部署需覆盖全场"))
        p = Project(name="方案测试", requirement_json="{}")
        s.add(p)
        s.flush()
        pid = p.id

    provider = FakeProvider()
    with get_session(db) as s:
        ctx = WorkflowContext(
            project_id=pid,
            slots={"area": 100, "scene": "会议室", "brand": "测试牌"},
            cfg={"deliverables": ["doc"], "project_dir": str(tmp_path)},
            session=s,
            provider=provider,
        )
        agent = get_agent("solution_design")
        await agent.analyze(ctx)
        await agent.execute(ctx)
        assert ctx.files.get("doc") and os.path.exists(ctx.files["doc"])
        assert ctx.outputs["solution_design"]["knowledge_refs"] == 1
        sol = s.query(Solution).filter_by(project_id=pid).first()
        assert sol is not None
        assert sol.status == "generated"
        assert json.loads(sol.file_paths_json) == [ctx.files["doc"]]

    # RAG 检索结果真实注入 LLM prompt，不是摆设
    assert "会议室部署规范" in provider.last_user


@pytest.mark.asyncio
async def test_requirement_analysis_recalls_project_memory(db):
    """requirement_analysis：读取 Project 记忆回填未明确槽位，记忆读写闭环。"""
    from app.agents.registry import get_agent

    with get_session(db) as s:
        p = Project(name="记忆测试", requirement_json="{}",
                    memory_json=json.dumps({"brand": "惠威", "config_level": "高配"}))
        s.add(p)
        s.flush()
        pid = p.id

    with get_session(db) as s:
        ctx = WorkflowContext(
            project_id=pid,
            slots={"area": 100, "scene": "会议室"},
            cfg={"deliverables": ["excel"]},
            session=s,
        )
        agent = get_agent("requirement_analysis")
        await agent.analyze(ctx)
        await agent.execute(ctx)
        assert ctx.slots["brand"] == "惠威"  # 从记忆回填
        assert ctx.slots["config_level"] == "高配"
        assert ctx.slots["deliverables"] == ["excel"]  # 无记忆字段仍走 cfg 默认
        assert ctx.outputs["requirement_analysis"]["memory_recalled"] is True
