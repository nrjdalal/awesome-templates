from __future__ import annotations

import logging
from collections.abc import Sequence

from src._core.domain.dtos.rag import BaseChunkDTO, CitationDTO, QueryAnswerDTO

logger = logging.getLogger(__name__)

_BODY_EXCERPT_LIMIT = 200
_CONTEXT_CHUNK_LIMIT = 3


class StubAnswerAgent:
    """Templated answerer used when no LLM provider is configured.

    Does not invoke any LLM — assembles a deterministic response from
    the top retrieved chunks so the RAG pipeline still round-trips in
    ``make quickstart`` without external credentials.
    """

    def __init__(self) -> None:
        logger.warning(
            "RAG stub answer agent active — answers are templated, not generated. "
            "Set LLM_PROVIDER + LLM_MODEL for real answers."
        )

    async def answer(
        self,
        question: str,
        context_chunks: Sequence[BaseChunkDTO],
    ) -> QueryAnswerDTO:
        if not context_chunks:
            return QueryAnswerDTO(
                answer=(
                    "No relevant context was retrieved for this question. "
                    "Ingest documents first, or refine the query."
                ),
                citations=[],
            )

        top = list(context_chunks[:_CONTEXT_CHUNK_LIMIT])
        body_lines = ["Based on the retrieved context, here is what I found:", ""]
        body_lines.extend(
            f"[{chunk.source_title}]: {_truncate(chunk.content, _BODY_EXCERPT_LIMIT)}..."
            for chunk in top
        )
        answer = "\n".join(body_lines)
        citations = [CitationDTO.from_chunk(chunk) for chunk in context_chunks]
        return QueryAnswerDTO(answer=answer, citations=citations)


def _truncate(text: str, limit: int) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip()
