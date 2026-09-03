import httpx

from app.llm.base import LLMProvider, ChatMessage


class OpenAICompatProvider(LLMProvider):
    """适用于 DeepSeek / 通义 / Kimi / GLM / 文心（OpenAI 兼容 /v1/chat/completions）。"""

    def __init__(self, api_key: str, model: str, base_url: str, name: str = "openai_compat"):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.name = name

    async def chat(self, messages, temperature=0.7):
        payload = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
        }
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
            )
            r.raise_for_status()
            data = r.json()
            return data["choices"][0]["message"]["content"]
