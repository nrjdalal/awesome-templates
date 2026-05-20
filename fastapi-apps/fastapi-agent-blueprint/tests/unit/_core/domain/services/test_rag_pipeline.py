from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src._core.domain.dtos.rag import BaseChunkDTO, QueryAnswerDTO
from src._core.domain.services.rag_pipeline import RagPipeline
from src._core.domain.value_objects.vector_query import VectorQuery
from src._core.domain.value_objects.vector_search_result import VectorSearchResult


def _make_chunk(idx: int) -> BaseChunkDTO:
    return BaseChunkDTO(
        content=f"content-{idx}",
        chunk_index=idx,
        source_id=str(idx),
        source_title=f"title-{idx}",
    )


def _make_pipeline(
    search_items: list[BaseChunkDTO],
    distances: list[float] | None,
    answer: QueryAnswerDTO | None = None,
):
    embedder = AsyncMock()
    embedder.embed_text = AsyncMock(return_value=[0.1, 0.2, 0.3])

    vector_store = AsyncMock()
    vector_store.search = AsyncMock(
        return_value=VectorSearchResult(
            items=search_items, distances=distances, count=len(search_items)
        )
    )

    agent = AsyncMock()
    agent.answer = AsyncMock(
        return_value=answer or QueryAnswerDTO(answer="final-answer", citations=[])
    )

    pipeline = RagPipeline(
        embedder=embedder, vector_store=vector_store, answer_agent=agent
    )
    return pipeline, embedder, vector_store, agent


@pytest.mark.asyncio
async def test_pipeline_calls_embedder_with_question():
    pipeline, embedder, _, _ = _make_pipeline([_make_chunk(0)], [0.1])

    await pipeline.answer(question="hi?", top_k=3)

    embedder.embed_text.assert_awaited_once_with("hi?")


@pytest.mark.asyncio
async def test_pipeline_calls_search_with_vector_query_filters_top_k():
    pipeline, _, vector_store, _ = _make_pipeline([_make_chunk(0)], [0.1])
    filters = {"source_id": {"$eq": "1"}}

    await pipeline.answer(question="q", top_k=7, filters=filters)

    vector_store.search.assert_awaited_once()
    (query,), _ = vector_store.search.call_args
    assert isinstance(query, VectorQuery)
    assert query.vector == [0.1, 0.2, 0.3]
    assert query.top_k == 7
    assert query.filters == filters


@pytest.mark.asyncio
async def test_pipeline_calls_agent_with_chunks_and_returns_tuple():
    chunks = [_make_chunk(0), _make_chunk(1)]
    expected_answer = QueryAnswerDTO(answer="A", citations=[])
    pipeline, _, _, agent = _make_pipeline(chunks, [0.1, 0.2], answer=expected_answer)

    answer, returned_chunks = await pipeline.answer(question="q")

    agent.answer.assert_awaited_once()
    call_kwargs = agent.answer.call_args.kwargs
    assert call_kwargs["question"] == "q"
    assert call_kwargs["context_chunks"] == chunks
    assert answer is expected_answer
    assert returned_chunks == chunks


@pytest.mark.asyncio
async def test_pipeline_attaches_distance_attribute_to_chunks():
    chunks = [_make_chunk(0), _make_chunk(1)]
    distances = [0.25, 0.75]
    pipeline, _, _, _ = _make_pipeline(chunks, distances)

    _, returned = await pipeline.answer(question="q")

    assert returned[0]._distance == 0.25  # type: ignore[attr-defined]
    assert returned[1]._distance == 0.75  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_pipeline_handles_empty_search_result():
    pipeline, _, _, agent = _make_pipeline([], distances=None)

    answer, chunks = await pipeline.answer(question="q")

    agent.answer.assert_awaited_once()
    assert agent.answer.call_args.kwargs["context_chunks"] == []
    assert chunks == []
    assert isinstance(answer, QueryAnswerDTO)


@pytest.mark.asyncio
async def test_pipeline_handles_none_distances():
    """When vector_store returns distances=None, _distance should be None."""
    chunks = [_make_chunk(0), _make_chunk(1)]
    pipeline, _, _, _ = _make_pipeline(chunks, distances=None)

    _, returned = await pipeline.answer(question="q")

    assert returned[0]._distance is None  # type: ignore[attr-defined]
    assert returned[1]._distance is None  # type: ignore[attr-defined]
