from __future__ import annotations

from typing import Any

from src._core.domain.value_objects.value_object import ValueObject


class VectorQuery(ValueObject):
    """Immutable vector similarity search query.

    ``DynamoKey`` counterpart — encapsulates search parameters.

    ``filters`` follows S3 Vectors native filter syntax:
    - Equality: ``{"category": "tech"}``
    - Comparison: ``{"year": {"$gte": 2020}}``
    - Compound: ``{"$and": [{"category": "tech"}, {"year": {"$gte": 2020}}]}``
    """

    vector: list[float]
    top_k: int = 10
    filters: dict[str, Any] | None = None
    return_metadata: bool = True
    return_distance: bool = True
