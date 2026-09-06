import os
import json
import shutil
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import or_
from pydantic import BaseModel

from app.api.deps import require_token
from app.db.session import get_session
from app.db.models import Product, Template, ConfigTemplate
from app.db.product_importer import import_products

MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 上传统一上限 20MB
from app.db.template_store import save_template, save_config_template, find_doc_template

router = APIRouter(prefix="/api", dependencies=[Depends(require_token)])




class ProductPriceIn(BaseModel):
    base_price: float = 0
    market_price: float = 0


@router.post("/products/{product_id}/price")
def update_product_price(product_id: int, body: ProductPriceIn):
    """更新单条产品价格（前端产品库"改价"）。"""
    with get_session() as s:
        p = s.query(Product).filter_by(id=product_id).first()
        if not p:
            raise HTTPException(status_code=404, detail="产品不存在")
        p.base_price = body.base_price
        p.market_price = body.market_price
    return {"ok": True, "id": product_id}

@router.get("/products")
def list_products(q: str = "", brand: str = "", category: str = ""):
    with get_session() as s:
        query = s.query(Product)
        if q:
            like = f"%{q}%"
            query = query.filter(or_(Product.name.like(like),
                                     Product.model.like(like),
                                     Product.brand.like(like)))
        if brand:
            query = query.filter(Product.brand == brand)
        if category:
            query = query.filter(Product.category == category)
        rows = query.order_by(Product.id.desc()).limit(1000).all()
        return [{"id": p.id, "name": p.name, "model": p.model,
                 "category": p.category, "brand": p.brand,
                 "description": p.description,
                 "base_price": p.base_price,
                 "market_price": p.market_price} for p in rows]


@router.delete("/products/{product_id}")
def delete_product(product_id: int):
    with get_session() as s:
        p = s.query(Product).filter_by(id=product_id).first()
        if not p:
            raise HTTPException(status_code=404, detail="产品不存在")
        s.delete(p)
    return {"ok": True}


@router.post("/products")
async def upload_products(file: UploadFile = File(...)):
    from app.config import settings

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    # 安全：客户端文件名只做展示，落盘固定名（防路径遍历），历史文件保留
    dest = os.path.join(settings.UPLOAD_DIR,
                        f"products_{uuid.uuid4().hex[:8]}{os.path.splitext(file.filename or '')[1].lower() or '.xlsx'}")
    size = 0
    with open(dest, "wb") as f:
        while chunk := file.file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                f.close()
                os.remove(dest)
                raise HTTPException(status_code=413, detail="文件过大（上限 20MB）")
            f.write(chunk)
    with get_session() as s:
        result = import_products(dest, s)
    return result


@router.get("/templates")
def list_templates():
    with get_session() as s:
        rows = s.query(Template).order_by(Template.id.desc()).limit(200).all()
        items = []
        for t in rows:
            meta = {}
            try:
                meta = json.loads(t.meta_json or "{}") or {}
            except Exception:
                pass
            items.append({"id": t.id, "name": t.name, "type": t.type,
                          "description": t.description, "file_path": t.file_path,
                          "area": None, "scene": meta.get("scene", ""),
                          "brand": meta.get("brand", ""),
                          "systems": meta.get("systems", [])})
        ct = s.query(ConfigTemplate).order_by(ConfigTemplate.id.desc()).limit(100).all()
        items += [{"id": c.id, "name": c.name, "type": "config",
                   "description": f"面积 {c.area}㎡", "file_path": "",
                   "area": c.area, "scene": c.scene,
                   "brand": c.brand, "systems": c.systems,
                   "config_level": c.config_level} for c in ct]
        return items


class TemplateIn(BaseModel):
    name: str
    type: str
    file_path: str = ""
    description: str = ""
    area: int = 0
    scene: str = ""
    systems: list = []
    config_level: str = ""
    brand: str = ""




