"""LLM 智能入库路由：上传文件 → LLM 识别类型 → 自动入库。

- POST /api/ingest         multipart 上传（桌面/手机通用）
- POST /api/ingest/local   本机文件路径（桌面端 Agent 工具 av_ingest 用）
"""

from __future__ import annotations

import os
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.api.deps import require_token
from app.config import settings
from app.db.session import get_session
from app.ingest.classifier import (
    classify_document,
    extract_knowledge,
    extract_products,
)
from app.ingest.extractor import extract_text
from app.ingest.ingestor import ingest_knowledge, ingest_products, summarize
from app.llm.registry import load_model_config, get_provider

router = APIRouter(prefix="/api", dependencies=[Depends(require_token)])

SUPPORTED_EXT = (".xlsx", ".xlsm", ".xls", ".docx", ".pdf", ".txt", ".md", ".csv")
TARGETS = ("products", "knowledge", "auto")


class LocalIngestIn(BaseModel):
    path: str
    target: str = "auto"


async def _get_provider():
    cfg = load_model_config()
    if not cfg.get("provider") or not cfg.get("api_key"):
        return None, "尚未配置模型。请先到「模型提供商」页选择提供商并填写 API Key。"
    p = get_provider(cfg)
    if hasattr(p, "__await__"):
        p = await p
    return p, ""


async def _ingest(provider, file_path: str, filename: str, target: str = "auto") -> dict:
    text = extract_text(file_path)
    if not text or text.startswith("（") or text.startswith("!"):
        return {"ok": False, "message": text or "文件内容为空，无法解析"}

    # 目标未指定 → LLM 分类
    if target not in ("products", "knowledge"):
        cls = await classify_document(provider, text, filename)
        ftype = cls.get("type", "other")
        target = ftype if ftype in ("products", "knowledge") else "auto"
        title = cls.get("title") or filename
        summary = cls.get("summary") or ""
    else:
        title, summary = filename, ""

    if target == "products":
        items = await extract_products(provider, text)
        if not items:
            return {"ok": False, "message": "未从文件中识别到产品行（可能是知识文档？可指定 target=knowledge 重试）",
                    "type": "products", "preview": []}
        import uuid as _uuid

        batch = f"ingest-{_uuid.uuid4().hex[:10]}"
        with get_session() as s:
            added, skipped, warns = ingest_products(s, items, batch_id=batch,
                                                    source_file=filename)
        msg = summarize("products", added, skipped)
        if warns:
            msg += f"\n⚠ 校验告警 {len(warns)} 条（如 底价高于单价）：" + "；".join(warns[:3])
        return {"ok": True, "type": "products", "title": title, "summary": summary,
                "message": msg, "added": added, "skipped": skipped, "warns": warns[:5],
                "batch_id": batch, "preview": items[:5]}

    if target == "knowledge":
        doc = await extract_knowledge(provider, text, filename)
        if doc is None:
            return {"ok": False, "message": "未能从文件中提炼知识要点", "type": "knowledge"}
        with get_session() as s:
            doc_id = ingest_knowledge(s, doc)
        skipped = 1 if doc_id == 0 else 0
        return {"ok": True, "type": "knowledge", "title": doc["title"], "summary": doc["excerpt"][:200],
                "message": summarize("knowledge", 1 if doc_id else 0, skipped, doc_id),
                "added": 1 if doc_id else 0, "skipped": skipped, "preview": doc}

    return {"ok": False, "message": "未能判断文件类型（支持：产品清单 / 知识文档）。可指定 target 重试。",
            "type": "other"}


@router.post("/ingest")
async def ingest_upload(file: UploadFile = File(...), target: str = Form("auto")):
    if target not in TARGETS:
        raise HTTPException(status_code=400, detail="target 仅支持 products/knowledge/auto")
    ext = os.path.splitext(file.filename or "file.xlsx")[1].lower()
    if ext not in SUPPORTED_EXT:
        raise HTTPException(status_code=400,
                            detail=f"不支持的文件类型 {ext}（支持：Excel/Word/PDF/文本）")
    provider, err = await _get_provider()
    if provider is None:
        return {"ok": False, "need_config": True, "message": err}
    tmp_path = os.path.join(settings.UPLOAD_DIR, f"ingest_{uuid.uuid4().hex[:8]}{ext}")
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    with open(tmp_path, "wb") as f:
        f.write(await file.read())
    try:
        return await _ingest(provider, tmp_path, file.filename or "文件", target)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@router.post("/ingest/local")
async def ingest_local(body: LocalIngestIn):
    """桌面端本机路径直接入库（Agent 工具 av_ingest 使用）。"""
    if body.target not in TARGETS:
        raise HTTPException(status_code=400, detail="target 仅支持 products/knowledge/auto")
    path = os.path.abspath(body.path)
    if not os.path.isfile(path):
        raise HTTPException(status_code=400, detail=f"文件不存在：{path}")
    provider, err = await _get_provider()
    if provider is None:
        return {"ok": False, "need_config": True, "message": err}
    return await _ingest(provider, path, os.path.basename(path), body.target)
