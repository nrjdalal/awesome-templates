from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import structlog

from ...domain.dtos.chatbot_memory_dto import ChatReply

logger = structlog.stdlib.get_logger(__name__)


@dataclass
class StubUsage:
    """Mock usage object matching the PydanticAI usage signature."""

    input_tokens: int | None = 0
    output_tokens: int | None = 0


class StubChatbotMemory:
    """Deterministic chatbot fallback used when no LLM provider is configured.

    Returns a stub reply that echoes the number of prior turns in history
    so tests can verify history is being passed correctly.
    """

    def __init__(self) -> None:
        logger.warning(
            "Chatbot memory stub active — replies are deterministic, not generated. "
            "Set LLM_PROVIDER + LLM_MODEL for real replies."
        )

    async def generate_reply(
        self, prompt: str, history: list[dict[str, str]]
    ) -> tuple[ChatReply, Any]:
        """Return a stub reply that reflects history length for test visibility."""
        reply = ChatReply(
            reply=f"Stub reply — history has {len(history)} prior turn(s).",
            confidence=0.0,
        )
        usage = StubUsage(input_tokens=0, output_tokens=0)
        return reply, usage
