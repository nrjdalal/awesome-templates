from __future__ import annotations

import math
from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from src._core.domain.value_objects.vector_query import VectorQuery
from src._core.domain.value_objects.vector_search_result import VectorSearchResult
from src._core.infrastructure.vectors.in_memory.exceptions import (
    VectorFilterUnsupportedException,
)
from src._core.infrastructure.vectors.vector_model import VectorModel

ReturnDTO = TypeVar("ReturnDTO", bound=BaseModel)


class BaseInMemoryVectorStore(Generic[ReturnDTO], ABC):
    """Process-local vector store mirroring BaseS3VectorStore's contract.

    Implements ``BaseVectorStoreProtocol``. Intended for quickstart
    demos, unit tests, and zero-config local development. Vectors live
    in a plain dict and are lost on process restart.

    Filter semantics support the S3 Vectors ``$eq`` / ``$in`` / ``$ne``
    subset so domain code written against the S3 backend remains
    portable. Operators outside that subset — ``$gte``, ``$lt``,
    ``$and`` and friends — raise ``NotImplementedError`` rather than
    being ignored; see ``_matches_filters`` for why the previous silent
    behaviour was unsafe in both directions (#328 F10).
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
        # Before the scan, so the rejection does not depend on how many records
        # happen to be stored or on which condition eliminates them first.
        validate_filters(query.filters)

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


# The operator subset this store implements. S3 Vectors itself supports
# $eq/$ne/$gt/$gte/$lt/$lte/$in/$nin/$exists/$and/$or, and this repo's S3 store
# passes `query.filters` through to `query_vectors` untouched — so the gap here
# is an unimplemented subset of the backend, not a deliberate ceiling. Widening
# it is a fine follow-up; silently ignoring what is missing is not.
_SUPPORTED_OPERATORS = frozenset({"$eq", "$in", "$ne"})


def validate_filters(filters: dict[str, Any] | None) -> None:
    """Reject filter operators this store cannot honour, before any scanning.

    Called once at :meth:`search` entry rather than per record. Inside the
    record loop the check is data-dependent and therefore not a guarantee: an
    empty store never evaluates a filter at all, and an earlier condition that
    eliminates every record short-circuits before a later unsupported operator
    is ever seen. ``{"category": "missing", "year": {"$gte": 2020}}`` returned an
    empty result set instead of raising (#328 F10 follow-up).

    Raises :class:`VectorFilterUnsupportedException` (a curated 400), never a
    bare ``NotImplementedError`` — the filter arrives from a public request body
    and an untranslated error would surface as a 500.
    """
    if not filters:
        return
    supported = sorted(_SUPPORTED_OPERATORS)
    for field, condition in filters.items():
        if field.startswith("$"):
            # Compound/top-level operators ($and, $or, $not) are not field
            # names, so the bare-equality branch would compare None against a
            # list and silently match nothing.
            raise VectorFilterUnsupportedException([field], supported)
        if isinstance(condition, dict):
            unsupported = set(condition) - _SUPPORTED_OPERATORS
            if unsupported:
                raise VectorFilterUnsupportedException(
                    sorted(unsupported), supported, field=field
                )


def _matches_filters(metadata: dict[str, Any], filters: dict[str, Any]) -> bool:
    """Evaluate a validated filter mapping against one record's metadata.

    Assumes :func:`validate_filters` has already run — it handles only the
    supported subset and does not re-check. The two silent behaviours this
    replaced went in opposite directions, and the fail-open one was the
    dangerous half: an unsupported operator was *discarded*, so a tenant or ACL
    filter written against the documented ``VectorQuery`` contract returned
    other tenants' rows.
    """
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
