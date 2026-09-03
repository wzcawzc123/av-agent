from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import require_token
from app.db.session import get_session
from app.db.models import Project

router = APIRouter(prefix="/api", dependencies=[Depends(require_token)])


class ProjectIn(BaseModel):
    name: str = "未命名项目"
    requirement_json: str = "{}"


@router.get("/projects")
def list_projects():
    with get_session() as s:
        rows = s.query(Project).order_by(Project.id.desc()).limit(100).all()
        return [{"id": p.id, "name": p.name, "status": p.status,
                 "requirement_json": p.requirement_json} for p in rows]


@router.post("/projects")
def create_project(body: ProjectIn):
    with get_session() as s:
        p = Project(name=body.name, requirement_json=body.requirement_json)
        s.add(p)
        s.flush()
        pid = p.id
    return {"id": pid, "name": body.name}


@router.get("/projects/{project_id}")
def get_project(project_id: int):
    with get_session() as s:
        p = s.query(Project).filter_by(id=project_id).first()
        if not p:
            return {"error": "项目不存在"}
        return {"id": p.id, "name": p.name, "status": p.status,
                "requirement_json": p.requirement_json}
