from __future__ import annotations

from typing import Any, Final, LiteralString
from uuid import uuid4

import structlog

from src._core.application.usage_tracker import track_agent_usage
from src._core.domain.protocols.agent_usage_recorder_protocol import (
    AgentUsageRecorderProtocol,
)
from src._core.domain.protocols.prompt_provider_protocol import (
    PromptProviderProtocol,
)
from src._core.exceptions.llm_exceptions import PromptInjectionDetected
from src._core.infrastructure.llm.guardrail_telemetry import log_guardrail_event
from src._core.infrastructure.llm.guardrails import detect_prompt_injection
from src._core.infrastructure.llm.prompt_boundaries import (
    CLASSIFIER_INSTRUCTIONS_TAIL,
    compose_instructions,
    escape_for_prompt_xml,
)
from src._core.infrastructure.prompt.inline_prompt_provider import (
    InlinePromptProvider,
)
from src._core.infrastructure.prompt.registry import register_prompt
from src.classification.domain.dtos.classification_dto import ClassificationDTO

_logger = structlog.stdlib.get_logger(__name__)

_AGENT_NAME: Final[str] = "classification"

# Operator-editable persona (#447): resolved per call under this prompt name
# by an operator-editable provider; this constant is the inline default and the
# fallback. The boundary tail is appended in code — see ``compose_instructions``
# and the parallel block in ``pydantic_ai_answer_agent.py``.
_PROMPT_NAME: Final[str] = _AGENT_NAME
_PERSONA: Final[LiteralString] = (
    "You are a precise text classifier. "
    "Classify the given text into one of the provided categories. "
    "Return your confidence score (0 to 1) and a brief reasoning."
)
register_prompt(_PROMPT_NAME, _PERSONA)


class PydanticAIClassifier:
    """Real LLM-backed classifier via PydanticAI Agent."""

    def __init__(
        self,
        llm_model: Any,
        *,
        guardrails_enabled: bool = True,
        usage_recorder: AgentUsageRecorderProtocol | None = None,
        model_name: str = "",
        provider: str | None = None,
        prompt_provider: PromptProviderProtocol | None = None,
    ) -> None:
        try:
            from pydantic_ai import Agent
        except ImportError:
            raise ImportError(
                "pydantic-ai is required for classification. "
                "Install it with: uv sync --extra pydantic-ai"
            )

        self._guardrails_enabled = guardrails_enabled
        # None → untracked (preserves existing unit tests); DI injects the
        # recorder in production.
        self._usage_recorder = usage_recorder
        self._model_name = model_name
        self._provider = provider
        # None → the code persona (preserves existing unit tests); DI injects
        # CoreContainer.prompt_provider in production.
        self._prompt_provider = prompt_provider or InlinePromptProvider()
        # Instructions are composed per run so the code-owned tail lands last;
        # see the matching note in ``pydantic_ai_answer_agent.py``.
        self._agent: Agent[None, ClassificationDTO] = Agent(
            model=llm_model,
            output_type=ClassificationDTO,
        )

    async def classify(
        self,
        text: str,
        categories: list[str] | None = None,
    ) -> ClassificationDTO:
        snapshot = await self._prompt_provider.get_active(
            _PROMPT_NAME, default=_PERSONA
        )
        instructions = compose_instructions(
            snapshot.content, CLASSIFIER_INSTRUCTIONS_TAIL
        )

        if self._usage_recorder is None:
            return await self._classify_guarded(
                text, categories, instructions, capture=None
            )

        async with track_agent_usage(
            call_id=uuid4().hex,
            agent_name=_AGENT_NAME,
            model=self._model_name,
            provider=self._provider,
            recorder=self._usage_recorder,
            prompt_snapshot=snapshot,
            strict_record=False,
        ) as capture:
            return await self._classify_guarded(text, categories, instructions, capture)

    async def _classify_guarded(
        self,
        text: str,
        categories: list[str] | None,
        instructions: str,
        capture: Any | None,
    ) -> ClassificationDTO:
        # Input guard (#197 Phase 3): both `text` AND every `categories` label
        # are user-supplied (request-body list[str], not a server registry) and
        # reach the prompt, so all of them are scanned for injection imperatives.
        # Raised before agent.run() → zero-token blocked usage row.
        if self._guardrails_enabled:
            for field in (text, *(categories or [])):
                rule = detect_prompt_injection(field)
                if rule is not None:
                    log_guardrail_event(
                        _logger,
                        agent=_AGENT_NAME,
                        stage="input",
                        rule=rule,
                        action="block",
                    )
                    raise PromptInjectionDetected()

        prompt = _format_prompt(text, categories)
        result = await self._agent.run(prompt, instructions=instructions)
        if capture is not None:
            capture.set_result(result)
        return result.output


def _format_prompt(text: str, categories: list[str] | None) -> str:
    """Compose the user-turn payload with XML-bounded, escape-safe wrapping.

    Even though current ``categories`` come from a typed registry, every
    label goes through :func:`escape_for_prompt_xml` so a future
    runtime-supplied label cannot break the boundary tags. The user text
    is wrapped in ``<user_text>`` and each label in ``<category>`` —
    child elements, not attributes, so attribute-quote breakout is
    impossible.
    """
    escaped_text = escape_for_prompt_xml(text)
    if not categories:
        return f"<user_text>{escaped_text}</user_text>"

    cats_xml = "\n".join(
        f"<category>{escape_for_prompt_xml(c)}</category>" for c in categories
    )
    return (
        f"<categories>\n{cats_xml}\n</categories>\n"
        f"<user_text>{escaped_text}</user_text>"
    )
