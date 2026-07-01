from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from ...domain.dtos.chatbot_dto import ChatReply


@runtime_checkable
class ChatbotProtocol(Protocol):
    """Protocol for LLM chatbot replies.

    Implementations live under ``infrastructure/chatbot/``.
    """

    async def generate_reply(self, prompt: str) -> tuple[ChatReply, Any]:
        """Generate a structured reply and return token usage data.

        Args:
            prompt: The user input text.

        Returns:
            A tuple of (ChatReply, usage).
        """
        ...
