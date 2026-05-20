from __future__ import annotations

from typing import Any

from src._core.domain.dtos.rag import BaseChunkDTO, QueryAnswerDTO
from src._core.domain.services.rag_pipeline import RagPipeline


class DocsQueryService:
    """Thin wrapper over the core RAG pipeline for the docs domain.

    Exists so the router has a domain-layer entry point; all RAG
    orchestration lives in ``RagPipeline`` (``_core.domain.services``).
    The docs domain plugs its own chunk store + embedder + answer agent
    into the pipeline via DI — this service just delegates to the pipeline.
    LLM/provider exceptions propagate to the server's generic_exception_handler.
    """

    def __init__(self, rag_pipeline: RagPipeline[BaseChunkDTO]) -> None:
        self._pipeline = rag_pipeline

    async def answer_question(
        self,
        question: str,
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> tuple[QueryAnswerDTO, int]:
        answer, chunks = await self._pipeline.answer(
            question=question, top_k=top_k, filters=filters
        )
        return answer, len(chunks)
