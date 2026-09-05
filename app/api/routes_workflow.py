import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import require_token
from app.db.models import AgentExecutionLog, Organization, Project, WorkflowRun
from app.db.session import get_session
from app.tasks.queue import submit_task

router = APIRouter(prefix="/api", dependencies=[Depends(require_token)])


class WorkflowRunIn(BaseModel):
    project_id: int
    deliverables: list[str] | None = None


def _load(s: str, fallback: object):
    try:
        return json.loads(s or "")
    except Exception:
        return fallback


@router.post("/workflow/runs")
async def create_workflow_run(body: WorkflowRunIn):
    """新建工作流运行：从 Project.requirement_json 恢复槽位，提交到后台任务队列。"""
    from app.config import settings

    with get_session() as s:
        p = s.query(Project).filter_by(id=body.project_id).first()
        if not p:
            raise HTTPException(status_code=404, detail="项目不存在")
        slots = _load(p.requirement_json, {})
        run = WorkflowRun(project_id=p.id, plan_json="[]", status="pending")
        s.add(run)
        s.flush()
        run_id = run.id
    deliverables = body.deliverables or ["excel"]
    cfg = {
        "deliverables": deliverables,
        "project_dir": f"{settings.OUTPUT_DIR}/proj_{body.project_id}",
        "run_id": run_id,
    }
    task_id = submit_task(body.project_id, cfg, slots)
    return {"run_id": run_id, "task_id": task_id}


@router.get("/workflow/runs")
def list_workflow_runs():
    with get_session() as s:
        rows = s.query(WorkflowRun).order_by(WorkflowRun.id.desc()).limit(100).all()
        return [{"id": r.id, "project_id": r.project_id, "status": r.status,
                 "progress": r.progress, "error": r.error,
                 "created_at": r.created_at.isoformat() if r.created_at else None,
                 "finished_at": r.finished_at.isoformat() if r.finished_at else None}
                for r in rows]


@router.get("/workflow/runs/{run_id}")
def get_workflow_run(run_id: int):
    with get_session() as s:
        r = s.query(WorkflowRun).filter_by(id=run_id).first()
        if not r:
            raise HTTPException(status_code=404, detail="运行记录不存在")
        return {"id": r.id, "project_id": r.project_id, "status": r.status,
                "progress": r.progress, "error": r.error,
                "plan": _load(r.plan_json, []), "result": _load(r.result_json, {}),
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "finished_at": r.finished_at.isoformat() if r.finished_at else None}


@router.get("/workflow/runs/{run_id}/logs")
def workflow_run_logs(run_id: int):
    with get_session() as s:
        rows = s.query(AgentExecutionLog).filter_by(run_id=run_id) \
            .order_by(AgentExecutionLog.id).all()
        return [{"id": l.id, "step": l.step, "agent_name": l.agent_name,
                 "status": l.status, "error": l.error,
                 "detail": _load(l.detail_json, {}),
                 "started_at": l.started_at.isoformat() if l.started_at else None,
                 "finished_at": l.finished_at.isoformat() if l.finished_at else None}
                for l in rows]


# ---- 企业组织 ----

class OrgIn(BaseModel):
    name: str
    code: str
    contact: str = ""


@router.get("/organizations")
def list_organizations():
    with get_session() as s:
        rows = s.query(Organization).order_by(Organization.id).all()
        return [{"id": o.id, "name": o.name, "code": o.code, "contact": o.contact}
                for o in rows]


@router.post("/organizations")
def create_organization(body: OrgIn):
    with get_session() as s:
        if s.query(Organization).filter_by(code=body.code).first():
            raise HTTPException(status_code=400, detail="组织编码已存在")
        o = Organization(name=body.name, code=body.code, contact=body.contact)
        s.add(o)
        s.flush()
        return {"id": o.id, "name": o.name, "code": o.code, "contact": o.contact}


# ---- 企业用户 ----

class UserIn(BaseModel):
    org_id: int | None = None
    name: str
    role: str = ""
    username: str | None = None


@router.get("/users")
def list_users():
    from app.db.models import User

    with get_session() as s:
        rows = s.query(User).order_by(User.id).all()
        return [{"id": u.id, "org_id": u.org_id, "name": u.name, "role": u.role,
                 "username": u.username} for u in rows]


@router.post("/users")
def create_user(body: UserIn):
    from app.db.models import User

    with get_session() as s:
        if body.username and s.query(User).filter_by(username=body.username).first():
            raise HTTPException(status_code=400, detail="用户名已存在")
        if body.org_id and not s.query(Organization).filter_by(id=body.org_id).first():
            raise HTTPException(status_code=400, detail="组织不存在")
        u = User(org_id=body.org_id, name=body.name, role=body.role, username=body.username)
        s.add(u)
        s.flush()
        return {"id": u.id, "org_id": u.org_id, "name": u.name, "role": u.role,
                "username": u.username}


# ---- 知识库 ----

class KnowledgeIn(BaseModel):
    title: str
    doc_type: str = ""
    file_path: str = ""
    excerpt: str = ""
    meta: dict = {}


@router.get("/knowledge")
def list_knowledge():
    from app.knowledge.retriever import list_documents

    with get_session() as s:
        return {"documents": list_documents(s)}


@router.post("/knowledge")
def create_knowledge(body: KnowledgeIn):
    from app.knowledge.retriever import register_document

    with get_session() as s:
        doc_id = register_document(s, body.title, body.doc_type, body.file_path,
                                   body.excerpt, body.meta)
        return {"id": doc_id}


@router.delete("/knowledge/{doc_id}")
def delete_knowledge(doc_id: int):
    from app.knowledge.retriever import delete_document

    with get_session() as s:
        if not delete_document(s, doc_id):
            raise HTTPException(status_code=404, detail="文档不存在")
        return {"ok": True}
