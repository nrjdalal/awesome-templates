from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class AdminCrudServiceProtocol(Protocol):
    """Minimal CRUD service contract consumed by ``BaseAdminPage``.

    Any ``BaseService`` subclass satisfies this protocol automatically since
    ``get_datas`` and ``get_data_by_data_id`` are provided by ``BaseService``.

    Typing the service provider as ``Callable[[], AdminCrudServiceProtocol]``
    gives pyright/mypy enough information to flag wiring mismatches without
    requiring a full generic signature with PaginationInfo and ReturnDTO.
    """

    async def get_datas(
        self, page: int, page_size: int, query_filter: Any
    ) -> tuple[list[Any], Any]: ...

    async def get_data_by_data_id(self, data_id: int) -> Any: ...
