from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src._core.domain.dtos.rag import BaseChunkDTO, QueryAnswerDTO
from src.docs.domain.services.docs_query_service import DocsQueryService


def _chunk(idx: int) -> BaseChunkDTO:
    return BaseChunkDTO(
        content=f"c{idx}",
        chunk_index=idx,
        source_id=str(idx),
        source_title=f"t{idx}",
    )


@pytest.mark.asyncio
async def test_answer_question_returns_answer_and_count():
    pipeline = MagicMock()
    answer = QueryAnswerDTO(answer="x", citations=[])
    chunks = [_chunk(0), _chunk(1), _chunk(2)]
    pipeline.answer = AsyncMock(return_value=(answer, chunks))

    service = DocsQueryService(rag_pipeline=pipeline)
    result_answer, count = await service.answer_question(question="q")

    assert result_answer is answer
    assert count == 3


@pytest.mark.asyncio
async def test_answer_question_propagates_exception():
    """Provider exceptions propagate to the server's generic_exception_handler for mapping."""
    pipeline = MagicMock()
    pipeline.answer = AsyncMock(side_effect=RuntimeError("boom"))

    service = DocsQueryService(rag_pipeline=pipeline)

    with pytest.raises(RuntimeError, match="boom"):
        await service.answer_question(question="q")


@pytest.mark.asyncio
async def test_passes_filters_and_top_k_to_pipeline():
    pipeline = MagicMock()
    pipeline.answer = AsyncMock(
        return_value=(QueryAnswerDTO(answer="a", citations=[]), [])
    )
    filters = {"source_id": {"$eq": "123"}}

    service = DocsQueryService(rag_pipeline=pipeline)
    await service.answer_question(question="q", top_k=9, filters=filters)

    pipeline.answer.assert_awaited_once_with(question="q", top_k=9, filters=filters)
