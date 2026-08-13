"""One place that knows the whole `BaseRepositoryProtocol` surface.

Test doubles here implement only the handful of methods their test exercises,
which is right — but every domain repository protocol *extends*
`BaseRepositoryProtocol`, so a partial double does not satisfy the annotation it
is passed to. Pyright says so once `tests/` is in its scope:

    "MockAiUsageRepository" is incompatible with protocol "AiUsageRepositoryProtocol"
      "insert_data" is not present
      "insert_datas" is not present
      "select_datas" is not present

Two of those gaps were not deliberate. `MockUserRepository` and
`MockRefreshTokenRepository` were missing exactly one member — `count_datas_by_day`,
added to the protocol in #368 — because a protocol grew and its doubles were never
updated. Nothing caught it: `tests/` was outside the type gate, so a double that
could no longer stand in for the real repository kept passing.

Inheriting this base fixes that class of drift structurally. Every member is
present, so the double satisfies the protocol; every member raises, so a call the
double was never meant to serve fails loudly instead of returning `None` or
`MagicMock()`. And when the protocol next grows, **this file breaks once** rather
than N doubles drifting in silence.

Subclasses override what they need and nothing else:

    class MockUserRepository(FakeRepositoryBase[UserDTO]):
        async def select_data_by_id(self, data_id: int) -> UserDTO:
            return self._rows[data_id]
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any, Generic, TypeVar

from pydantic import BaseModel

if TYPE_CHECKING:
    from datetime import datetime

    from src._core.domain.value_objects.daily_count import DailyCount
    from src._core.domain.value_objects.query_filter import QueryFilter

ReturnDTO = TypeVar("ReturnDTO", bound=BaseModel)


class FakeRepositoryBase(Generic[ReturnDTO]):
    """Every `BaseRepositoryProtocol` member, each raising until overridden.

    Deliberately not a `Protocol` subclass and not abstract: it is a *double*, and
    instantiating it directly should be possible so a test can pass one where the
    code under test never touches the repository.
    """

    def _unsupported(self, method: str) -> NotImplementedError:
        return NotImplementedError(
            f"{type(self).__name__}.{method} is not implemented. This double "
            "covers only what its test exercises — if the code under test now "
            "calls this, implement it here rather than widening the double's "
            "annotation."
        )

    async def insert_data(self, entity: BaseModel) -> ReturnDTO:
        raise self._unsupported("insert_data")

    async def insert_datas(self, entities: Sequence[BaseModel]) -> list[ReturnDTO]:
        raise self._unsupported("insert_datas")

    async def select_datas(self, page: int, page_size: int) -> list[ReturnDTO]:
        raise self._unsupported("select_datas")

    async def select_data_by_id(self, data_id: int) -> ReturnDTO:
        raise self._unsupported("select_data_by_id")

    async def select_datas_by_ids(self, data_ids: list[int]) -> list[ReturnDTO]:
        raise self._unsupported("select_datas_by_ids")

    async def exists_by_id(self, data_id: int) -> bool:
        raise self._unsupported("exists_by_id")

    async def exists_by_fields(
        self,
        filters: Mapping[str, Any],
        *,
        exclude_id: int | None = None,
    ) -> bool:
        raise self._unsupported("exists_by_fields")

    async def existing_values_by_field(
        self,
        field: str,
        values: list[Any],
        *,
        exclude_id: int | None = None,
    ) -> set[Any]:
        raise self._unsupported("existing_values_by_field")

    async def select_datas_with_count(
        self,
        page: int,
        page_size: int,
        query_filter: QueryFilter | None = None,
    ) -> tuple[list[ReturnDTO], int]:
        raise self._unsupported("select_datas_with_count")

    async def update_data_by_data_id(
        self, data_id: int, entity: BaseModel
    ) -> ReturnDTO:
        raise self._unsupported("update_data_by_data_id")

    async def delete_data_by_data_id(self, data_id: int) -> bool:
        raise self._unsupported("delete_data_by_data_id")

    async def count_datas(self) -> int:
        raise self._unsupported("count_datas")

    async def count_datas_by_day(
        self, *, since: datetime, column_name: str = "created_at"
    ) -> list[DailyCount]:
        raise self._unsupported("count_datas_by_day")
