import os
import shutil

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.api.deps import require_token
from app.db.session import get_session
from app.db.models import Product, Template
from app.db.product_importer import import_products
from app.db.template_store import save_template

router = APIRouter(prefix="/api", dependencies=[Depends(require_token)])


@router.get("/products")
def list_products():
    with get_session() as s:
        rows = s.query(Product).order_by(Product.id.desc()).limit(500).all()
        return [{"id": p.id, "name": p.name, "model": p.model,
                 "category": p.category, "base_price": p.base_price,
                 "market_price": p.market_price} for p in rows]


@router.post("/products")
async def upload_products(file: UploadFile = File(...)):
    from app.config import settings

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    dest = os.path.join(settings.UPLOAD_DIR, file.filename or "products.xlsx")
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    with get_session() as s:
        result = import_products(dest, s)
    return result


@router.get("/templates")
def list_templates():
    with get_session() as s:
        rows = s.query(Template).order_by(Template.id.desc()).limit(200).all()
        return [{"id": t.id, "name": t.name, "type": t.type,
                 "description": t.description, "file_path": t.file_path} for t in rows]


class TemplateIn(BaseModel):
    name: str
    type: str
    file_path: str
    description: str = ""


@router.post("/templates")
def create_template(body: TemplateIn):
    with get_session() as s:
        t = save_template(s, body.name, body.type, body.file_path, body.description)
        return {"id": t.id}


@router.delete("/templates/{template_id}")
def delete_template(template_id: int):
    with get_session() as s:
        t = s.query(Template).filter_by(id=template_id).first()
        if not t:
            raise HTTPException(status_code=404, detail="模板不存在")
        s.delete(t)
    return {"ok": True}
