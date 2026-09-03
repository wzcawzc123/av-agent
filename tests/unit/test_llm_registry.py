import pytest

from app.llm.base import ChatMessage, LLMProvider
from app.llm.registry import (
    PROVIDER_NAMES,
    save_model_config,
    load_model_config,
    get_provider,
)


def test_builtin_providers():
    assert "deepseek" in PROVIDER_NAMES
    assert "openai" in PROVIDER_NAMES
    assert "gemini" in PROVIDER_NAMES
    assert "qwen" in PROVIDER_NAMES


def test_save_load_config(tmp_path, monkeypatch):
    monkeypatch.setattr("app.llm.registry.CONFIG_PATH", str(tmp_path / "model.json"))
    save_model_config({"provider": "deepseek", "api_key": "sk-x", "model": "deepseek-chat"})
    cfg = load_model_config()
    assert cfg["provider"] == "deepseek"
    assert cfg["api_key"] == "sk-x"


@pytest.mark.asyncio
async def test_get_provider_returns_chat():
    cfg = {"provider": "deepseek", "api_key": "sk-test", "model": "deepseek-chat",
           "base_url": "https://api.deepseek.com/v1"}
    p = await get_provider(cfg)
    assert isinstance(p, LLMProvider)
    assert p.name == "deepseek"
