from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import require_token
from app.llm.registry import save_model_config, load_model_config

router = APIRouter(prefix="/api", dependencies=[Depends(require_token)])


class ModelConfigIn(BaseModel):
    provider: str
    api_key: str = ""
    model: str = ""
    base_url: str = ""


@router.get("/settings/model")
def get_model_config():
    return load_model_config()


@router.put("/settings/model")
def put_model_config(body: ModelConfigIn):
    cfg = {"provider": body.provider, "api_key": body.api_key,
           "model": body.model, "base_url": body.base_url}
    save_model_config(cfg)
    return {"ok": True}
