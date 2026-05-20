from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from src._core.domain.value_objects.vector_query import VectorQuery
from src._core.domain.value_objects.vector_search_result import VectorSearchResult
from src._core.infrastructure.vectors.s3.client import S3VectorClient
from src._core.infrastructure.vectors.vector_model import VectorModel

ReturnDTO = TypeVar("ReturnDTO", bound=BaseModel)

# S3 Vectors API batch limits
_PUT_BATCH_SIZE = 500
_GET_BATCH_SIZE = 100
_DELETE_BATCH_SIZE = 500


class BaseS3VectorStore(Generic[ReturnDTO], ABC):
    """Base vector store for S3 Vectors operations.

    Implements ``BaseVectorStoreProtocol``.
    Constructor takes ``S3VectorClient``, ``VectorModel`` class,
    the return DTO class, and the bucket name.
    """

    def __init__(
        self,
        s3vector_client: S3VectorClient,
        *,
        model: type[VectorModel],
        return_entity: type[ReturnDTO],
        bucket_name: str,
    ) -> None:
        self.s3vector_client = s3vector_client
        self.model = model
        self.return_entity = return_entity
        self.bucket_name = bucket_name

    @property
    def index_name(self) -> str:
        return self.model.__vector_meta__.index_name

    # ------------------------------------------------------------------
    # Abstract: subclass must implement
    # ------------------------------------------------------------------

    @abstractmethod
    def _to_model(self, entity: BaseModel) -> VectorModel:
        """Convert a PutDTO into an VectorModel instance.

        Each domain store must implement this to map its DTO
        fields into key, VectorData, and metadata fields.
        """
        ...

    # ------------------------------------------------------------------
    # VectorStore operations
    # ------------------------------------------------------------------

    async def upsert(self, entities: Sequence[BaseModel]) -> int:
        """Upsert vectors in batches of 500 (S3 Vectors API limit)."""
        total = 0
        for i in range(0, len(entities), _PUT_BATCH_SIZE):
            batch = entities[i : i + _PUT_BATCH_SIZE]
            vectors = [self._to_model(e).to_s3vector() for e in batch]

            async with self.s3vector_client.client() as client:
                await client.put_vectors(
                    vectorBucketName=self.bucket_name,
                    indexName=self.index_name,
                    vectors=vectors,
                )

            total += len(vectors)
        return total

    async def search(self, query: VectorQuery) -> VectorSearchResult[ReturnDTO]:
        """Search vectors by similarity."""
        params: dict[str, Any] = {
            "vectorBucketName": self.bucket_name,
            "indexName": self.index_name,
            "topK": query.top_k,
            "queryVector": {"float32": query.vector},
            "returnMetadata": query.return_metadata,
            "returnDistance": query.return_distance,
        }
        if query.filters:
            params["filter"] = query.filters

        async with self.s3vector_client.client() as client:
            response = await client.query_vectors(**params)

        raw_vectors = response.get("vectors", [])
        items = [self._deserialize_result(v) for v in raw_vectors]
        distances = (
            [v.get("distance", 0.0) for v in raw_vectors]
            if query.return_distance
            else None
        )

        return VectorSearchResult(
            items=items,
            distances=distances,
            count=len(items),
        )

    async def get(self, keys: list[str]) -> list[ReturnDTO]:
        """Get vectors by keys in batches of 100 (S3 Vectors API limit)."""
        results: list[ReturnDTO] = []

        for i in range(0, len(keys), _GET_BATCH_SIZE):
            batch_keys = keys[i : i + _GET_BATCH_SIZE]

            async with self.s3vector_client.client() as client:
                response = await client.get_vectors(
                    vectorBucketName=self.bucket_name,
                    indexName=self.index_name,
                    keys=batch_keys,
                    returnMetadata=True,
                )

            raw_vectors = response.get("vectors", [])
            results.extend(self._deserialize_result(v) for v in raw_vectors)

        return results

    async def delete(self, keys: list[str]) -> bool:
        """Delete vectors by keys in batches of 500 (S3 Vectors API limit)."""
        for i in range(0, len(keys), _DELETE_BATCH_SIZE):
            batch_keys = keys[i : i + _DELETE_BATCH_SIZE]

            async with self.s3vector_client.client() as client:
                await client.delete_vectors(
                    vectorBucketName=self.bucket_name,
                    indexName=self.index_name,
                    keys=batch_keys,
                )

        return True

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _deserialize_result(self, raw: dict[str, Any]) -> ReturnDTO:
        """Convert S3 Vectors response item to ReturnDTO.

        Default: validates metadata dict into ReturnDTO.
        Override in subclass if custom deserialization is needed.
        """
        metadata = raw.get("metadata", {})
        return self.return_entity.model_validate(metadata)
