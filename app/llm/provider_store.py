"""模型提供商存储：内置 + 用户自定义，参考 ETA-2 的 Provider 体系。

设计（对齐 ETA-2 BuiltinProviders / ProviderSourceRegistry / ProviderRepository）：
- 内置提供商带官方模型目录，启动时自动合并进 providers.json；
- 用户可新增/复制/编辑/删除自定义提供商（内置不可删）；
- 每个提供商可远程拉取模型列表（GET /models），也可手动增删模型；
- 当前选择（provider + model）单独存 model.json。
"""
from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from typing import Optional

# ---------- 常量 ----------

PROVIDER_TYPES = {"openai_compatible": "openai_compatible", "anthropic": "anthropic", "gemini": "gemini"}
ENDPOINT_MODES = {"chat_completions": "chat_completions", "responses": "responses"}

# source_type（来源注册表，对应 ETA-2 ProviderSourceTypes）
SOURCE_CUSTOM = "custom"
KNOWN_SOURCE_TYPES = {
    "openai", "anthropic", "qwen", "deepseek", "moonshot", "mimo",
    "minimax", "stepfun", "siliconflow", "openrouter", "glm", "wenxin", "gemini", SOURCE_CUSTOM,
}

# ---------- 数据模型 ----------


@dataclass
class Model:
    id: str
    model_id: str
    display_name: str = ""
    owned_by: str = ""
    is_enabled: bool = True
    sort_order: int = 0
    context_window: Optional[int] = None

    @property
    def label(self) -> str:
        return self.display_name or self.model_id


@dataclass
class ProviderSetting:
    id: str
    name: str
    base_url: str = ""
    source_type: str = SOURCE_CUSTOM
    api_key: str = ""
    is_enabled: bool = True
    is_built_in: bool = False
    sort_order: int = 0
    system_prompt: Optional[str] = None
    provider_type: str = "openai_compatible"  # openai_compatible | anthropic | gemini
    endpoint_mode: str = "chat_completions"   # chat_completions | responses
    models: list[Model] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    def public_dict(self) -> dict:
        """对外展示：隐藏完整 api_key。"""
        d = self.to_dict()
        d["api_key"] = mask_api_key(self.api_key)
        d["has_api_key"] = bool(self.api_key)
        return d

    def default_model_id(self) -> str:
        enabled = [m for m in self.models if m.is_enabled]
        if not enabled:
            return ""
        return enabled[0].model_id


