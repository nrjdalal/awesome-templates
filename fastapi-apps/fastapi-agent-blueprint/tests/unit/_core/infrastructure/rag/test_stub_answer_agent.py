from __future__ import annotations

import pytest

from src._core.domain.dtos.rag import BaseChunkDTO
from src._core.infrastructure.rag.stub_answer_agent import StubAnswerAgent


def _chunk(idx: int, title: str, content: str = "chunk body content") -> BaseChunkDTO:
    return BaseChunkDTO(
        content=content,
        chunk_index=idx,
        source_id=str(idx),
        source_title=title,
    )


@pytest.mark.asyncio
async def test_returns_templated_answer_with_all_titles():
    agent = StubAnswerAgent()
    chunks = [
        _chunk(0, "Alpha Doc"),
        _chunk(1, "Beta Doc"),
        _chunk(2, "Gamma Doc"),
    ]

    result = await agent.answer(question="q?", context_chunks=chunks)

    assert "Alpha Doc" in result.answer
    assert "Beta Doc" in result.answer
    assert "Gamma Doc" in result.answer
    assert len(result.citations) == 3


@pytest.mark.asyncio
async def test_empty_chunks_returns_fallback_and_no_citations():
    agent = StubAnswerAgent()

    result = await agent.answer(question="q?", context_chunks=[])

    assert result.citations == []
    assert result.answer  # non-empty fallback message
    assert "No relevant" in result.answer or "Ingest" in result.answer


@pytest.mark.asyncio
async def test_citations_preserve_source_id_and_source_title():
    agent = StubAnswerAgent()
    chunks = [
        _chunk(0, "Doc One"),
        _chunk(7, "Doc Two"),
    ]

    result = await agent.answer(question="q", context_chunks=chunks)

    assert result.citations[0].source_id == "0"
    assert result.citations[0].source_title == "Doc One"
    assert result.citations[1].source_id == "7"
    assert result.citations[1].source_title == "Doc Two"
