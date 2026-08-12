from __future__ import annotations

from abc import ABC
from collections.abc import Mapping
from datetime import date, datetime
from typing import TYPE_CHECKING, Any, Generic, TypeVar

import structlog
from pydantic import BaseModel
from sqlalchemy import Date, DateTime, String, func, or_, select
from sqlalchemy.orm import InstrumentedAttribute

from src._core.domain.value_objects.daily_count import DailyCount
from src._core.exceptions.base_exception import BaseCustomException
from src._core.infrastructure.persistence.rdb.database import Base, Database
from src._core.infrastructure.persistence.rdb.exceptions import DatabaseException

if TYPE_CHECKING:
    from src._core.domain.value_objects.query_filter import QueryFilter

_logger = structlog.stdlib.get_logger(__name__)

# Bind-parameter ceiling for the defaults reload. Well under every driver's
# limit; the public batch endpoint caps at 100 anyway.
_DEFAULTS_REFRESH_CHUNK = 500

ReturnDTO = TypeVar("ReturnDTO", bound=BaseModel)


class BaseRepository(Generic[ReturnDTO], ABC):
    def __init__(
        self,
        database: Database,
        *,
        model: type[Base],
        return_entity: type[ReturnDTO],
    ) -> None:
        self.database = database
        self.model = model
        self.return_entity = return_entity

    async def insert_data(self, entity: BaseModel) -> ReturnDTO:
        async with self.database.session() as session:
            data = self.model(**entity.model_dump(exclude_none=True))
            session.add(data)
            await session.commit()
            await session.refresh(data)
            return self.return_entity.model_validate(data, from_attributes=True)

    async def insert_datas(self, entities: list[BaseModel]) -> list[ReturnDTO]:
        async with self.database.session() as session:
            datas = [
                self.model(**entity.model_dump(exclude_none=True))
                for entity in entities
            ]
            session.add_all(datas)
            await session.flush()

            # Load server-side defaults with ONE query, before commit.
            #
            # Where insert_returning is False (MySQL/MariaDB today) the
            # server_default columns are unloaded after flush, and the
            # synchronous access inside model_validate would trigger a lazy
            # refresh with no greenlet — MissingGreenlet, which
            # Database.session() turns into a 500. ADR 058 D1.
            #
            # Two shapes were rejected. A per-instance session.refresh() loop is
            # INSERT x N + SELECT x N: on the public batch endpoint (100 items)
            # that is 100 sequential round-trips. Doing it *after* commit is
            # worse than slow — a refresh that fails then returns a 500 for rows
            # already written, which is the exact failure this fix exists to
            # remove. Building the DTOs before commit closes that window.
            await self._populate_defaults(session, datas)
            results = [
                self.return_entity.model_validate(data, from_attributes=True)
                for data in datas
            ]
            await session.commit()
            return results

    async def select_datas(self, page: int, page_size: int) -> list[ReturnDTO]:
        async with self.database.session() as session:
            result = await session.execute(
                select(self.model)
                .order_by(*self._stable_order())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
            datas = result.scalars().all()

            return [
                self.return_entity.model_validate(data, from_attributes=True)
                for data in datas
            ]

    async def select_data_by_id(self, data_id: int) -> ReturnDTO:
        id_column = self._id_column()
        async with self.database.session() as session:
            result = await session.execute(
                select(self.model).filter(id_column == data_id)
            )
            data = result.scalar_one_or_none()
            if not data:
                raise BaseCustomException(
                    status_code=404, message=f"Data with ID [ {data_id} ] not found"
                )
            return self.return_entity.model_validate(data, from_attributes=True)

    async def select_datas_by_ids(self, data_ids: list[int]) -> list[ReturnDTO]:
        if not data_ids:
            return []
        id_column = self._id_column()
        async with self.database.session() as session:
            result = await session.execute(
                select(self.model).where(id_column.in_(data_ids))
            )
            datas = result.scalars().all()
            return [
                self.return_entity.model_validate(data, from_attributes=True)
                for data in datas
            ]

    async def exists_by_id(self, data_id: int) -> bool:
        id_column = self._id_column()
        async with self.database.session() as session:
            result = await session.execute(
                select(id_column).where(id_column == data_id).limit(1)
            )
            return result.scalar_one_or_none() is not None

    async def exists_by_fields(
        self,
        filters: Mapping[str, Any],
        *,
        exclude_id: int | None = None,
    ) -> bool:
        if not filters:
            return False
        id_column = self._id_column()
        async with self.database.session() as session:
            query = select(id_column).where(
                *[
                    self._column_for_field(field) == value
                    for field, value in filters.items()
                ]
            )
            if exclude_id is not None:
                query = query.where(id_column != exclude_id)
            result = await session.execute(query.limit(1))
            return result.scalar_one_or_none() is not None

    async def existing_values_by_field(
        self,
        field: str,
        values: list[Any],
        *,
        exclude_id: int | None = None,
    ) -> set[Any]:
        value_set = {value for value in values if value is not None}
        if not value_set:
            return set()
        column = self._column_for_field(field)
        id_column = self._id_column()
        async with self.database.session() as session:
            query = select(column).where(column.in_(value_set))
            if exclude_id is not None:
                query = query.where(id_column != exclude_id)
            result = await session.execute(query)
            return set(result.scalars().all())

    async def select_datas_with_count(
        self,
        page: int,
        page_size: int,
        query_filter: QueryFilter | None = None,
    ) -> tuple[list[ReturnDTO], int]:
        """Fetch data and count in a single session to optimize connection pool usage."""
        async with self.database.session() as session:
            query = select(self.model)
            count_query = select(func.count()).select_from(self.model)

            sorted_explicitly = False
            if query_filter:
                # Apply search filter
                if query_filter.search_query and query_filter.search_fields:
                    conditions = self._search_conditions(
                        query_filter.search_fields, query_filter.search_query
                    )
                    query = query.where(or_(*conditions))
                    count_query = count_query.where(or_(*conditions))

                # Apply sorting. _column_for_field is the single resolver — the
                # sort path used to do bare hasattr/getattr and then call
                # .desc() on whatever came back, which for a method or a class
                # attribute produced an opaque 500 (ADR 058 D4).
                if query_filter.sort_field:
                    column = self._column_for_field(query_filter.sort_field)
                    ordering = [
                        column.asc()
                        if query_filter.sort_order == "asc"
                        else column.desc()
                    ]
                    # The explicit column is the *primary* key, not the only
                    # one. Dropping the tiebreaker entirely put tie order back
                    # in the engine's hands, so sorting by a non-unique column
                    # (created_at, status) could still repeat or skip rows
                    # across pages — the defect this was meant to remove.
                    # Skipped when the caller already sorted by the PK, so the
                    # same column is not ordered twice in opposite directions.
                    if column is not self._id_column():
                        ordering.extend(self._stable_order())
                    query = query.order_by(*ordering)
                    sorted_explicitly = True

            if not sorted_explicitly:
                # Same reason as select_datas: an unordered offset page can
                # repeat or skip rows. Applied only when the caller did not
                # sort, so an explicit sort still wins (ADR 058 D2).
                query = query.order_by(*self._stable_order())

            result = await session.execute(
                query.offset((page - 1) * page_size).limit(page_size)
            )
            datas = result.scalars().all()

            count_result = await session.execute(count_query)
            total_count = count_result.scalar_one()

            return [
                self.return_entity.model_validate(data, from_attributes=True)
                for data in datas
            ], total_count

    async def update_data_by_data_id(
        self, data_id: int, entity: BaseModel
    ) -> ReturnDTO:
        id_column = self._id_column()
        async with self.database.session() as session:
            result = await session.execute(
                select(self.model).filter(id_column == data_id)
            )
            data = result.scalar_one_or_none()
            if not data:
                raise BaseCustomException(
                    status_code=404, message=f"Data with ID [ {data_id} ] not found"
                )
            for key, value in entity.model_dump(exclude_none=True).items():
                setattr(data, key, value)
            await session.commit()
            await session.refresh(data)
            return self.return_entity.model_validate(data, from_attributes=True)

    async def delete_data_by_data_id(self, data_id: int) -> bool:
        id_column = self._id_column()
        async with self.database.session() as session:
            result = await session.execute(
                select(self.model).filter(id_column == data_id)
            )
            data = result.scalar_one_or_none()
            if not data:
                raise BaseCustomException(
                    status_code=404, message=f"Data with ID [ {data_id} ] not found"
                )
            await session.delete(data)
            await session.commit()
            return True

    async def count_datas(self) -> int:
        async with self.database.session() as session:
            result = await session.execute(select(func.count()).select_from(self.model))
            return result.scalar_one()

    async def count_datas_by_day(
        self, *, since: datetime, column_name: str = "created_at"
    ) -> list[DailyCount]:
        """Rows per calendar day at or after ``since``, oldest day first.

        Two dialect differences are absorbed here rather than left to callers,
        per the ADR 058 guarantee that ``BaseRepository`` behaves the same on
        PostgreSQL, MySQL and SQLite.

        **1. How the day is truncated.** ``func.date(column)`` is used, and the
        alternatives were measured rather than assumed:

        =============================== ========= ============
        expression                      SQLite    PostgreSQL
        =============================== ========= ============
        ``cast(column, Date)``          **fails** works
        ``func.date(column)``           works     works
        ``substr(cast(col, String), …)`` works     works
        =============================== ========= ============

        ``cast(column, Date)`` raises ``TypeError: fromisoformat: argument must
        be str`` on SQLite, which is the quickstart default — so the obvious
        cast is the one that breaks the most common configuration. Do not
        "simplify" this to a cast. MySQL's ``DATE()`` is long-standing, but note
        ADR 058's stated limit: no real MySQL runs in CI, so that leg rests on
        documentation rather than a test.

        **2. What Python type comes back.** ``func.date`` returns ``str`` on
        SQLite and ``datetime.date`` on PostgreSQL (both measured). Callers get
        ``datetime.date`` on every engine because :meth:`_as_date` normalises it;
        without that, a caller formatting the value would work on one engine and
        raise on another.

        Days with no rows are **absent**, not zero-filled — see
        :class:`DailyCount`. Fails closed with a curated 400 when the column
        cannot carry the aggregate, following the ``DB_SEARCH_FIELD_UNUSABLE``
        precedent (ADR 058 D3) rather than returning an empty list that reads
        like "no data".

        ``since`` must match the column's tz-awareness. Every timestamp column
        in-tree today is naive ``DateTime`` (``user.created_at``,
        ``ai_usage.occurred_at``), so a naive ``since`` is what callers pass; a
        fork that switches a column to ``DateTime(timezone=True)`` has to pass an
        aware one. No coercion happens here because guessing which the caller
        meant is worse than the comparison failing.
        """
        column = getattr(self.model, column_name, None)
        if not isinstance(column, InstrumentedAttribute) or not isinstance(
            column.type, (Date, DateTime)
        ):
            raise DatabaseException(
                status_code=400,
                message=(
                    f"Field [ {column_name} ] cannot carry a date-grouped count; "
                    "a Date or DateTime column is required"
                ),
                error_code="DB_TIME_FIELD_UNUSABLE",
            )

        day = func.date(column)
        async with self.database.session() as session:
            result = await session.execute(
                select(day.label("day"), func.count().label("count"))
                .where(column >= since)
                .group_by(day)
                .order_by(day)
            )
            return [
                DailyCount(day=self._as_date(row.day), count=row.count)
                for row in result
            ]

    @staticmethod
    def _as_date(value: object) -> date:
        """Normalise a grouped day value to ``datetime.date`` across engines."""
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            return date.fromisoformat(value[:10])
        raise DatabaseException(
            status_code=500,
            message=f"Unsupported grouped-day type {type(value).__name__}",
            error_code="DB_INTERNAL_ERROR",
        )

    async def _populate_defaults(self, session, datas: list) -> None:
        """Load server-side defaults for freshly flushed instances.

        One ``populate_existing`` SELECT over the flushed ids rather than a
        refresh per instance. Chunked because a batch large enough to exceed the
        driver's bind-parameter limit would otherwise fail on the query rather
        than on the insert.
        """
        if not datas:
            return
        ids = [data.id for data in datas]
        id_column = self._id_column()
        for start in range(0, len(ids), _DEFAULTS_REFRESH_CHUNK):
            await session.execute(
                select(self.model)
                .where(id_column.in_(ids[start : start + _DEFAULTS_REFRESH_CHUNK]))
                .execution_options(populate_existing=True)
            )

    def _stable_order(self) -> tuple[InstrumentedAttribute, ...]:
        """A deterministic tiebreaker for offset pagination (ADR 058 D2).

        Offset paging over an unordered result set can repeat or skip rows,
        because the engine is free to return a different order per query. The
        flagship list endpoint passed `query_filter=None`, so it did exactly
        that; `ai_usage_repository` had hand-fixed it locally, which is evidence
        the contract was missing rather than the code.

        The primary key is the tiebreaker: always present, always unique, and
        already indexed. Descending so a default page is newest-first, matching
        what the domains that fixed this themselves chose. Order is API-visible —
        see the CHANGELOG entry.
        """
        return (self._id_column().desc(),)

    def _search_conditions(self, fields: list[str], term: str) -> list:
        """Build ILIKE conditions, rejecting fields that cannot carry one.

        Fails closed. Previously every non-`String` field was dropped silently
        and, if none survived, no WHERE clause was added at all — so a search
        returned the **entire table** with `total_items` set to the full count.
        A search that cannot be honoured is an error, not an unfiltered list
        (ADR 058 D3).

        A field that is usable is still used even when a sibling is not: dropping
        the unusable half is what failed open, but rejecting a request where some
        field works would be over-correction.
        """
        conditions = []
        unusable = []
        for field_name in fields:
            column = getattr(self.model, field_name, None)
            if not isinstance(column, InstrumentedAttribute):
                unusable.append(field_name)
                continue
            if not isinstance(column.type, String):
                unusable.append(field_name)
                continue
            conditions.append(column.ilike(f"%{term}%"))
        if not conditions:
            raise DatabaseException(
                status_code=400,
                message=(
                    f"No searchable text field among {sorted(fields)}; "
                    "search requires at least one String column"
                ),
                error_code="DB_SEARCH_FIELD_UNUSABLE",
            )
        if unusable:
            _logger.info(
                "search_fields_skipped",
                skipped=sorted(unusable),
                used=len(conditions),
            )
        return conditions

    def _column_for_field(self, field: str) -> InstrumentedAttribute:
        """The single field resolver (ADR 058 D4).

        A curated 400 rather than ``ValueError``: the field name arrives from a
        query string, and the generic handler turns a bare ValueError into
        INTERNAL_SERVER_ERROR — a 500 plus an operator page for a malformed
        request.
        """
        column = getattr(self.model, field, None)
        if not isinstance(column, InstrumentedAttribute):
            raise DatabaseException(
                status_code=400,
                message=f"Unknown model field: {field}",
                error_code="DB_UNKNOWN_FIELD",
            )
        return column

    def _id_column(self) -> InstrumentedAttribute:
        return self._column_for_field("id")
