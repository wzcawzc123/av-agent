"""招标改单 API：上传解析 → 匹配 → 精修 → 快照 → 确认转 BOM。"""
from __future__ import annotations

import os
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import func

from app.api.deps import require_token
from app.config import settings
from app.db.session import get_session
from app.db.models import TenderMatch
from app.engines.tender.parser import parse_file
from app.engines.tender.matcher import match_items
from app.engines.tender.coverage import detect_merge
from app.engines.tender.llm_pick import refine_rows, flag_extras
from app.engines.tender.store import save_snapshot, load_rows, to_bom_rows

router = APIRouter(prefix="/api/tender", dependencies=[Depends(require_token)])


class RowEditIn(BaseModel):
    brand: str = ""
    model: str = ""
    status: str = ""
    remark: str = ""
    preference: str = ""


class ConfirmIn(BaseModel):
    project_id: int
    snapshot: str = ""


@router.post("/upload")
def upload_tender(
    file: UploadFile = File(...),
    project_id: int = Form(0),
):
    """上传招标文件，解析→匹配→精修→存快照，返回匹配行。"""
    ext = os.path.splitext(file.filename or "file.xlsx")[1].lower()
    if ext not in (".xlsx", ".xlsm", ".docx", ".pdf"):
        raise HTTPException(status_code=400, detail=f"不支持的文件类型：{ext}")

    # 保存临时文件
    tmp_name = f"{uuid.uuid4().hex}{ext}"
    tmp_path = os.path.join(settings.UPLOAD_DIR, tmp_name)
    with open(tmp_path, "wb") as f:
        f.write(file.file.read())

    try:
        items = parse_file(tmp_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"文件解析失败：{e}")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    if not items:
        raise HTTPException(status_code=400, detail="未从文件中识别到设备需求行")

    # 匹配
    with get_session() as s:
        rows = match_items(items, s)
        n = detect_merge(rows, s)
        refine_rows(rows, llm_enabled=True)
        flag_extras(rows, llm_enabled=True)
        snapshot = save_snapshot(s, project_id, rows)
        s.commit()
        return {
            "ok": True,
            "project_id": project_id,
            "snapshot": snapshot,
            "items": [r.to_dict() for r in rows],
            "merged": n,
        }


@router.get("/{project_id}/snapshots")
def list_snapshots(project_id: int):
    """快照列表。"""
    with get_session() as s:
        snaps = (
            s.query(TenderMatch.snapshot, func.count(TenderMatch.id))
            .filter_by(project_id=project_id)
            .group_by(TenderMatch.snapshot)
            .all()
        )
        return {
            "ok": True,
            "snapshots": [
                {"snapshot": sn, "rows": cnt} for sn, cnt in snaps
            ],
        }


@router.get("/{project_id}/snapshots/{snapshot}")
def get_snapshot(project_id: int, snapshot: str):
    """读取快照匹配行。"""
    with get_session() as s:
        rows = load_rows(s, project_id, snapshot)
        return {
            "ok": True,
            "project_id": project_id,
            "snapshot": snapshot,
            "rows": [r.to_dict() for r in rows],
        }


@router.put("/{project_id}/rows/{source_idx}")
def edit_row(project_id: int, source_idx: int, body: RowEditIn):
    """编辑单行（品牌/型号/状态/备注/偏好）。"""
    with get_session() as s:
        from app.engines.tender.store import update_row

        rows = load_rows(s, project_id, snapshot="")
        if not rows:
            raise HTTPException(status_code=404, detail="未找到匹配行")
        # 取最新快照
        row = (
            s.query(TenderMatch)
            .filter_by(project_id=project_id, source_idx=source_idx)
            .order_by(TenderMatch.id.desc())
            .first()
        )
        if not row:
            raise HTTPException(status_code=404, detail="行不存在")
        if body.brand:
            row.brand = body.brand
        if body.model:
            row.model = body.model
        if body.status:
            row.status = body.status
        if body.remark:
            row.remark = body.remark
        if body.preference:
            row.preference = body.preference
        s.commit()
        return {"ok": True}


@router.post("/{project_id}/confirm")
def confirm_tender(project_id: int, body: ConfirmIn):
    """确认改单，生成 BOM 行。"""
    with get_session() as s:
        rows = load_rows(s, project_id, body.snapshot)
        if not rows:
            raise HTTPException(status_code=404, detail="未找到匹配行")
        bom = to_bom_rows(rows)
        return {"ok": True, "project_id": project_id, "rows": bom}