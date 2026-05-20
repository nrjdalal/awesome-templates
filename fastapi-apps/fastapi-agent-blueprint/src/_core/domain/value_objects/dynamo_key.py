from __future__ import annotations

from typing import Literal

from src._core.domain.value_objects.value_object import ValueObject


class DynamoKey(ValueObject):
    """Immutable DynamoDB item key (partition key + optional sort key)."""

    partition_key: str
    sort_key: str | None = None


class SortKeyCondition(ValueObject):
    """Sort key condition for DynamoDB queries."""

    operator: Literal["eq", "begins_with", "between", "lt", "lte", "gt", "gte"]
    value: str
    value2: str | None = None  # Only used with "between"