def mask_api_key(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return "*" * len(key)
    return f"{key[:4]}{'*' * (len(key) - 8)}{key[-4:]}"


# ---------- URL 构造（对应 ETA-2 ProviderUrls） ----------


def normalize_base_url(base_url: str) -> str:
    return base_url.strip().rstrip("/")


def chat_completions_url(base_url: str) -> str:
    return f"{normalize_base_url(base_url)}/chat/completions"


def responses_url(base_url: str) -> str:
    return f"{normalize_base_url(base_url)}/responses"


def openai_models_url(base_url: str) -> str:
    return f"{normalize_base_url(base_url)}/models"


def anthropic_messages_url(base_url: str) -> str:
    return f"{normalize_base_url(base_url)}/v1/messages"


def anthropic_models_url(base_url: str) -> str:
    return f"{normalize_base_url(base_url)}/v1/models"


# ---------- 内置提供商（对应 ETA-2 BuiltinProviders + OfficialModelCatalog） ----------

def _m(provider: str, model_id: str, display: str = "", owned: str = "", order: int = 0,
       window: Optional[int] = None) -> Model:
    return Model(
        id=f"builtin-{provider}-{model_id.replace('.', '-').replace('/', '-')}",
        model_id=model_id,
        display_name=display or model_id,
        owned_by=owned,
        sort_order=order,
        context_window=window,
    )


BUILTIN_PROVIDERS: list[ProviderSetting] = [
    ProviderSetting(
        id="openai", name="OpenAI", base_url="https://api.openai.com/v1",
        source_type="openai", is_built_in=True, sort_order=0, provider_type="openai_compatible",
        endpoint_mode="chat_completions",
        models=[
            _m("openai", "gpt-4o-mini", "GPT-4o mini", "openai", 0, 128000),
            _m("openai", "gpt-4o", "GPT-4o", "openai", 1, 128000),
            _m("openai", "gpt-4.1", "GPT-4.1", "openai", 2, 1048576),
        ],
    ),
    ProviderSetting(
        id="anthropic", name="Anthropic", base_url="https://api.anthropic.com",
        source_type="anthropic", is_built_in=True, sort_order=1, provider_type="anthropic",
        models=[
            _m("anthropic", "claude-sonnet-4-5", "Claude Sonnet 4.5", "anthropic", 0, 1048576),
            _m("anthropic", "claude-opus-4-1", "Claude Opus 4.1", "anthropic", 1, 1048576),
            _m("anthropic", "claude-haiku-4-5", "Claude Haiku 4.5", "anthropic", 2, 1048576),
        ],
    ),
    ProviderSetting(
        id="qwen", name="阿里百炼", base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        source_type="qwen", is_built_in=True, sort_order=2, provider_type="openai_compatible",
        models=[
            _m("qwen", "qwen-plus", "Qwen Plus", "qwen", 0, 131072),
            _m("qwen", "qwen-max", "Qwen Max", "qwen", 1, 32768),
            _m("qwen", "qwen-turbo", "Qwen Turbo", "qwen", 2, 1048576),
        ],
    ),
    ProviderSetting(
        id="deepseek", name="DeepSeek", base_url="https://api.deepseek.com/v1",
        source_type="deepseek", is_built_in=True, sort_order=3, provider_type="openai_compatible",
        models=[
            _m("deepseek", "deepseek-chat", "DeepSeek Chat", "deepseek", 0, 131072),
            _m("deepseek", "deepseek-reasoner", "DeepSeek Reasoner", "deepseek", 1, 131072),
        ],
    ),
    ProviderSetting(
        id="kimi", name="Kimi", base_url="https://api.moonshot.cn/v1",
        source_type="moonshot", is_built_in=True, sort_order=4, provider_type="openai_compatible",
        models=[
            _m("kimi", "moonshot-v1-8k", "Moonshot v1 8K", "moonshot", 0, 8192),
            _m("kimi", "moonshot-v1-32k", "Moonshot v1 32K", "moonshot", 1, 32768),
            _m("kimi", "moonshot-v1-128k", "Moonshot v1 128K", "moonshot", 2, 131072),
        ],
    ),
    ProviderSetting(
        id="mimo", name="MiMo（小米）", base_url="https://api.xiaomimimo.com/v1",
        source_type="mimo", is_built_in=True, sort_order=5, provider_type="openai_compatible",
        models=[
            _m("mimo", "mimo-v2.5-pro", "MiMo V2.5 Pro", "xiaomi", 0, 1000000),
            _m("mimo", "mimo-v2.5", "MiMo V2.5", "xiaomi", 1, 1000000),
        ],
    ),
    ProviderSetting(
        id="minimax", name="MiniMax", base_url="https://api.minimaxi.com/v1",
        source_type="minimax", is_built_in=True, sort_order=6, provider_type="openai_compatible",
        models=[
            _m("minimax", "MiniMax-Text-01", "MiniMax Text 01", "minimax", 0, 1048576),
            _m("minimax", "abab6.5s-chat", "abab6.5s Chat", "minimax", 1, 245760),
        ],
    ),
    ProviderSetting(
        id="stepfun", name="StepFun（阶跃星辰）", base_url="https://api.stepfun.com/v1",
        source_type="stepfun", is_built_in=True, sort_order=7, provider_type="openai_compatible",
        models=[
            _m("stepfun", "step-2-16k", "Step 2 16K", "stepfun", 0, 16384),
            _m("stepfun", "step-1-8k", "Step 1 8K", "stepfun", 1, 8192),
        ],
    ),
    ProviderSetting(
        id="siliconflow", name="硅基流动", base_url="https://api.siliconflow.cn/v1",
        source_type="siliconflow", is_built_in=True, sort_order=8, provider_type="openai_compatible",
        models=[
            _m("siliconflow", "deepseek-ai/DeepSeek-V3", "DeepSeek V3", "deepseek", 0, 65536),
            _m("siliconflow", "Qwen/Qwen2.5-72B-Instruct", "Qwen2.5 72B", "qwen", 1, 131072),
        ],
    ),
    ProviderSetting(
        id="openrouter", name="OpenRouter", base_url="https://openrouter.ai/api/v1",
        source_type="openrouter", is_built_in=True, sort_order=9, provider_type="openai_compatible",
        models=[
            _m("openrouter", "openrouter/auto", "OpenRouter Auto", "openrouter", 0, 400000),
            _m("openrouter", "deepseek/deepseek-chat", "DeepSeek Chat", "deepseek", 1, 131072),
        ],
    ),
    ProviderSetting(
        id="glm", name="智谱 GLM", base_url="https://open.bigmodel.cn/api/paas/v4",
        source_type="glm", is_built_in=True, sort_order=10, provider_type="openai_compatible",
        models=[
            _m("glm", "glm-4-flash", "GLM-4 Flash", "zhipu", 0, 128000),
            _m("glm", "glm-4-plus", "GLM-4 Plus", "zhipu", 1, 128000),
        ],
    ),
    ProviderSetting(
        id="wenxin", name="百度文心", base_url="https://qianfan.baidubce.com/v2",
        source_type="wenxin", is_built_in=True, sort_order=11, provider_type="openai_compatible",
        models=[
            _m("wenxin", "ernie-4.0-turbo-8k", "ERNIE 4.0 Turbo", "baidu", 0, 8192),
            _m("wenxin", "ernie-3.5-8k", "ERNIE 3.5 8K", "baidu", 1, 8192),
        ],
    ),
    ProviderSetting(
        id="gemini", name="Google Gemini", base_url="https://generativelanguage.googleapis.com",
        source_type="gemini", is_built_in=True, sort_order=12, provider_type="gemini",
        models=[
            _m("gemini", "gemini-2.0-flash", "Gemini 2.0 Flash", "google", 0, 1048576),
            _m("gemini", "gemini-1.5-flash", "Gemini 1.5 Flash", "google", 1, 1048576),
        ],
    ),
]

BUILTIN_BY_ID = {p.id: p for p in BUILTIN_PROVIDERS}


# ---------- 来源注册表（对应 ETA-2 ProviderSourceRegistry） ----------


def normalize_source_type(source_type: Optional[str]) -> str:
    s = (source_type or "").strip().lower()
    return s if s in KNOWN_SOURCE_TYPES else SOURCE_CUSTOM


def source_type_from_base_url(base_url: str) -> str:
    host = ""
    try:
        from urllib.parse import urlparse
        host = urlparse(base_url.strip()).hostname or ""
    except Exception:
        host = ""
    mapping = {
        "api.openai.com": "openai",
        "api.anthropic.com": "anthropic",
        "dashscope.aliyuncs.com": "qwen",
        "api.deepseek.com": "deepseek",
        "api.moonshot.cn": "moonshot",
        "api.moonshot.ai": "moonshot",
        "api.xiaomimimo.com": "mimo",
        "api.minimax.io": "minimax",
        "api.minimaxi.com": "minimax",
        "api.stepfun.com": "stepfun",
        "api.siliconflow.cn": "siliconflow",
        "openrouter.ai": "openrouter",
        "open.bigmodel.cn": "glm",
        "qianfan.baidubce.com": "wenxin",
        "generativelanguage.googleapis.com": "gemini",
    }
    for hostname, st in mapping.items():
        if host == hostname:
            return st
    return SOURCE_CUSTOM


def resolve_source_type(provider_id: str, source_type: Optional[str], base_url: str) -> str:
    """归一化：显式 source_type 优先，其次 provider_id，再按 base_url 反查。"""
    normalized = normalize_source_type(source_type)
    if normalized != SOURCE_CUSTOM:
        return normalized
    if provider_id in BUILTIN_BY_ID:
        return BUILTIN_BY_ID[provider_id].source_type
    return source_type_from_base_url(base_url)


# ---------- 存储（对应 ETA-2 ProviderRepository + RemoteModelFetcher） ----------

STORE_PATH = None


def _store_path() -> str:
    global STORE_PATH
    if STORE_PATH is None:
        from app.config import settings
        STORE_PATH = os.path.join(settings.DATA_DIR, "providers.json")
    return STORE_PATH


def _model_from_dict(d: dict) -> Model:
    return Model(
        id=d.get("id") or uuid.uuid4().hex,
        model_id=d.get("model_id", ""),
        display_name=d.get("display_name", ""),
        owned_by=d.get("owned_by", ""),
        is_enabled=bool(d.get("is_enabled", True)),
        sort_order=int(d.get("sort_order", 0)),
        context_window=d.get("context_window"),
    )


def _provider_from_dict(d: dict) -> ProviderSetting:
    return ProviderSetting(
        id=d.get("id", ""),
        name=d.get("name", ""),
        base_url=d.get("base_url", ""),
        source_type=d.get("source_type", SOURCE_CUSTOM),
        api_key=d.get("api_key", ""),
        is_enabled=bool(d.get("is_enabled", True)),
        is_built_in=bool(d.get("is_built_in", False)),
        sort_order=int(d.get("sort_order", 0)),
        system_prompt=d.get("system_prompt"),
        provider_type=d.get("provider_type", "openai_compatible"),
        endpoint_mode=d.get("endpoint_mode", "chat_completions"),
        models=[_model_from_dict(m) for m in d.get("models", [])],
    )


def load_all() -> list[ProviderSetting]:
    path = _store_path()
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [_provider_from_dict(d) for d in data.get("providers", [])]
    except Exception:
        return []


def save_all(providers: list[ProviderSetting]):
    os.makedirs(os.path.dirname(_store_path()), exist_ok=True)
    with open(_store_path(), "w", encoding="utf-8") as f:
        json.dump({"providers": [p.to_dict() for p in providers]}, f, ensure_ascii=False, indent=2)


def ensure_builtins_merged() -> list[ProviderSetting]:
    """内置缺失时合并进存储（保留已有 api_key / models 覆盖）；自定义原样保留。"""
    current = load_all()
    existing = {p.id: p for p in current}
    merged: list[ProviderSetting] = []
    for builtin in BUILTIN_PROVIDERS:
        stored = existing.get(builtin.id)
        if stored is None:
            merged.append(builtin)
        else:
            stored.is_built_in = True
            stored.provider_type = builtin.provider_type
            stored.source_type = builtin.source_type
            merged.append(stored)
    for custom in current:
        if custom.id not in BUILTIN_BY_ID:
            merged.append(custom)
    merged.sort(key=lambda p: p.sort_order)
    save_all(merged)
    return merged


def get_provider_by_id(provider_id: str) -> Optional[ProviderSetting]:
    return next((p for p in load_all() if p.id == provider_id), None)


def new_provider_id() -> str:
    return f"custom-{uuid.uuid4().hex[:8]}"


def add_provider(provider: ProviderSetting) -> ProviderSetting:
    all_p = load_all()
    if any(p.id == provider.id for p in all_p):
        raise ValueError(f"提供商 {provider.id} 已存在")
    provider.is_built_in = False
    provider.sort_order = (max((p.sort_order for p in all_p), default=-1)) + 1
    all_p.append(provider)
    save_all(all_p)
    return provider


def update_provider(provider_id: str, **fields) -> Optional[ProviderSetting]:
    all_p = load_all()
    # 内置尚未并入存储时，先从内置定义补入（对齐 ensure_builtins_merged 语义）
    if not any(p.id == provider_id for p in all_p) and provider_id in BUILTIN_BY_ID:
        builtin = BUILTIN_BY_ID[provider_id]
        all_p.append(ProviderSetting(**{**builtin.to_dict()}))
    for i, p in enumerate(all_p):
        if p.id == provider_id:
            for k, v in fields.items():
                if k == "models":
                    setattr(p, k, [_model_from_dict(m) if isinstance(m, dict) else m for m in v])
                elif hasattr(p, k):
                    setattr(p, k, v)
            save_all(all_p)
            return p
    return None


def delete_provider(provider_id: str) -> bool:
    p = get_provider_by_id(provider_id)
    if p is None or p.is_built_in:
        return False
    all_p = [x for x in load_all() if x.id != provider_id]
    save_all(all_p)
    return True


def copy_provider(provider_id: str) -> Optional[ProviderSetting]:
    """复制内置/自定义为新的自定义提供商（对应 ETA-2 copyProvider）。"""
    src = get_provider_by_id(provider_id)
    if src is None:
        return None
    new_id = new_provider_id()
    copied = ProviderSetting(
        id=new_id, name=f"{src.name} 副本", base_url=src.base_url,
        source_type=src.source_type, api_key=src.api_key, is_built_in=False,
        sort_order=(max((p.sort_order for p in load_all()), default=-1)) + 1,
        provider_type=src.provider_type, endpoint_mode=src.endpoint_mode,
        models=[Model(id=uuid.uuid4().hex, model_id=m.model_id, display_name=m.display_name,
                      owned_by=m.owned_by, is_enabled=m.is_enabled, sort_order=i,
                      context_window=m.context_window) for i, m in enumerate(src.models)],
    )
    all_p = load_all()
    all_p.append(copied)
    save_all(all_p)
    return copied


def reset_builtin(provider_id: str) -> Optional[ProviderSetting]:
    """恢复内置提供商定义（保留已填 api_key），对应 ETA-2 resetBuiltIn。"""
    builtin = BUILTIN_BY_ID.get(provider_id)
    if builtin is None:
        return None
    current = get_provider_by_id(provider_id)
    restored = ProviderSetting(**{**builtin.to_dict()})
    if current:
        restored.api_key = current.api_key
        restored.sort_order = current.sort_order
    all_p = [x for x in load_all() if x.id != provider_id]
    all_p.append(restored)
    all_p.sort(key=lambda p: p.sort_order)
    save_all(all_p)
    return restored


def find_model(provider: ProviderSetting, model_id: str) -> Optional[Model]:
    for m in provider.models:
        if m.model_id == model_id and m.is_enabled:
            return m
    return provider.default_model_id() and provider.models[0] or None


async def fetch_remote_models(provider: ProviderSetting) -> list[Model]:
    """远程拉取模型列表（对应 ETA-2 RemoteModelFetcher）。

    OpenAI 兼容：GET {base}/models，解析 data[].id；
    Anthropic：GET {base}/v1/models。
    """
    import httpx

    if not provider.api_key:
        return []
    if provider.provider_type == "anthropic":
        url = anthropic_models_url(provider.base_url)
        headers = {"x-api-key": provider.api_key, "anthropic-version": "2023-06-01"}
    else:
        url = openai_models_url(provider.base_url)
        headers = {"Authorization": f"Bearer {provider.api_key}"}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, headers=headers)
        r.raise_for_status()
        data = r.json()
    items = data.get("data", []) if isinstance(data, dict) else []
    return [
        Model(
            id=uuid.uuid4().hex,
            model_id=str(it.get("id", "")).strip(),
            display_name=str(it.get("id", "")).strip(),
            owned_by=str(it.get("owned_by", "") or ""),
            sort_order=i,
            context_window=it.get("context_window"),
        )
        for i, it in enumerate(items)
        if str(it.get("id", "")).strip()
    ]
