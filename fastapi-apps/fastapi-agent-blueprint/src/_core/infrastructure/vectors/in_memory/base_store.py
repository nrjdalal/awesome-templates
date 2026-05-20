from __future__ import annotations

import math
from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from src._core.domain.value_objects.vector_query import VectorQuery
from src._core.domain.value_objects.vector_search_result import VectorSearchResult
from src._core.infrastructure.vectors.vector_model import VectorModel

ReturnDTO = TypeVar("ReturnDTO", bound=BaseModel)


class BaseInMemoryVectorStore(Generic[ReturnDTO], ABC):
    """Process-local vector store mirroring BaseS3VectorStore's contract.

    Implements ``BaseVectorStoreProtocol``. Intended for quickstart
    demos, unit tests, and zero-config local development. Vectors live
    in a plain dict and are lost on process restart.

    Filter semantics support the S3 Vectors ``$eq`` / ``$in`` subset
    so domain code written against the S3 backend remains portable.
    """

    def __init__(
        self,
        *,
        model: type[VectorModel],
        return_entity: type[ReturnDTO],
    ) -> None:
        self.model = model
        self.return_entity = return_entity
        self._store: dict[str, dict[str, Any]] = {}

    @abstractmethod
    def _to_model(self, entity: BaseModel) -> VectorModel:
        """Convert a PutDTO into a VectorModel — same contract as S3 backend."""
        ...

    async def upsert(self, entities: Sequence[BaseModel]) -> int:
        for entity in entities:
            raw = self._to_model(entity).to_s3vector()
            self._store[raw["key"]] = {
                "vector": list(raw["data"]["float32"]),
                "metadata": raw["metadata"],
            }
        return len(entities)

    async def search(self, query: VectorQuery) -> VectorSearchResult[ReturnDTO]:
        scored: list[tuple[float, dict[str, Any]]] = []
        for record in self._store.values():
            if query.filters and not _matches_filters(
                record["metadata"], query.filters
            ):
                continue
            distance = _cosine_distance(query.vector, record["vector"])
            scored.append((distance, record["metadata"]))

        scored.sort(key=lambda pair: pair[0])
        top = scored[: query.top_k]

        items = [self.return_entity.model_validate(meta) for _, meta in top]
        distances = [dist for dist, _ in top] if query.return_distance else None
        return VectorSearchResult(items=items, distances=distances, count=len(items))

    async def get(self, keys: list[str]) -> list[ReturnDTO]:
        return [
            self.return_entity.model_validate(self._store[key]["metadata"])
            for key in keys
            if key in self._store
        ]

    async def delete(self, keys: list[str]) -> bool:
        for key in keys:
            self._store.pop(key, None)
        return True


def _matches_filters(metadata: dict[str, Any], filters: dict[str, Any]) -> bool:
    for field, condition in filters.items():
        value = metadata.get(field)
        if isinstance(condition, dict):
            if "$eq" in condition and value != condition["$eq"]:
                return False
            if "$in" in condition and value not in condition["$in"]:
                return False
            if "$ne" in condition and value == condition["$ne"]:
                return False
        else:
            if value != condition:
                return False
    return True


def _cosine_distance(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        return 1.0
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for x, y in zip(a, b, strict=True):
        dot += x * y
        norm_a += x * x
        norm_b += y * y
    if norm_a == 0.0 or norm_b == 0.0:
        return 1.0
    return 1.0 - (dot / (math.sqrt(norm_a) * math.sqrt(norm_b)))
