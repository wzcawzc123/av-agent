import json

import pytest

from app.llm import provider_store
from app.llm.provider_store import (
    Model, ProviderSetting,
    normalize_base_url, chat_completions_url, anthropic_messages_url, openai_models_url,
    normalize_source_type, source_type_from_base_url, resolve_source_type,
    mask_api_key, ensure_builtins_merged, get_provider_by_id,
    add_provider, update_provider, delete_provider, copy_provider, reset_builtin,
)


def test_builtin_providers_cover_mimo_and_more():
    ids = {p.id for p in provider_store.BUILTIN_PROVIDERS}
    assert {"openai", "anthropic", "qwen", "deepseek", "kimi", "mimo",
            "minimax", "stepfun", "siliconflow", "openrouter",
            "glm", "wenxin", "gemini"} <= ids
    mimo = provider_store.BUILTIN_BY_ID["mimo"]
    assert mimo.base_url == "https://api.xiaomimimo.com/v1"
    assert any(m.model_id.startswith("mimo") for m in mimo.models)


def test_url_building():
    assert normalize_base_url(" https://api.deepseek.com/v1/ ") == "https://api.deepseek.com/v1"
    assert chat_completions_url("https://api.deepseek.com/v1") == "https://api.deepseek.com/v1/chat/completions"
    assert anthropic_messages_url("https://api.anthropic.com") == "https://api.anthropic.com/v1/messages"
    assert openai_models_url("https://api.deepseek.com/v1") == "https://api.deepseek.com/v1/models"


def test_source_type_normalization():
    assert normalize_source_type(" DEEPSEEK ") == "deepseek"
    assert normalize_source_type("unknown") == "custom"
    assert source_type_from_base_url("https://api.xiaomimimo.com/v1") == "mimo"
    assert source_type_from_base_url("https://api.deepseek.com/v1") == "deepseek"
    assert source_type_from_base_url("https://some.gateway.com/v1") == "custom"
    assert resolve_source_type("qwen", None, "") == "qwen"
    assert resolve_source_type("custom-x", None, "https://openrouter.ai/api/v1") == "openrouter"


def test_mask_api_key():
    assert mask_api_key("") == ""
    assert mask_api_key("abcdef") == "******"
    key = mask_api_key("sk-1234567890abcdef")
    assert key.startswith("sk-") and key.endswith("cdef") and "*" in key
    assert len(key) == len("sk-1234567890abcdef")


def test_merge_and_crud(tmp_path, monkeypatch):
    monkeypatch.setattr(provider_store, "STORE_PATH", str(tmp_path / "providers.json"))
    all_p = ensure_builtins_merged()
    assert len(all_p) == len(provider_store.BUILTIN_PROVIDERS)

    p = ProviderSetting(id="custom-x", name="中转站", base_url="https://gw.example.com/v1",
                        api_key="sk-1", provider_type="openai_compatible",
                        models=[Model(id="m1", model_id="gpt-4o-mini", display_name="4o mini")])
    add_provider(p)
    assert get_provider_by_id("custom-x").name == "中转站"

    # 更新 api_key
    update_provider("custom-x", api_key="sk-2")
    assert get_provider_by_id("custom-x").api_key == "sk-2"

    # 复制 -> 新自定义
    cp = copy_provider("custom-x")
    assert cp.id != "custom-x" and cp.is_built_in is False
    assert cp.name == "中转站 副本"

    # 删除
    assert delete_provider("custom-x") is True
    assert get_provider_by_id("custom-x") is None

    # 内置不可删
    assert delete_provider("deepseek") is False


def test_reset_builtin_keeps_api_key(tmp_path, monkeypatch):
    monkeypatch.setattr(provider_store, "STORE_PATH", str(tmp_path / "providers.json"))
    ensure_builtins_merged()
    update_provider("deepseek", api_key="sk-keep", base_url="https://custom.example.com/v1")
    reset_builtin("deepseek")
    p = get_provider_by_id("deepseek")
    assert p.api_key == "sk-keep"
    assert p.base_url == provider_store.BUILTIN_BY_ID["deepseek"].base_url


def test_public_dict_masks_key(tmp_path, monkeypatch):
    monkeypatch.setattr(provider_store, "STORE_PATH", str(tmp_path / "providers.json"))
    p = ProviderSetting(id="c", name="C", api_key="sk-secret-key-123")
    d = p.public_dict()
    assert d["api_key"] != "sk-secret-key-123"
    assert d["has_api_key"] is True


@pytest.mark.asyncio
async def test_fetch_remote_models(monkeypatch):
    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"data": [
                {"id": "gpt-4o", "owned_by": "openai"},
                {"id": "gpt-4o-mini", "owned_by": "openai"},
            ]}

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, *a, **k):
            return FakeResp()

    monkeypatch.setattr("httpx.AsyncClient", lambda **k: FakeClient())
    p = ProviderSetting(id="openai", name="OpenAI", base_url="https://api.openai.com/v1",
                        api_key="sk-x")
    models = await provider_store.fetch_remote_models(p)
    assert [m.model_id for m in models] == ["gpt-4o", "gpt-4o-mini"]
