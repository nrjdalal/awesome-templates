from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import structlog

from ...domain.dtos.chatbot_dto import ChatReply

logger = structlog.stdlib.get_logger(__name__)


@dataclass
class StubUsage:
    """Mock usage object matching the PydanticAI usage signature."""

    input_tokens: int | None = 0
    output_tokens: int | None = 0


class StubChatbot:
    """Deterministic chatbot fallback used when no LLM provider is configured.

    Emits warning log at startup to inform the developer.
    """

    def __init__(self) -> None:
        logger.warning(
            "Chatbot stub active — replies are deterministic, not generated. "
            "Set LLM_PROVIDER + LLM_MODEL for real replies."
        )

    async def generate_reply(self, prompt: str) -> tuple[ChatReply, Any]:
        """Return a mock reply with low confidence and zero token usage."""
        _ = prompt
        reply = ChatReply(
            reply="Stub chatbot reply — no LLM model configured.",
            confidence=0.0,
        )
        usage = StubUsage(input_tokens=0, output_tokens=0)
        return reply, usage
