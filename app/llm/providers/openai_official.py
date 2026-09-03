from app.llm.providers.openai_compat import OpenAICompatProvider


class OpenAIProvider(OpenAICompatProvider):
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        super().__init__(api_key, model, "https://api.openai.com/v1", name="openai")
