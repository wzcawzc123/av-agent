from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import require_token
from app.llm import provider_store
from app.llm.registry import (
    save_model_config,
    load_model_config,
    get_provider,
    resolve_credentials,
    all_providers,
)

router = APIRouter(prefix="/api", dependencies=[Depends(require_token)])


# ---------- 模型配置（当前选择） ----------

class ModelConfigIn(BaseModel):
    provider: str
    api_key: str = ""
    model: str = ""
    base_url: str = ""


@router.get("/settings/model")
def get_model_config():
    from app.llm.provider_store import mask_api_key

    cfg = load_model_config()
    if cfg.get("api_key"):
        cfg = dict(cfg)
        cfg["api_key"] = mask_api_key(cfg["api_key"])
        cfg["has_api_key"] = True
    return cfg


@router.put("/settings/model")
async def put_model_config(body: ModelConfigIn):
    resolved = resolve_credentials(body.model_dump())
    # 前端回填的掩码值（含 ******）视为未修改，保留原 key
    submitted_key = "" if "******" in (body.api_key or "") else body.api_key
    cfg = {"provider": resolved["provider"], "api_key": submitted_key or resolved["api_key"],
           "model": body.model or resolved["model"], "base_url": body.base_url or resolved["base_url"]}
    # 同步 api_key / base_url 到该提供商记录
    provider_store.update_provider(resolved["provider"], api_key=cfg["api_key"], base_url=cfg["base_url"])
    save_model_config(cfg)
    return {"ok": True}


# ---------- 提供商管理（内置 + 自定义） ----------

class ModelIn(BaseModel):
    model_id: str
    display_name: str = ""
    owned_by: str = ""
    context_window: int | None = None


class ProviderIn(BaseModel):
    name: str
    base_url: str = ""
    api_key: str = ""
    provider_type: str = "openai_compatible"  # openai_compatible | anthropic | gemini
    endpoint_mode: str = "chat_completions"
    models: list[ModelIn] = []


@router.get("/providers")
def list_providers():
    return [p.public_dict() for p in all_providers()]


@router.post("/providers")
def create_provider(body: ProviderIn):
    if not body.name.strip():
        raise HTTPException(status_code=400, detail="提供商名称不能为空")
    provider = provider_store.ProviderSetting(
        id=provider_store.new_provider_id(),
        name=body.name.strip(),
        base_url=body.base_url.strip(),
        api_key=body.api_key.strip(),
        provider_type=body.provider_type if body.provider_type in provider_store.PROVIDER_TYPES else "openai_compatible",
        endpoint_mode=body.endpoint_mode if body.endpoint_mode in provider_store.ENDPOINT_MODES else "chat_completions",
        models=[provider_store.Model(
            id=f"m-{i}", model_id=m.model_id, display_name=m.display_name,
            owned_by=m.owned_by, context_window=m.context_window, sort_order=i,
        ) for i, m in enumerate(body.models)],
    )
    return provider_store.add_provider(provider).public_dict()


@router.put("/providers/{provider_id}")
def update_provider(provider_id: str, body: ProviderIn):
    existing = provider_store.get_provider_by_id(provider_id)
    if not existing:
        raise HTTPException(status_code=404, detail="提供商不存在")
    fields = {"name": body.name.strip() or existing.name,
              "base_url": body.base_url.strip() or existing.base_url,
              "api_key": body.api_key.strip() or existing.api_key,
              "provider_type": body.provider_type if body.provider_type in provider_store.PROVIDER_TYPES else "openai_compatible",
              "endpoint_mode": body.endpoint_mode if body.endpoint_mode in provider_store.ENDPOINT_MODES else "chat_completions"}
    if body.models:
        fields["models"] = [{"id": f"m-{i}", "model_id": m.model_id, "display_name": m.display_name,
                             "owned_by": m.owned_by, "context_window": m.context_window,
                             "sort_order": i, "is_enabled": True} for i, m in enumerate(body.models)]
    p = provider_store.update_provider(provider_id, **fields)
    return p.public_dict()


@router.delete("/providers/{provider_id}")
def delete_provider(provider_id: str):
    if not provider_store.delete_provider(provider_id):
        raise HTTPException(status_code=400, detail="内置提供商不可删除或不存在")
    return {"ok": True}


