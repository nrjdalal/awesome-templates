from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Final, LiteralString
from uuid import uuid4

import structlog
from pydantic import BaseModel, Field

from src._core.application.usage_tracker import track_agent_usage
from src._core.domain.dtos.rag import BaseChunkDTO, CitationDTO, QueryAnswerDTO
from src._core.domain.protocols.agent_usage_recorder_protocol import (
    AgentUsageRecorderProtocol,
)
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
from src._core.infrastructure.llm.prompt_boundaries import (
    RAG_INSTRUCTIONS_TAIL,
    escape_for_prompt_xml,
)

_logger = structlog.stdlib.get_logger(__name__)

_AGENT_NAME: Final[str] = "docs_answer"

_PERSONA: Final[LiteralString] = (
    "You are a precise RAG assistant. "
    "Answer the user's question using ONLY the provided context chunks. "
    "Cite sources as [source_title]. "
    "If the context doesn't contain the answer, say so plainly."
)

# Concatenation of two ``LiteralString`` values is itself ``LiteralString``,
# so static analysis (``uv run pyright``) blocks any future f-string that
# would interpolate untrusted runtime data into the agent's behavioural
# contract. The boundary-tag wrapping in ``_format_prompt`` is what
# actually mitigates LLM01; this constant is the matching "treat the
# wrapped content as untrusted DATA" guidance for the model.
_INSTRUCTIONS: Final[LiteralString] = _PERSONA + RAG_INSTRUCTIONS_TAIL

# PII token types precise enough to BLOCK on fabrication. ``email`` (``@`` anchor)
# and ``ipv4`` (range-validated dotted quad) rarely collide with non-PII text;
# ``phone`` is a bare digit run that collides with dates / invoice numbers / IDs,
# so phone fabrication is logged but NOT blocked (codex completion-gate MEDIUM).
_BLOCKING_PII_TYPES: Final[frozenset[str]] = frozenset({"email", "ipv4"})


class _AgentAnswer(BaseModel):
    """Structured output requested from the LLM.

    Citations are assembled deterministically from the retrieval result
    (see ``PydanticAIAnswerAgent.answer``) rather than fabricated by the
    model, so the agent is asked only for the answer text.
    """

    answer: str = Field(..., description="The answer text")


