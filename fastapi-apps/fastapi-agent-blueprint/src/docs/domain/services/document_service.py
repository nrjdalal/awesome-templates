from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from src._core.common.text_utils import chunk_text
from src._core.domain.dtos.rag import BaseChunkDTO
from src._core.domain.protocols.embedding_protocol import BaseEmbeddingProtocol
from src._core.domain.protocols.vector_store_protocol import BaseVectorStoreProtocol
from src._core.domain.services.base_service import BaseService
from src._core.domain.value_objects.vector_query import VectorQuery
from src._core.exceptions.base_exception import BaseCustomException
from src.docs.domain.dtos.document_dto import DocumentDTO
from src.docs.domain.exceptions.docs_exceptions import IngestionFailedException
from src.docs.domain.protocols.document_repository_protocol import (
    DocumentRepositoryProtocol,
)
from src.docs.interface.server.schemas.docs_schema import (
    CreateDocumentRequest,
    UpdateDocumentRequest,
)

logger = logging.getLogger(__name__)

# Simple inline threshold — small docs ingest synchronously; large docs
# should go through the worker (see ``document_ingestion_task``).
_SYNC_INGEST_CHAR_THRESHOLD = 20_000


class DocumentService(
    BaseService[CreateDocumentRequest, UpdateDocumentRequest, DocumentDTO]
):
    """Docs domain document service.

    On ``create_data`` the new row is immediately put through the
    ingestion pipeline (chunk → embed → upsert) and the resulting
    ``chunk_count`` is persisted back on the row.
    """

    def __init__(
        self,
        document_repository: DocumentRepositoryProtocol,
        embedder: BaseEmbeddingProtocol,
        chunk_vector_store: BaseVectorStoreProtocol[BaseChunkDTO],
    ) -> None:
        super().__init__(repository=document_repository)
        self._document_repository = document_repository
        self._embedder = embedder
        self._chunk_vector_store = chunk_vector_store

    # ------------------------------------------------------------------
    # CRUD overrides
    # ------------------------------------------------------------------

    async def create_data(self, entity: CreateDocumentRequest) -> DocumentDTO:
        created = await super().create_data(entity=entity)
        try:
            chunk_count = await self._ingest(created)
        except Exception as exc:
            logger.exception("Docs ingestion failed for document %s", created.id)
            # Best-effort cleanup so the caller does not see a phantom row.
            await self._document_repository.delete_data_by_data_id(data_id=created.id)
            if isinstance(exc, BaseCustomException):
                raise
            raise IngestionFailedException("ingestion pipeline error") from exc

        if chunk_count != created.chunk_count:
            created = await super().update_data_by_data_id(
                data_id=created.id,
                entity=UpdateDocumentRequest(chunk_count=chunk_count),
            )
        return created

    async def create_without_ingestion(
        self, entity: CreateDocumentRequest
    ) -> DocumentDTO:
        """Create the document row only — no chunking, no embedding.

        Caller is responsible for dispatching the ingestion task (see
        ``ingest_document_task``) after the row is persisted. Used for
        large documents where inline ingestion would exceed the request
        budget; the chunk_count stays at 0 until the worker catches up.
        """
        return await super().create_data(entity=entity)

    async def delete_data_by_data_id(self, data_id: int) -> bool:
        """Delete the document row and best-effort purge its vectors."""
        doc = await self._document_repository.select_data_by_id(data_id=data_id)
        await self._purge_vectors_for_document(doc)
        return await super().delete_data_by_data_id(data_id=data_id)

    # ------------------------------------------------------------------
    # Ingestion pipeline (reused by worker task)
    # ------------------------------------------------------------------

    async def ingest_existing_document(self, document_id: int) -> int:
        """Re-run ingestion against an already-persisted document."""
        doc = await self._document_repository.select_data_by_id(data_id=document_id)
        await self._purge_vectors_for_document(doc)
        chunk_count = await self._ingest(doc)
        if chunk_count != doc.chunk_count:
            await super().update_data_by_data_id(
                data_id=doc.id,
                entity=UpdateDocumentRequest(chunk_count=chunk_count),
            )
        return chunk_count

    def should_ingest_sync(self, content: str) -> bool:
        """Return True when inline ingestion is acceptable for ``content``."""
        return len(content) <= _SYNC_INGEST_CHAR_THRESHOLD

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _ingest(self, document: DocumentDTO) -> int:
        chunks = chunk_text(document.content)
        if not chunks:
            return 0

        vectors = await self._embedder.embed_batch(chunks)
        entities = [
            _ChunkUpsertPayload(
                chunk=BaseChunkDTO(
                    content=text,
                    chunk_index=index,
                    source_id=str(document.id),
                    source_title=document.title,
                ),
                vector=vector,
            )
            for index, (text, vector) in enumerate(zip(chunks, vectors, strict=True))
        ]
        await self._chunk_vector_store.upsert(entities)
        return len(entities)

    async def _purge_vectors_for_document(self, document: DocumentDTO) -> None:
        """Best-effort: drop any vectors tied to this document.

        Uses the filter-based search path to collect keys. Cap at a
        generous upper bound so the call stays bounded — full
        reconciliation is a follow-up concern.
        """
        if document.chunk_count <= 0:
            return
        try:
            probe_vector = [0.0] * self._embedder.dimension
            result = await self._chunk_vector_store.search(
                VectorQuery(
                    vector=probe_vector,
                    top_k=max(document.chunk_count, 10),
                    filters={"source_id": {"$eq": str(document.id)}},
                    return_distance=False,
                )
            )
            keys = [chunk.chunk_id for chunk in result.items if chunk.chunk_id]
            if keys:
                await self._chunk_vector_store.delete(keys)
        except Exception:
            logger.warning(
                "Docs vector purge failed for document %s (continuing)",
                document.id,
                exc_info=True,
            )


class _ChunkUpsertPayload(BaseModel):
    """Lightweight carrier passed to ``vector_store.upsert``.

    Bundles the chunk DTO with its embedding so the vector store stays
    free of any embedder coupling.
    """

    chunk: BaseChunkDTO
    vector: list[float] = Field(default_factory=list)
