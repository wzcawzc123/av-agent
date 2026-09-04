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




class RebuildIn(BaseModel):
    rows: list = []       # BOM 行（system/type/spec/brand/model/qty/unit/price/note）
    deliverables: list = ["excel"]  # 仅支持 ["excel"]：编辑清单后重出报价表


@router.get("/projects/{project_id}/bom")
def get_project_bom(project_id: int):
    """读取项目 BOM 行：优先数据库快照，空则从最新 xlsx 解析回填。"""
    import json as _json
    from app.config import settings
    from app.generators.excel_generator import parse_design_sheet

    with get_session() as s:
        p = s.query(Project).filter_by(id=project_id).first()
        if not p:
            raise HTTPException(status_code=404, detail="项目不存在")
        try:
            bom = _json.loads(p.bom_json or "{}")
        except Exception:
            bom = {}
        if isinstance(bom, list) and bom:
            return {"id": project_id, "rows": bom}
    project_dir = os.path.join(settings.OUTPUT_DIR, f"proj_{project_id}")
    xlsx = os.path.join(project_dir, "设计方案清单.xlsx")
    if os.path.isfile(xlsx):
        return {"id": project_id, "rows": parse_design_sheet(xlsx)}
    return {"id": project_id, "rows": []}


@router.post("/projects/{project_id}/rebuild")
def rebuild_project_excel(project_id: int, body: RebuildIn):
    """编辑 BOM 后跳过 LLM 直接重出 Excel 报价表（设计方案清单_v2.xlsx）。"""
    import json as _json
    from app.config import settings
    from app.generators.excel_generator import build_design_sheet

    rows = [r for r in body.rows if isinstance(r, dict) and (r.get("type") or r.get("model"))]
    if not rows:
        raise HTTPException(status_code=400, detail="清单为空，无法生成")
    # 统一 BOM 行格式：前端 price -> 生成器 market_price
    for r in rows:
        r.setdefault("qty", 1)
        r.setdefault("unit", "台")
        r.setdefault("note", "")
        r.setdefault("category", "主要设备")
        r["market_price"] = float(r.get("market_price") or r.get("price") or 0)
        r["base_price"] = float(r.get("base_price") or 0)
    with get_session() as s:
        p = s.query(Project).filter_by(id=project_id).first()
        if not p:
            raise HTTPException(status_code=404, detail="项目不存在")
        try:
            req = _json.loads(p.requirement_json or "{}")
        except Exception:
            req = {}
        p.bom_json = _json.dumps(rows, ensure_ascii=False)
        scene = req.get("scene") or p.name
    project_dir = os.path.join(settings.OUTPUT_DIR, f"proj_{project_id}")
    os.makedirs(project_dir, exist_ok=True)
    out = os.path.join(project_dir, "设计方案清单_v2.xlsx")
    build_design_sheet(out, {"项目名称": scene}, rows)
    return {"files": {"excel": out}, "rows": len(rows)}

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
