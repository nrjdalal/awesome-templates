from __future__ import annotations

from src._core.domain.value_objects.value_object import ValueObject


class QueryFilter(ValueObject):
    """Immutable filter object for paginated queries.

    Consolidates sort/search params into a single object so that
    BaseRepository.select_datas_with_count keeps a clean signature.
    """

    sort_field: str | None = None
    sort_order: str = "desc"
    search_query: str | None = None
    search_fields: list[str] | None = None
