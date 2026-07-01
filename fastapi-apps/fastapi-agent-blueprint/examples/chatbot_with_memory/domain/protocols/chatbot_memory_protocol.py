from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from ..dtos.chatbot_memory_dto import ChatReply


@runtime_checkable
class ChatbotMemoryProtocol(Protocol):
    """Protocol for LLM chatbot with conversation history support.

    Implementations live under ``infrastructure/chatbot/``.
    """

    async def generate_reply(
        self, prompt: str, history: list[dict[str, str]]
    ) -> tuple[ChatReply, Any]:
        """Generate a structured reply given prompt and prior conversation history.

        Args:
            prompt: The user input text.
            history: List of prior turns as [{"role": "user"|"assistant", "content": "..."}].

        Returns:
            A tuple of (ChatReply, usage).
        """
        ...
