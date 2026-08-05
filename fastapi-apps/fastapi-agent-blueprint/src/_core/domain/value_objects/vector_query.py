from __future__ import annotations

from typing import Any

from src._core.domain.value_objects.value_object import ValueObject


class VectorQuery(ValueObject):
    """Immutable vector similarity search query.

    ``DynamoKey`` counterpart — encapsulates search parameters.

    ``filters`` follows S3 Vectors native filter syntax:
    - Equality: ``{"category": "tech"}`` or ``{"category": {"$eq": "tech"}}``
    - Membership: ``{"category": {"$in": ["tech", "sci"]}}``
    - Negation: ``{"category": {"$ne": "tech"}}``
    - Comparison: ``{"year": {"$gte": 2020}}``
    - Compound: ``{"$and": [{"category": "tech"}, {"year": {"$gte": 2020}}]}``

    **Backend support is not uniform.** The in-memory store implements only the
    equality / membership / negation subset above and raises
    ``NotImplementedError`` for comparison and compound operators — it does not
    silently ignore them (#328 F10). Since ``inmemory`` is the default whenever
    ``VECTOR_STORE_TYPE`` is unset, code written against the full syntax will
    fail loudly on the default backend rather than returning unfiltered results.
    Check the concrete store before relying on an operator outside the subset.
    """

    vector: list[float]
    top_k: int = 10
    filters: dict[str, Any] | None = None
    return_metadata: bool = True
    return_distance: bool = True
