from __future__ import annotations

from typing import Generic, TypeVar

from src._core.domain.value_objects.value_object import ValueObject

T = TypeVar("T")


class VectorSearchResult(ValueObject, Generic[T]):
    """Result of a vector similarity search.

    ``CursorPage`` counterpart — vector search uses top-K instead of cursor.
    ``distances`` is present only when ``return_distance=True`` in the query.
    ``items[i]`` corresponds to ``distances[i]``.
    """

    items: list[T]
    distances: list[float] | None = None
    count: int