@router.post("/templates/upload")
async def upload_template(file: UploadFile = File(...),
                          name: str = Form(""),
                          type: str = Form("doc"),
                          scene: str = Form(""),
                          brand: str = Form(""),
                          systems: str = Form("[]"),
                          description: str = Form("")):
    """上传 doc/ppt/deviation 模板文件：存 UPLOAD_DIR/templates，按 场景×品牌 参与自动选型。"""
    from app.config import settings
    if type not in ("doc", "ppt", "deviation"):
        raise HTTPException(status_code=400, detail="仅支持 doc/ppt/deviation 模板上传")
    ext = os.path.splitext(file.filename or "")[1].lower()
    allowed = {".docx", ".doc", ".pptx", ".ppt", ".xlsx", ".xls"} if type == "deviation"         else ({".docx", ".doc"} if type == "doc" else {".pptx", ".ppt"})
    if ext not in allowed:
        raise HTTPException(status_code=400,
                            detail="仅支持 " + "/".join(sorted(allowed)) + " 文件")
    tdir = os.path.join(settings.UPLOAD_DIR, "templates")
    os.makedirs(tdir, exist_ok=True)
    base = "".join(ch for ch in (name or "模板") if ch not in '\\/:*?"<>|').strip() or "模板"
    dest = os.path.join(tdir, f"{base}{ext}")
    n = 1
    while os.path.exists(dest):
        dest = os.path.join(tdir, f"{base}_{n}{ext}")
        n += 1
    size = 0
    with open(dest, "wb") as f:
        while chunk := file.file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                f.close()
                os.remove(dest)
                raise HTTPException(status_code=413, detail="文件过大（上限 20MB）")
            f.write(chunk)
    try:
        systems_list = json.loads(systems or "[]")
        if not isinstance(systems_list, list):
            systems_list = []
    except Exception:
        systems_list = []
    with get_session() as s:
        t = save_template(s, name or os.path.basename(dest), type, dest,
                          description, meta={"scene": scene, "brand": brand,
                                             "systems": systems_list})
        return {"id": t.id, "file_path": dest, "name": t.name, "type": type}

@router.post("/templates")
def create_template(body: TemplateIn):
    with get_session() as s:
        if body.type == "config":
            c = save_config_template(s, body.name, body.area, body.scene, {},
                                     systems=body.systems,
                                     config_level=body.config_level,
                                     brand=body.brand)
            return {"id": c.id}
        meta = {"scene": body.scene, "brand": body.brand, "systems": body.systems}
        t = save_template(s, body.name, body.type, body.file_path,
                          body.description, meta=meta)
        return {"id": t.id}


@router.delete("/templates/{template_id}")
def delete_template(template_id: int, type: str = "doc"):
    with get_session() as s:
        if type == "config":
            c = s.query(ConfigTemplate).filter_by(id=template_id).first()
            if not c:
                raise HTTPException(status_code=404, detail="模板不存在")
            s.delete(c)
        else:
            t = s.query(Template).filter_by(id=template_id).first()
            if not t:
                raise HTTPException(status_code=404, detail="模板不存在")
            s.delete(t)
    return {"ok": True}


class BomTemplateIn(BaseModel):
    name: str
    scene: str = ""
    area: int = 0
    systems: list = []
    config_level: str = ""
    brand: str = ""
    rows: list = []  # BOM 行（含 system/type/spec/brand/model/qty/unit/note）


@router.post("/templates/from-bom")
def create_template_from_bom(body: BomTemplateIn):
    """把可编辑 BOM 清单回存为常规配置模板（config_template）。"""
    with get_session() as s:
        c = save_config_template(s, body.name, body.area, body.scene,
                                 {"rows": body.rows}, systems=body.systems,
                                 config_level=body.config_level, brand=body.brand)
        return {"id": c.id}


@router.get("/templates/{template_id}/bom")
def get_template_bom(template_id: int, type: str = "config"):
    """读取配置模板的 BOM 行（应用模板时前端载入）。"""
    with get_session() as s:
        if type != "config":
            raise HTTPException(status_code=400, detail="仅 config 模板支持 BOM")
        c = s.query(ConfigTemplate).filter_by(id=template_id).first()
        if not c:
            raise HTTPException(status_code=404, detail="模板不存在")
        try:
            cfg = json.loads(c.config_json or "{}")
        except Exception:
            cfg = {}
        return {"id": c.id, "name": c.name, "area": c.area, "scene": c.scene,
                "systems": c.systems, "config_level": c.config_level,
                "brand": c.brand, "rows": cfg.get("rows", [])}


@router.get("/templates/doc-match")
def match_doc_template(scene: str = "", brand: str = ""):
    """按 场景×品牌 匹配 doc/ppt 模板；返回 file_path 或空（用默认模板）。"""
    with get_session() as s:
        t = find_doc_template(s, scene, brand)
        if not t:
            return {"template_id": None, "file_path": None, "type": None}
        return {"template_id": t.id, "file_path": t.file_path, "type": t.type}
