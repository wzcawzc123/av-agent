"""模型提供商注册与客户端工厂（对齐 ETA-2 ProviderClientFactory + ProviderRepository）。

- 内置提供商来自 provider_store.BUILTIN_PROVIDERS（启动时合并进 providers.json）；
- 用户可自定义新增 OpenAI 兼容 / Anthropic / Gemini 提供商；
- get_provider(config) 按 provider 类型分派客户端。
"""
import json
import os

from app.llm.base import LLMProvider
from app.llm.providers.openai_compat import OpenAICompatProvider
from app.llm.providers.anthropic import AnthropicProvider
from app.llm.providers.gemini import GeminiProvider
from app.llm import provider_store

CONFIG_PATH = None

PROVIDER_NAMES = list(provider_store.BUILTIN_BY_ID.keys())


def _path():
    global CONFIG_PATH
    if CONFIG_PATH is None:
        from app.config import settings

        CONFIG_PATH = os.path.join(settings.DATA_DIR, "model.json")
    return CONFIG_PATH


def save_model_config(cfg: dict):
    from app.security.crypto import encrypt_secret

    stored = dict(cfg)
    stored["api_key"] = encrypt_secret(stored.get("api_key", ""))
    with open(_path(), "w", encoding="utf-8") as f:
        json.dump(stored, f, ensure_ascii=False, indent=2)


def load_model_config() -> dict:
    if not os.path.exists(_path()):
        return {}
    from app.security.crypto import decrypt_secret

    with open(_path(), "r", encoding="utf-8") as f:
        cfg = json.load(f)
    if isinstance(cfg, dict) and cfg.get("api_key"):
        cfg["api_key"] = decrypt_secret(cfg["api_key"])
    return cfg


def all_providers() -> list[provider_store.ProviderSetting]:
    """内置 + 自定义的完整列表（启动时确保内置合并）。"""
    return provider_store.ensure_builtins_merged()


def get_provider_by_id(provider_id: str) -> provider_store.ProviderSetting | None:
    return provider_store.get_provider_by_id(provider_id)


def resolve_credentials(cfg: dict) -> dict:
    """合并配置与存储：api_key / model / base_url 缺省时从提供商记录补齐。"""
    provider_id = cfg.get("provider") or "deepseek"
    stored = get_provider_by_id(provider_id)
    base = stored or provider_store.BUILTIN_BY_ID.get(provider_id)
    api_key = cfg.get("api_key") or (stored.api_key if stored else "")
    model = cfg.get("model") or (base.default_model_id() if base else "")
    base_url = cfg.get("base_url") or (base.base_url if base else "")
    return {"provider": provider_id, "api_key": api_key, "model": model, "base_url": base_url,
            "provider_type": base.provider_type if base else "openai_compatible",
            "endpoint_mode": base.endpoint_mode if base else "chat_completions"}


async def get_provider(config: dict) -> LLMProvider:
    r = resolve_credentials(config)
    provider_type = r["provider_type"]
    if provider_type == "gemini":
        return GeminiProvider(r["api_key"], r["model"])
    if provider_type == "anthropic":
        return AnthropicProvider(r["api_key"], r["model"], r["base_url"])
    return OpenAICompatProvider(r["api_key"], r["model"], r["base_url"], name=r["provider"])