@router.post("/providers/{provider_id}/copy")
def copy_provider(provider_id: str):
    p = provider_store.copy_provider(provider_id)
    if not p:
        raise HTTPException(status_code=404, detail="提供商不存在")
    return p.public_dict()


@router.post("/providers/{provider_id}/reset")
def reset_provider(provider_id: str):
    p = provider_store.reset_builtin(provider_id)
    if not p:
        raise HTTPException(status_code=404, detail="非内置提供商无需重置")
    return p.public_dict()


@router.post("/providers/{provider_id}/fetch-models")
async def fetch_provider_models(provider_id: str):
    """从提供商远程拉取模型列表（GET /models），失败时保留本地。"""
    p = provider_store.get_provider_by_id(provider_id)
    if not p:
        raise HTTPException(status_code=404, detail="提供商不存在")
    fetched = await provider_store.fetch_remote_models(p)
    if not fetched:
        raise HTTPException(status_code=502, detail="远程拉取模型失败（请检查 API Key 与 Base URL）")
    return {"fetched": [f.model_id for f in fetched]}


@router.post("/providers/{provider_id}/test")
async def test_provider(provider_id: str):
    """发送最小请求验证连接（1 个 token）。"""
    p = provider_store.get_provider_by_id(provider_id)
    if not p:
        raise HTTPException(status_code=404, detail="提供商不存在")
    model_id = p.default_model_id()
    if not model_id:
        raise HTTPException(status_code=400, detail="该提供商没有可用模型")
    try:
        from app.llm.base import ChatMessage
        provider = await get_provider({"provider": provider_id, "model": model_id})
        await provider.chat([ChatMessage(role="user", content="ping")], temperature=0)
        return {"ok": True, "model": model_id}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"连接失败：{type(e).__name__}: {e}")


# ---------- 软件更新（GitHub Releases） ----------

import json as _json
from pathlib import Path as _Path

import httpx as _httpx

from app.version import VERSION as LOCAL_VERSION, DEFAULT_CHECK_URL, is_newer
from app.config import settings as _settings

_UPDATE_CFG_PATH = _Path(_settings.base_dir) / "data" / "update.json"


def _load_update_cfg() -> dict:
    try:
        return _json.loads(_UPDATE_CFG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"check_url": DEFAULT_CHECK_URL, "token": ""}


def _save_update_cfg(cfg: dict):
    _UPDATE_CFG_PATH.parent.mkdir(parents=True, exist_ok=True)
    _UPDATE_CFG_PATH.write_text(_json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


class UpdateConfigIn(BaseModel):
    check_url: str = ""
    token: str = ""


@router.get("/update/config")
def get_update_config():
    cfg = _load_update_cfg()
    return {"check_url": cfg.get("check_url") or DEFAULT_CHECK_URL, "has_token": bool(cfg.get("token"))}


@router.put("/update/config")
def put_update_config(body: UpdateConfigIn):
    cfg = _load_update_cfg()
    if body.check_url.strip():
        cfg["check_url"] = body.check_url.strip()
    if body.token:
        cfg["token"] = body.token.strip()
    elif body.token == "" and "token" in body.model_dump():
        # 显式传空字符串表示清除 token
        cfg["token"] = ""
    _save_update_cfg(cfg)
    return {"ok": True}


@router.get("/update/check")
async def check_update():
    """检查 GitHub Releases 是否有新版本。私有仓库需配置 token。"""
    cfg = _load_update_cfg()
    url = cfg.get("check_url") or DEFAULT_CHECK_URL
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "AVAgent-Updater"}
    if cfg.get("token"):
        headers["Authorization"] = f"Bearer {cfg['token']}"
    try:
        async with _httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"检查更新失败：{type(e).__name__}: {e}")

    latest = (data.get("tag_name") or "").lstrip("v") or data.get("name") or ""
    assets = data.get("assets") or []
    exe_asset = next((a for a in assets if (a.get("name") or "").lower().endswith(".exe")), None)
    return {
        "current_version": LOCAL_VERSION,
        "latest_version": latest,
        "has_update": bool(latest) and is_newer(latest, LOCAL_VERSION),
        "notes": (data.get("body") or "")[:2000],
        "download_url": exe_asset.get("browser_download_url") if exe_asset else data.get("html_url", ""),
        "published_at": data.get("published_at"),
    }
