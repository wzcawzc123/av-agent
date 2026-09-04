import os

from fastapi import APIRouter, Depends, HTTPException
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


@router.get("/projects/{project_id}/files")
def list_project_files(project_id: int):
    """列出项目产出目录中的文件（doc/ppt/excel/pdf），供前端项目页下载。"""
    from app.config import settings
    from app.db.session import get_session as gs
    from app.db.models import Project as P

    with gs() as s:
        p = s.query(P).filter_by(id=project_id).first()
        name = p.name if p else f"项目 {project_id}"
    project_dir = os.path.join(settings.OUTPUT_DIR, f"proj_{project_id}")
    files = []
    if os.path.isdir(project_dir):
        kind_map = {".docx": "doc", ".doc": "doc", ".xlsx": "excel", ".xls": "excel",
                    ".pptx": "ppt", ".pdf": "pdf"}
        for fn in sorted(os.listdir(project_dir)):
            ext = os.path.splitext(fn)[1].lower()
            if ext in kind_map:
                files.append({"name": fn, "kind": kind_map[ext],
                              "path": os.path.join(project_dir, fn)})
    return {"id": project_id, "name": name, "files": files}


@router.delete("/projects/{project_id}")
def delete_project(project_id: int):
    from app.config import settings
    import shutil

    with get_session() as s:
        p = s.query(Project).filter_by(id=project_id).first()
        if not p:
            raise HTTPException(status_code=404, detail="项目不存在")
        s.delete(p)
    project_dir = os.path.join(settings.OUTPUT_DIR, f"proj_{project_id}")
    if os.path.isdir(project_dir):
        shutil.rmtree(project_dir, ignore_errors=True)
    return {"ok": True}