class PydanticAIAnswerAgent:
    """Real LLM-backed RAG answerer via PydanticAI."""

    def __init__(
        self,
        llm_model: Any,
        *,
        guardrails_enabled: bool = True,
        usage_recorder: AgentUsageRecorderProtocol | None = None,
        model_name: str = "",
        provider: str | None = None,
    ) -> None:
        try:
            from pydantic_ai import Agent
        except ImportError:
            raise ImportError(
                "pydantic-ai is required for the RAG answer agent. "
                "Install it with: uv sync --extra pydantic-ai"
            )

        self._guardrails_enabled = guardrails_enabled
        # When ``usage_recorder`` is None the call runs untracked (preserves the
        # adapter's existing unit tests). DI injects the recorder in production.
        self._usage_recorder = usage_recorder
        self._model_name = model_name
        self._provider = provider
        self._agent: Agent[None, _AgentAnswer] = Agent(
            model=llm_model,
            output_type=_AgentAnswer,
            instructions=_INSTRUCTIONS,
        )

    async def answer(
        self,
        question: str,
        context_chunks: Sequence[BaseChunkDTO],
    ) -> QueryAnswerDTO:
        chunks = list(context_chunks)

        if self._usage_recorder is None:
            return await self._answer_guarded(question, chunks, capture=None)

        # Track usage for the whole call. A guardrail block raises inside the CM,
        # so ``track_agent_usage`` records it (status=error + error_code +
        # guardrail_triggered=True). strict_record=False: a ledger write failure
        # must never turn a successful answer into a 500 nor mask a guardrail.
        async with track_agent_usage(
            call_id=uuid4().hex,
            agent_name=_AGENT_NAME,
            model=self._model_name,
            provider=self._provider,
            recorder=self._usage_recorder,
            strict_record=False,
        ) as capture:
            return await self._answer_guarded(question, chunks, capture)

    async def _answer_guarded(
        self,
        question: str,
        chunks: list[BaseChunkDTO],
        capture: Any | None,
    ) -> QueryAnswerDTO:
        # Input guard (#197 Phase 3): block obvious prompt-injection imperatives
        # in the user question BEFORE calling the model. Only the question is
        # scanned — retrieved chunk content is DATA (already escaped in Phase
        # 1+2) and may legitimately quote trigger phrases. Raised before
        # agent.run() → no result → zero-token blocked usage row.
        if self._guardrails_enabled:
            rule = detect_prompt_injection(question)
            if rule is not None:
                # rule name → structlog ONLY; never to the client response.
                log_guardrail_event(
                    _logger,
                    agent=_AGENT_NAME,
                    stage="input",
                    rule=rule,
                    action="block",
                )
                raise PromptInjectionDetected()

        prompt = _format_prompt(question, chunks)
        result = await self._agent.run(prompt)
        # Record consumed tokens BEFORE the output guard so an output block still
        # accounts for the tokens the provider already charged.
        if capture is not None:
            capture.set_result(result)
        answer_text = result.output.answer

        # Output guard (#197 Phase 3).
        if self._guardrails_enabled:
            self._check_output(answer_text, chunks)

        citations = [CitationDTO.from_chunk(chunk) for chunk in chunks]
        return QueryAnswerDTO(answer=answer_text, citations=citations)

    def _check_output(self, answer_text: str, chunks: list[BaseChunkDTO]) -> None:
        """Block fabricated *precise* PII; log everything else.

        PII fabrication = PII in the answer that is absent from every chunk
        field that reaches the prompt (``source_title`` + ``content``).

        Severity follows the precise-block / fuzzy-log doctrine BY PII TYPE:
        ``email`` and ``ipv4`` have structural anchors (``@``, range-validated
        dotted quad) → precise → BLOCK. ``phone`` is a bare digit run that
        collides with dates, invoice numbers, and IDs → fuzzy → LOG-ONLY,
        never block (a 422 on a legitimately-cited date would be a worse
        outcome than missing an invented phone number). Verbatim prompt leak
        is also log-only.

        Only the count + token TYPES are logged — never the PII values.
        """
        context_pii: set[str] = set()
        for chunk in chunks:
            context_pii |= scan_pii(chunk.source_title)
            context_pii |= scan_pii(chunk.content)

        fabricated = scan_pii(answer_text) - context_pii
        if fabricated:
            blocking = {
                token
                for token in fabricated
                if token.split(":", 1)[0] in _BLOCKING_PII_TYPES
            }
            fuzzy = fabricated - blocking
            if fuzzy:
                log_guardrail_event(
                    _logger,
                    agent=_AGENT_NAME,
                    stage="output",
                    rule="pii_fabrication_fuzzy",
                    action="log",
                    count=len(fuzzy),
                    types=sorted({t.split(":", 1)[0] for t in fuzzy}),
                )
            if blocking:
                log_guardrail_event(
                    _logger,
                    agent=_AGENT_NAME,
                    stage="output",
                    rule="pii_fabrication",
                    action="block",
                    count=len(blocking),
                    types=sorted({t.split(":", 1)[0] for t in blocking}),
                )
                raise GuardrailBlocked()

        if find_prompt_leak(answer_text, _INSTRUCTIONS):
            log_guardrail_event(
                _logger,
                agent=_AGENT_NAME,
                stage="output",
                rule="prompt_leak",
                action="log",
            )


def _format_prompt(question: str, chunks: list[BaseChunkDTO]) -> str:
    """Compose the user-turn payload with XML-bounded, escape-safe wrapping.

    Every dynamic field (chunk title, chunk content, user question) goes
    through :func:`escape_for_prompt_xml`. ``index`` is integer-formatted
    so it cannot host injection. ``<title>`` / ``<content>`` are child
    elements (not attributes) so an attribute-quote breakout
    (``title=""onload="``) is impossible.

    A literal ``</document>`` inside chunk content is escaped to
    ``&lt;/document&gt;`` and therefore cannot close the surrounding
    boundary in the model's parse — verified by the adversarial fixtures
    in ``test_pydantic_ai_answer_agent_prompt.py``.
    """
    escaped_question = escape_for_prompt_xml(question)
    if not chunks:
        return f"<documents />\n<user_question>{escaped_question}</user_question>"

    docs_xml = "\n".join(
        f'<document index="{i + 1}">'
        f"<title>{escape_for_prompt_xml(chunk.source_title)}</title>"
        f"<content>{escape_for_prompt_xml(chunk.content)}</content>"
        f"</document>"
        for i, chunk in enumerate(chunks)
    )
    return (
        f"<documents>\n{docs_xml}\n</documents>\n"
        f"<user_question>{escaped_question}</user_question>"
    )
