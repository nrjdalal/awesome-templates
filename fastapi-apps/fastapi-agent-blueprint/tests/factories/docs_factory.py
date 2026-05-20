from __future__ import annotations

from datetime import datetime

from src._core.domain.dtos.rag import BaseChunkDTO
from src.docs.domain.dtos.document_dto import DocumentDTO
from src.docs.interface.server.schemas.docs_schema import (
    CreateDocumentRequest,
    UpdateDocumentRequest,
)
from src.docs.interface.worker.payloads.docs_payload import DocumentIngestionPayload


def make_document_dto(
    id: int = 1,
    title: str = "Sample Title",
    content: str = "Sample content body.",
    source: str | None = None,
    chunk_count: int = 0,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> DocumentDTO:
    now = datetime.now()
    return DocumentDTO(
        id=id,
        title=title,
        content=content,
        source=source,
        chunk_count=chunk_count,
        created_at=created_at or now,
        updated_at=updated_at or now,
    )


def make_create_document_request(
    title: str = "Sample Title",
    content: str = "Sample content body.",
    source: str | None = None,
) -> CreateDocumentRequest:
    return CreateDocumentRequest(title=title, content=content, source=source)


def make_update_document_request(
    title: str | None = None,
    content: str | None = None,
    source: str | None = None,
    chunk_count: int | None = None,
) -> UpdateDocumentRequest:
    return UpdateDocumentRequest(
        title=title, content=content, source=source, chunk_count=chunk_count
    )


def make_base_chunk_dto(
    chunk_id: str = "",
    content: str = "chunk body",
    chunk_index: int = 0,
    source_id: str = "1",
    source_title: str = "Sample Title",
) -> BaseChunkDTO:
    return BaseChunkDTO(
        chunk_id=chunk_id,
        content=content,
        chunk_index=chunk_index,
        source_id=source_id,
        source_title=source_title,
    )


def make_document_ingestion_payload(
    document_id: int = 1,
    title: str | None = "Sample Title",
    content: str | None = "Sample content body.",
    source: str | None = None,
) -> DocumentIngestionPayload:
    return DocumentIngestionPayload(
        document_id=document_id,
        title=title,
        content=content,
        source=source,
    )
