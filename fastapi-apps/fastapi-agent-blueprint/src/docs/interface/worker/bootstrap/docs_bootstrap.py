from __future__ import annotations

from src.docs.infrastructure.di.docs_container import DocsContainer
from src.docs.interface.worker.tasks import document_ingestion_task


def create_docs_container(docs_container: DocsContainer) -> None:
    docs_container.wire(modules=[document_ingestion_task])


def bootstrap_docs_domain(docs_container: DocsContainer) -> None:
    create_docs_container(docs_container=docs_container)
