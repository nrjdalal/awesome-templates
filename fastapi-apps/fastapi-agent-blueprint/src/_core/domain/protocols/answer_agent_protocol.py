from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from src._core.domain.dtos.rag import BaseChunkDTO, QueryAnswerDTO


@runtime_checkable
class AnswerAgentProtocol(Protocol):
    """Generates the final answer from retrieved chunks.

    Implementations live under ``src/_core/infrastructure/rag/``; any
    consumer domain plugs them into ``RagPipeline`` via DI.

    Bundled implementations:
    - ``PydanticAIAnswerAgent`` — real LLM via PydanticAI.
    - ``StubAnswerAgent`` — templated fallback when no LLM is configured.
    """

    async def answer(
        self,
        question: str,
        context_chunks: Sequence[BaseChunkDTO],
    ) -> QueryAnswerDTO: ...
