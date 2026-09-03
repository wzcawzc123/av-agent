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
