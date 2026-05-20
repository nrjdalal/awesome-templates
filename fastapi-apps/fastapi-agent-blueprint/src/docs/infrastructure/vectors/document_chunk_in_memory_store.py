from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src._core.domain.dtos.rag import BaseChunkDTO
from src._core.infrastructure.vectors.in_memory.base_store import (
    BaseInMemoryVectorStore,
)
from src._core.infrastructure.vectors.vector_model import VectorData
from src.docs.infrastructure.vectors.document_chunk_vector_model import (
    DocumentChunkVectorModel,
)


class DocumentChunkInMemoryVectorStore(BaseInMemoryVectorStore[BaseChunkDTO]):
    """Process-local vector store for docs chunks.

    Default backend when ``VECTOR_STORE_TYPE`` is unset or ``"inmemory"``.
    Mirrors the S3 backend's serialisation so ``_to_model`` is shared.
    """

    def __init__(self) -> None:
        super().__init__(
            model=DocumentChunkVectorModel,
            return_entity=BaseChunkDTO,
        )

    def _to_model(self, entity: BaseModel) -> DocumentChunkVectorModel:
        data = entity.model_dump()
        chunk = data["chunk"]
        vector = data["vector"]
        return DocumentChunkVectorModel(
            data=VectorData(float32=list(vector)),
            source_id=chunk["source_id"],
            source_title=chunk["source_title"],
            content=chunk["content"],
            chunk_index=chunk["chunk_index"],
        )

    async def search(self, query):  # noqa: ANN001 - see base class signature
        result = await super().search(query)
        _rehydrate_chunk_ids(result.items, self._store)
        return result

    async def get(self, keys: list[str]) -> list[BaseChunkDTO]:
        items = await super().get(keys)
        for key, item in zip(keys, items, strict=False):
            item.chunk_id = key
        return items


def _rehydrate_chunk_ids(
    items: list[BaseChunkDTO], store: dict[str, dict[str, Any]]
) -> None:
    """Best-effort: attach the store key back onto each DTO.

    Matches on ``(source_id, chunk_index)`` — unique per source.
    """
    lookup: dict[tuple[str, int], str] = {}
    for key, record in store.items():
        meta = record["metadata"]
        lookup[(meta["source_id"], meta["chunk_index"])] = key

    for item in items:
        key = lookup.get((item.source_id, item.chunk_index))
        if key:
            item.chunk_id = key
