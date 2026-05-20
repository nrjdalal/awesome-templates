from __future__ import annotations

import pytest

from src.docs.infrastructure.repositories.document_repository import DocumentRepository
from src.docs.interface.server.schemas.docs_schema import UpdateDocumentRequest
from tests.factories.docs_factory import make_create_document_request


@pytest.mark.asyncio
async def test_create_and_fetch_document(test_db):
    repo = DocumentRepository(database=test_db)
    request = make_create_document_request(title="Alpha", content="hello")

    created = await repo.insert_data(entity=request)
    assert created.id is not None
    assert created.title == "Alpha"

    fetched = await repo.select_data_by_id(data_id=created.id)
    assert fetched.id == created.id
    assert fetched.content == "hello"


@pytest.mark.asyncio
async def test_list_documents_paginated(test_db):
    repo = DocumentRepository(database=test_db)
    for i in range(3):
        await repo.insert_data(
            entity=make_create_document_request(title=f"Doc{i}", content=f"c{i}")
        )

    datas, total = await repo.select_datas_with_count(page=1, page_size=2)

    assert len(datas) == 2
    assert total >= 3


@pytest.mark.asyncio
async def test_update_document_chunk_count(test_db):
    repo = DocumentRepository(database=test_db)
    created = await repo.insert_data(
        entity=make_create_document_request(title="U", content="body")
    )

    updated = await repo.update_data_by_data_id(
        data_id=created.id, entity=UpdateDocumentRequest(chunk_count=5)
    )

    assert updated.chunk_count == 5
    assert updated.title == "U"


@pytest.mark.asyncio
async def test_delete_document(test_db):
    repo = DocumentRepository(database=test_db)
    created = await repo.insert_data(
        entity=make_create_document_request(title="D", content="x")
    )

    result = await repo.delete_data_by_data_id(data_id=created.id)
    assert result is True
