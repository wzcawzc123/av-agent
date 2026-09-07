import httpx

from app.llm.base import LLMProvider


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self, api_key: str, model: str = "gemini-1.5-flash"):
        self.api_key = api_key
        self.model = model

    async def chat(self, messages, temperature=0.7):
        contents = []
        for m in messages:
            if m.role in ("user", "assistant"):
                contents.append({"role": "model" if m.role == "assistant" else "user",
                                 "parts": [{"text": m.content}]})
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
                params={"key": self.api_key},
                json={"contents": contents},
            )
            r.raise_for_status()
            return r.json()["candidates"][0]["content"]["parts"][0]["text"]
