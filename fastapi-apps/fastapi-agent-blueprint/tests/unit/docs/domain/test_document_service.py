from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src._core.common.text_utils import chunk_text
from src._core.domain.dtos.rag import BaseChunkDTO
from src._core.domain.value_objects.vector_search_result import VectorSearchResult
from src.docs.domain.services.document_service import DocumentService
from tests.factories.docs_factory import (
    make_create_document_request,
    make_document_dto,
)


def _make_service(
    insert_return,
    embedder_batch: list[list[float]] | None = None,
    update_return=None,
    search_items: list[BaseChunkDTO] | None = None,
    select_return=None,
):
    repo = MagicMock()
    repo.insert_data = AsyncMock(return_value=insert_return)
    repo.update_data_by_data_id = AsyncMock(
        return_value=update_return if update_return is not None else insert_return
    )
    repo.delete_data_by_data_id = AsyncMock(return_value=True)
    repo.select_data_by_id = AsyncMock(
        return_value=select_return if select_return is not None else insert_return
    )

    embedder = MagicMock()
    embedder.dimension = 8
    embedder.embed_batch = AsyncMock(return_value=embedder_batch or [[0.0] * 8])

    vector_store = MagicMock()
    vector_store.upsert = AsyncMock(return_value=0)
    vector_store.search = AsyncMock(
        return_value=VectorSearchResult(
            items=search_items or [], distances=None, count=len(search_items or [])
        )
    )
    vector_store.delete = AsyncMock(return_value=True)

    service = DocumentService(
        document_repository=repo, embedder=embedder, chunk_vector_store=vector_store
    )
    return service, repo, embedder, vector_store


@pytest.mark.asyncio
async def test_create_data_short_document_single_chunk():
    created_dto = make_document_dto(
        id=1, title="T", content="Hello world.", chunk_count=0
    )
    updated_dto = created_dto.model_copy(update={"chunk_count": 1})
    service, repo, embedder, vector_store = _make_service(
        insert_return=created_dto,
        embedder_batch=[[0.1] * 8],
        update_return=updated_dto,
    )

    result = await service.create_data(
        entity=make_create_document_request(content="Hello world.")
    )

    embedder.embed_batch.assert_awaited_once()
    vector_store.upsert.assert_awaited_once()
    upserted = vector_store.upsert.call_args.args[0]
    assert len(upserted) == 1
    assert result.chunk_count == 1
    repo.update_data_by_data_id.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_data_chunks_and_upserts():
    long_content = ("Paragraph about RAG pipelines. " * 200).strip()
    expected_chunks = chunk_text(long_content)
    assert len(expected_chunks) >= 2, "fixture should span multiple chunks"
    n = len(expected_chunks)

    created_dto = make_document_dto(
        id=42, title="Long", content=long_content, chunk_count=0
    )
    updated_dto = created_dto.model_copy(update={"chunk_count": n})

    service, repo, embedder, vector_store = _make_service(
        insert_return=created_dto,
        embedder_batch=[[0.1] * 8 for _ in range(n)],
        update_return=updated_dto,
    )

    result = await service.create_data(
        entity=make_create_document_request(title="Long", content=long_content)
    )

    embedder.embed_batch.assert_awaited_once_with(expected_chunks)
    vector_store.upsert.assert_awaited_once()
    upserted = vector_store.upsert.call_args.args[0]
    assert len(upserted) == n
    assert result.chunk_count == n


@pytest.mark.asyncio
async def test_delete_data_purges_vectors():
    doc = make_document_dto(id=7, chunk_count=3)
    chunk_a = BaseChunkDTO(
        chunk_id="key-a", content="a", chunk_index=0, source_id="7", source_title="T"
    )
    chunk_b = BaseChunkDTO(
        chunk_id="key-b", content="b", chunk_index=1, source_id="7", source_title="T"
    )

    service, repo, _, vector_store = _make_service(
        insert_return=doc,
        search_items=[chunk_a, chunk_b],
        select_return=doc,
    )

    result = await service.delete_data_by_data_id(data_id=7)

    assert result is True
    vector_store.search.assert_awaited_once()
    search_query = vector_store.search.call_args.args[0]
    assert search_query.filters == {"source_id": {"$eq": "7"}}
    vector_store.delete.assert_awaited_once_with(["key-a", "key-b"])
    repo.delete_data_by_data_id.assert_awaited_once_with(data_id=7)


@pytest.mark.asyncio
async def test_ingest_existing_document_updates_chunk_count():
    doc = make_document_dto(id=5, content="Fresh content here.", chunk_count=0)
    service, repo, embedder, vector_store = _make_service(
        insert_return=doc,
        embedder_batch=[[0.1] * 8],
        select_return=doc,
    )

    count = await service.ingest_existing_document(document_id=5)

    assert count == 1
    embedder.embed_batch.assert_awaited_once()
    vector_store.upsert.assert_awaited_once()
    repo.update_data_by_data_id.assert_awaited_once()


def test_should_ingest_sync_threshold():
    service, *_ = _make_service(insert_return=make_document_dto())

    assert service.should_ingest_sync("short") is True
    assert service.should_ingest_sync("x" * 20_001) is False


@pytest.mark.asyncio
async def test_create_without_ingestion_skips_embed_and_upsert():
    created_dto = make_document_dto(id=11, title="Large", content="x" * 50_000)
    service, repo, embedder, vector_store = _make_service(insert_return=created_dto)

    result = await service.create_without_ingestion(
        entity=make_create_document_request(title="Large", content="x" * 50_000)
    )

    assert result.id == 11
    assert result.chunk_count == 0
    repo.insert_data.assert_awaited_once()
    embedder.embed_batch.assert_not_awaited()
    vector_store.upsert.assert_not_awaited()
    repo.update_data_by_data_id.assert_not_awaited()
