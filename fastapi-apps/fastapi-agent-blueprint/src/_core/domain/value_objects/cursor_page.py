from __future__ import annotations

from typing import Generic, TypeVar

from src._core.domain.value_objects.value_object import ValueObject

T = TypeVar("T")


class CursorPage(ValueObject, Generic[T]):
    """Cursor-based pagination result for DynamoDB queries."""

    items: list[T]
    next_cursor: str | None = None
    count: int  # Number of items in this page (not total)
