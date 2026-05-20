from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src._core.domain.dtos.rag import BaseChunkDTO
from src._core.infrastructure.vectors.s3.base_store import BaseS3VectorStore
from src._core.infrastructure.vectors.s3.client import S3VectorClient
from src._core.infrastructure.vectors.vector_model import VectorData
from src.docs.infrastructure.vectors.document_chunk_vector_model import (
    DocumentChunkVectorModel,
)


class DocumentChunkS3VectorStore(BaseS3VectorStore[BaseChunkDTO]):
    """S3 Vectors backend for docs chunks."""

    def __init__(self, s3vector_client: S3VectorClient, bucket_name: str) -> None:
        super().__init__(
            s3vector_client=s3vector_client,
            model=DocumentChunkVectorModel,
            return_entity=BaseChunkDTO,
            bucket_name=bucket_name,
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

    def _deserialize_result(self, raw: dict[str, Any]) -> BaseChunkDTO:
        """Include the store ``key`` as ``chunk_id`` on the returned DTO."""
        metadata = dict(raw.get("metadata", {}))
        metadata.setdefault("chunk_id", raw.get("key", ""))
        return self.return_entity.model_validate(metadata)
