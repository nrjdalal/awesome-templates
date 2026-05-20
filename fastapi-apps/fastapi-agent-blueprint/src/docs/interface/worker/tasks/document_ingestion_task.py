from __future__ import annotations

from dependency_injector.wiring import Provide, inject

from src._apps.worker.broker import broker
from src.docs.domain.services.document_service import DocumentService
from src.docs.infrastructure.di.docs_container import DocsContainer
from src.docs.interface.worker.payloads.docs_payload import (
    DOCS_INGEST_DOCUMENT_TASK_NAME,
    DocumentIngestionPayload,
)


@broker.task(task_name=DOCS_INGEST_DOCUMENT_TASK_NAME)
@inject
async def ingest_document_task(
    document_service: DocumentService = Provide[DocsContainer.document_service],
    **kwargs,
) -> None:
    """Re-run the docs ingestion pipeline for an already-persisted document.

    Dispatched from ``POST /v1/docs/documents`` when the submitted
    content exceeds ``DocumentService._SYNC_INGEST_CHAR_THRESHOLD`` — the
    row is created synchronously, and chunking + embedding + upsert runs
    here out-of-band.
    """
    payload = DocumentIngestionPayload.model_validate(kwargs)
    await document_service.ingest_existing_document(document_id=payload.document_id)
