from dataclasses import dataclass
from abc import ABC, abstractmethod


@dataclass
class ChatMessage:
    role: str  # system | user | assistant
    content: str


class LLMProvider(ABC):
    name: str = "base"

    @abstractmethod
    async def chat(self, messages: list[ChatMessage], temperature: float = 0.7) -> str:
        """返回模型回复文本。"""
        raise NotImplementedError

    async def chat_stream(self, messages: list[ChatMessage], temperature: float = 0.7):
        """流式回复：逐段 yield 文本增量。默认实现退化为一次性 chat()。"""
        yield await self.chat(messages, temperature=temperature)
