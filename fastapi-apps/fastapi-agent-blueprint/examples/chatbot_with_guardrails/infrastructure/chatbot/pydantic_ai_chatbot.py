from __future__ import annotations

from typing import Any, Final, LiteralString

import structlog

from src._core.exceptions.llm_exceptions import (
    GuardrailBlocked,
    PromptInjectionDetected,
)
from src._core.infrastructure.llm.guardrail_telemetry import log_guardrail_event
from src._core.infrastructure.llm.guardrails import (
    detect_prompt_injection,
    find_prompt_leak,
    scan_pii,
)

from ...domain.dtos.chatbot_dto import ChatReply

_logger = structlog.stdlib.get_logger(__name__)
_AGENT_NAME: Final[str] = "chatbot_with_guardrails"
_INSTRUCTIONS: Final[LiteralString] = "You are a helpful assistant."

# PII types that block (precise, low false-positive rate).
_BLOCKING_PII_PREFIXES = ("email:", "ipv4:")


class PydanticAIChatbot:
    """LLM-backed chatbot with runtime guardrails wired around agent.run().

    Guardrail layers (following PydanticAIClassifier / PydanticAIAnswerAgent):
    1. Input  — detect_prompt_injection → PromptInjectionDetected (400)
    2. Output — scan_pii (email/ipv4 block, phone log-only) → GuardrailBlocked (422)
    3. Output — find_prompt_leak → log-only
    """

    def __init__(
        self,
        llm_model: Any,
        *,
        guardrails_enabled: bool = True,
    ) -> None:
        try:
            from pydantic_ai import Agent
        except ImportError:
            raise ImportError(
                "pydantic-ai is required. Install with: uv sync --extra pydantic-ai"
            )

        self._guardrails_enabled = guardrails_enabled
        self._agent = Agent(
            model=llm_model,
            output_type=ChatReply,
            instructions=_INSTRUCTIONS,
        )

    async def generate_reply(self, prompt: str) -> tuple[ChatReply, Any]:
        """Generate a reply with guardrails around the LLM call.

        Args:
            prompt: The user input text.

        Returns:
            A tuple of (ChatReply, usage).

        Raises:
            PromptInjectionDetected: If the prompt contains injection imperatives.
            GuardrailBlocked: If the output contains blocking PII types.
        """
        # ── Input guard ────────────────────────────────────────────────────
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

        # ── LLM call ───────────────────────────────────────────────────────
        result = await self._agent.run(prompt)

        # ── Output guard ───────────────────────────────────────────────────
        if self._guardrails_enabled:
            reply_text = result.output.reply

            # scan_pii: block on email/ipv4 (precise), log-only on phone
            pii_tokens = scan_pii(reply_text)
            if pii_tokens:
                blocking = {
                    t
                    for t in pii_tokens
                    if any(t.startswith(p) for p in _BLOCKING_PII_PREFIXES)
                }
                phone_tokens = pii_tokens - blocking

                if phone_tokens:
                    log_guardrail_event(
                        _logger,
                        agent=_AGENT_NAME,
                        stage="output",
                        rule="pii_phone",
                        action="log",
                        count=len(phone_tokens),
                        types=["phone"],
                    )

                if blocking:
                    log_guardrail_event(
                        _logger,
                        agent=_AGENT_NAME,
                        stage="output",
                        rule="pii_blocking",
                        action="block",
                        count=len(blocking),
                        types=sorted({t.split(":")[0] for t in blocking}),
                    )
                    raise GuardrailBlocked()

            # find_prompt_leak: log-only (no-op when instructions < 100 chars)
            if find_prompt_leak(reply_text, _INSTRUCTIONS):
                log_guardrail_event(
                    _logger,
                    agent=_AGENT_NAME,
                    stage="output",
                    rule="prompt_leak",
                    action="log",
                )

        return result.output, result.usage()
