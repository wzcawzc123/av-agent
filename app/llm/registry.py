import json
import os

from app.llm.base import LLMProvider
from app.llm.providers.openai_compat import OpenAICompatProvider
from app.llm.providers.openai_official import OpenAIProvider
from app.llm.providers.gemini import GeminiProvider

CONFIG_PATH = None

BUILTIN = {
    "deepseek": {"base_url": "https://api.deepseek.com/v1", "default_model": "deepseek-chat"},
    "qwen": {"base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "default_model": "qwen-plus"},
    "kimi": {"base_url": "https://api.moonshot.cn/v1", "default_model": "moonshot-v1-8k"},
    "glm": {"base_url": "https://open.bigmodel.cn/api/paas/v4", "default_model": "glm-4-flash"},
    "openai": {"base_url": "https://api.openai.com/v1", "default_model": "gpt-4o-mini"},
    "wenxin": {"base_url": "https://qianfan.baidubce.com/v2", "default_model": "ernie-4.0-turbo-8k"},
    "gemini": {"base_url": "", "default_model": "gemini-1.5-flash"},
}
PROVIDER_NAMES = list(BUILTIN.keys())


def _path():
    global CONFIG_PATH
    if CONFIG_PATH is None:
        from app.config import settings

        CONFIG_PATH = os.path.join(settings.DATA_DIR, "model.json")
    return CONFIG_PATH


def save_model_config(cfg: dict):
    with open(_path(), "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def load_model_config() -> dict:
    if not os.path.exists(_path()):
        return {}
    with open(_path(), "r", encoding="utf-8") as f:
        return json.load(f)


async def get_provider(config: dict) -> LLMProvider:
    provider = config.get("provider", "deepseek")
    api_key = config.get("api_key", "")
    model = config.get("model") or BUILTIN[provider]["default_model"]
    base_url = config.get("base_url") or BUILTIN[provider]["base_url"]
    if provider == "openai":
        return OpenAIProvider(api_key, model)
    if provider == "gemini":
        return GeminiProvider(api_key, model)
    return OpenAICompatProvider(api_key, model, base_url, name=provider)
