"""企业数据模型单测：Organization/User/KnowledgeDocument/Solution/Quotation/
WorkflowRun/AgentExecutionLog CRUD + Project 扩展列 + Project Memory（remember/recall 合并）。"""
import json

import pytest

from app.db.memory import recall, remember
from app.db.models import (AgentExecutionLog, Base, KnowledgeDocument, Organization,
                           Project, Quotation, Solution, User, WorkflowRun)
from app.db.session import get_engine, get_session


@pytest.fixture()
def db(tmp_path):
    engine = get_engine(f"sqlite:///{tmp_path / 'ent.db'}")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


def test_organization_user_crud(db):
    with get_session(db) as s:
        org = Organization(name="示例公司", code="DEMO", contact="张三")
        s.add(org)
        s.flush()
        s.add(User(org_id=org.id, name="李四", role="sales", username="lisi"))
    with get_session(db) as s:
        org = s.query(Organization).filter_by(code="DEMO").first()
        assert org is not None and org.name == "示例公司" and org.contact == "张三"
        user = s.query(User).filter_by(username="lisi").first()
        assert user is not None and user.name == "李四" and user.role == "sales"
        assert user.org_id == org.id
        # 删除（外键为可空关联，SQLite 不强制级联）
        s.delete(org)
    with get_session(db) as s:
        assert s.query(Organization).count() == 0
        assert s.query(User).filter_by(username="lisi").count() == 1


def test_project_memory_columns(db):
    with get_session(db) as s:
        p = Project(name="企业项目", customer_name="客户A", memory_json="{}")
        s.add(p)
        s.flush()
        pid = p.id
    with get_session(db) as s:
        p = s.query(Project).filter_by(id=pid).first()
        assert p.customer_name == "客户A"
        assert p.org_id is None
        assert json.loads(p.memory_json) == {}


def test_memory_remember_merges_and_recall(db):
    with get_session(db) as s:
        p = Project(name="记忆项目")
        s.add(p)
        s.flush()
        pid = p.id
    with get_session(db) as s:
        remember(s, pid, "brand", "惠威")
        remember(s, pid, "scene", "会议室")
    with get_session(db) as s:
        m = recall(s, pid)
        assert m == {"brand": "惠威", "scene": "会议室"}
        assert recall(s, pid, "brand") == "惠威"
        assert recall(s, pid, "missing") is None
    # 同 key 覆盖不丢其它 key
    with get_session(db) as s:
        remember(s, pid, "brand", "MAXHUB")
    with get_session(db) as s:
        assert recall(s, pid) == {"brand": "MAXHUB", "scene": "会议室"}


def test_memory_recall_no_memory(db):
    with get_session(db) as s:
        p = Project(name="无记忆项目")
        s.add(p)
        s.flush()
        pid = p.id
    with get_session(db) as s:
        assert recall(s, pid) == {}


def test_enterprise_entity_crud(db):
    with get_session(db) as s:
        p = Project(name="实体项目")
        s.add(p)
        s.flush()
        pid = p.id
        s.add(Solution(project_id=pid, title="方案A",
                       content_json='{"body": "正文"}', file_paths_json='["/tmp/a.docx"]',
                       status="draft"))
        s.add(Quotation(project_id=pid, total_amount=12345.5,
                        items_json='[{"name": "音箱", "qty": 2, "price": 6000}]',
                        status="draft"))
        s.add(KnowledgeDocument(title="音箱选型手册", doc_type="manual",
                                file_path="/tmp/manual.pdf", excerpt="8寸音箱参数",
                                meta_json='{"brand": "惠威"}'))
        s.add(WorkflowRun(project_id=pid, plan_json="[]", status="success", progress=100))
    with get_session(db) as s:
        sol = s.query(Solution).filter_by(project_id=pid).first()
        assert sol is not None and sol.title == "方案A" and sol.status == "draft"
        assert json.loads(sol.file_paths_json) == ["/tmp/a.docx"]
        quo = s.query(Quotation).filter_by(project_id=pid).first()
        assert quo.total_amount == 12345.5
        assert json.loads(quo.items_json)[0]["name"] == "音箱"
        doc = s.query(KnowledgeDocument).filter_by(doc_type="manual").first()
        assert doc.title == "音箱选型手册"
        assert json.loads(doc.meta_json)["brand"] == "惠威"
        run = s.query(WorkflowRun).filter_by(project_id=pid).first()
        assert run.status == "success" and run.progress == 100
        # 引用同一次运行的 Agent 执行日志
        s.add(AgentExecutionLog(run_id=run.id, project_id=pid, step="product_selection",
                                agent_name="product_selection", status="success",
                                detail_json='{"rows": 3}'))
    with get_session(db) as s:
        run = s.query(WorkflowRun).filter_by(project_id=pid).first()
        logs = s.query(AgentExecutionLog).filter_by(run_id=run.id).all()
        assert len(logs) == 1
        assert logs[0].agent_name == "product_selection"
        assert logs[0].status == "success"
