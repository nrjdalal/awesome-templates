from __future__ import annotations

from src._core.application.dtos.base_payload import BasePayload
from src._core.config import settings

# Shared contract between the dispatcher (router) and the consumer (worker
# task). Kept alongside the payload so both sides import the same name.
DOCS_INGEST_DOCUMENT_TASK_NAME = f"{settings.task_name_prefix}.docs.ingest_document"


class DocumentIngestionPayload(BasePayload):
    """Payload for async (re-)ingestion of an existing document row."""

    document_id: int
    title: str | None = None
    content: str | None = None
    source: str | None = None
