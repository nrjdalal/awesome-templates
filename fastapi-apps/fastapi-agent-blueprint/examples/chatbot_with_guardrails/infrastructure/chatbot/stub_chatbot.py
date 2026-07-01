from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import structlog

from src._core.exceptions.llm_exceptions import PromptInjectionDetected
from src._core.infrastructure.llm.guardrail_telemetry import log_guardrail_event
from src._core.infrastructure.llm.guardrails import detect_prompt_injection

from ...domain.dtos.chatbot_dto import ChatReply

_logger = structlog.stdlib.get_logger(__name__)
_AGENT_NAME = "chatbot_with_guardrails_stub"


@dataclass
class StubUsage:
    input_tokens: int | None = 0
    output_tokens: int | None = 0


class StubChatbot:
    """Deterministic chatbot fallback with guardrails enabled for consistency."""

    def __init__(self, *, guardrails_enabled: bool = True) -> None:
        self._guardrails_enabled = guardrails_enabled
        _logger.warning("Chatbot stub active — no LLM model configured.")

    async def generate_reply(self, prompt: str) -> tuple[ChatReply, Any]:
        if self._guardrails_enabled:
            rule = detect_prompt_injection(prompt)
            if rule is not None:
                log_guardrail_event(
                    _logger,
                    agent=_AGENT_NAME,
                    stage="input",
                    rule=rule,
                    action="block",
                )
                raise PromptInjectionDetected()

        reply = ChatReply(
            reply="Stub chatbot reply — no LLM model configured.",
            confidence=0.0,
        )
        return reply, StubUsage()
