"""What `BaseRepository` guarantees regardless of `DATABASE_ENGINE` (#325, ADR 058).

Five defects in one base class that six domains and nine examples inherit, so
each ships N times. The ADR exists because "what does this guarantee across
engines?" had no answer, which is why the answers diverged.

**F3 — `insert_datas` 500s on any backend without RETURNING.** `insert_data`
(singular) does `commit()` then `refresh()`. `insert_datas` (bulk) does
`add_all` → `flush` → `commit` and then `model_validate(..., from_attributes=True)`
with **no refresh**. On dialects that support RETURNING, SQLAlchemy's
`eager_defaults="auto"` fetches `server_default` columns during the INSERT, so it
happens to work. Where `insert_returning` is False, `created_at`/`updated_at` are
never loaded, the synchronous attribute access inside `model_validate` triggers a
lazy refresh with no greenlet, and `Database.session()`'s catch-all turns
`MissingGreenlet` into a 500. Measured:

    mysql       prefer_eager=False insert_returning=False
    aiomysql    prefer_eager=False insert_returning=False
    postgresql  prefer_eager=True  insert_returning=True
    sqlite      prefer_eager=True  insert_returning=True

The rows are **already committed** when the exception fires, so the client sees a
failure for a write that succeeded and retries into duplicate-key errors. 16
model files carry `server_default=func.now()`.

These tests force `insert_returning=False` on SQLite rather than adding a MySQL
CI leg (a deliberate scope decision — see ADR 058 for the limitation this leaves).

**Unordered offset pagination.** `select_datas` and the no-sort branch of
`select_datas_with_count` page a result set with no `ORDER BY`, so rows can repeat
or vanish across pages. `ai_usage_repository` hand-fixed this locally, which is
evidence the contract was missing rather than the code.

**`related_entities`.** `session.refresh(datas, [...])` passes a *list* where
`AsyncSession.refresh` takes one instance. The repo declares no `relationship()`
anywhere and the attribute is defined nowhere, so the branch is dead — and would
raise the moment it were not.

**Search fails open.** Non-`String` search fields are dropped silently; if none
survive, no WHERE clause is added and the whole table is returned with
`total_items` set to the full count.

**Two field resolvers.** `_column_for_field` validates and raises;
the sort path used bare `hasattr` + `getattr` and called `.desc()` on whatever came
back, producing an opaque 500.
"""

from __future__ import annotations

from datetime import date, datetime

import pytest
from sqlalchemy import update

from src._core.domain.value_objects.query_filter import QueryFilter
from src._core.infrastructure.persistence.rdb.exceptions import DatabaseException
from src.user.domain.dtos.user_dto import UserDTO
from src.user.infrastructure.database.models.user_model import UserModel
from src.user.infrastructure.repositories.user_repository import UserRepository
from tests.factories.user_factory import make_create_user_request


def _request(username: str):
    """Unique username *and* email — both carry unique constraints."""
    return make_create_user_request(username=username, email=f"{username}@example.com")


@pytest.fixture
def repository(test_db):
    return UserRepository(database=test_db)


@pytest.fixture
def no_returning(test_db, monkeypatch):
    """Make the engine behave like MySQL for INSERT.

    Forces the dialect flags that decide whether `server_default` columns are
    fetched during the INSERT. This is the whole reason the defect is invisible
    on the two engines CI runs.
    """
    dialect = test_db.async_engine.sync_engine.dialect
    monkeypatch.setattr(dialect, "insert_returning", False, raising=False)
    monkeypatch.setattr(dialect, "insert_executemany_returning", False, raising=False)
    return test_db


class TestBulkInsertAcrossEngines:
    @pytest.mark.asyncio
    async def test_bulk_insert_returns_server_defaults_without_returning(
        self, repository, no_returning
    ) -> None:
        # The F3 case. Before the fix this raised MissingGreenlet, which
        # Database.session() converted to a 500 — for rows already committed.
        results = await repository.insert_datas(
            [_request(f"bulk{i}") for i in range(3)]
        )

        assert len(results) == 3
        for dto in results:
            assert dto.created_at is not None, "server_default was never loaded"
            assert dto.updated_at is not None

    @pytest.mark.asyncio
    async def test_bulk_insert_still_works_with_returning(self, repository) -> None:
        # The engines CI does run must not regress.
        results = await repository.insert_datas([_request(f"ret{i}") for i in range(2)])

        assert all(dto.created_at is not None for dto in results)

    @pytest.mark.asyncio
    async def test_singular_and_bulk_agree_on_what_they_return(
        self, repository, no_returning
    ) -> None:
        """The parity the ADR is about.

        `insert_data` refreshed and `insert_datas` did not, so the same write
        expressed two ways produced DTOs with different fields populated.
        """
        one = await repository.insert_data(_request("solo"))
        many = await repository.insert_datas([_request("many")])

        assert (one.created_at is None) == (many[0].created_at is None)

    @pytest.mark.asyncio
    async def test_empty_bulk_insert_is_a_noop(self, repository) -> None:
        assert await repository.insert_datas([]) == []


class TestDeterministicPagination:
    @pytest.mark.asyncio
    async def test_pages_do_not_overlap_or_skip(self, repository) -> None:
        # Without a stable ORDER BY the engine may return rows in any order per
        # query, so page 2 can repeat or omit rows from page 1.
        await repository.insert_datas([_request(f"page{i:02d}") for i in range(10)])

        first = await repository.select_datas(page=1, page_size=5)
        second = await repository.select_datas(page=2, page_size=5)

        ids = [dto.id for dto in first] + [dto.id for dto in second]
        assert len(ids) == len(set(ids)), "a row appeared on two pages"
        assert len(ids) == 10, "a row was skipped between pages"

    @pytest.mark.asyncio
    async def test_paged_count_query_is_also_ordered(self, repository) -> None:
        await repository.insert_datas([_request(f"cnt{i:02d}") for i in range(6)])

        first, total = await repository.select_datas_with_count(
            page=1, page_size=3, query_filter=None
        )
        second, _ = await repository.select_datas_with_count(
            page=2, page_size=3, query_filter=None
        )

        assert total >= 6
        overlap = {d.id for d in first} & {d.id for d in second}
        assert not overlap

    @pytest.mark.asyncio
    async def test_an_explicit_sort_is_still_honoured(self, repository) -> None:
        # The default tiebreaker must not override a caller's sort.
        await repository.insert_datas([_request(f"srt{i}") for i in range(3)])

        rows, _ = await repository.select_datas_with_count(
            page=1,
            page_size=10,
            query_filter=QueryFilter(sort_field="username", sort_order="desc"),
        )

        usernames = [r.username for r in rows if r.username.startswith("srt")]
        assert usernames == sorted(usernames, reverse=True)

    @pytest.mark.asyncio
    async def test_ties_under_an_explicit_sort_are_still_deterministic(
        self, repository
    ) -> None:
        """The case the first fix missed.

        `sorted_explicitly` skipped the tiebreaker entirely, so sorting by a
        non-unique column put tie order back in the engine's hands — and offset
        paging over ties can still repeat or skip rows. "Explicit sort wins"
        means it is the *primary* key, not the only one.

        `full_name` is identical across these rows, so every row is a tie.
        """
        await repository.insert_datas(
            [
                make_create_user_request(
                    username=f"tie{i:02d}",
                    email=f"tie{i:02d}@example.com",
                    full_name="Same Name",
                )
                for i in range(8)
            ]
        )
        query_filter = QueryFilter(sort_field="full_name", sort_order="asc")

        first, _ = await repository.select_datas_with_count(
            page=1, page_size=4, query_filter=query_filter
        )
        second, _ = await repository.select_datas_with_count(
            page=2, page_size=4, query_filter=query_filter
        )

        ids = [d.id for d in first] + [d.id for d in second]
        assert len(ids) == len(set(ids)), "a tied row appeared on two pages"

    @pytest.mark.asyncio
    async def test_sorting_by_the_primary_key_is_not_ordered_twice(
        self, repository
    ) -> None:
        # The tiebreaker is the PK descending; adding it beside an explicit
        # ascending PK sort would order the same column both ways.
        await repository.insert_datas([_request(f"pk{i}") for i in range(3)])

        rows, _ = await repository.select_datas_with_count(
            page=1,
            page_size=10,
            query_filter=QueryFilter(sort_field="id", sort_order="asc"),
        )

        ids = [r.id for r in rows]
        assert ids == sorted(ids)


class TestSearchFailsClosed:
    @pytest.mark.asyncio
    async def test_a_search_over_no_usable_field_does_not_return_everything(
        self, repository
    ) -> None:
        # Previously: every non-String field was dropped, no WHERE was added,
        # and the full table came back with total_items = full count.
        await repository.insert_datas([_request(f"sf{i}") for i in range(4)])

        with pytest.raises(DatabaseException) as exc:
            await repository.select_datas_with_count(
                page=1,
                page_size=10,
                query_filter=QueryFilter(search_query="x", search_fields=["id"]),
            )

        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_an_unknown_search_field_is_rejected(self, repository) -> None:
        with pytest.raises(DatabaseException) as exc:
            await repository.select_datas_with_count(
                page=1,
                page_size=10,
                query_filter=QueryFilter(
                    search_query="x", search_fields=["nope_not_a_field"]
                ),
            )

        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_a_usable_search_field_still_filters(self, repository) -> None:
        await repository.insert_datas([_request("findme")])

        rows, total = await repository.select_datas_with_count(
            page=1,
            page_size=10,
            query_filter=QueryFilter(search_query="findme", search_fields=["username"]),
        )

        assert total == 1
        assert rows[0].username == "findme"

    @pytest.mark.asyncio
    async def test_a_mix_keeps_the_usable_fields(self, repository) -> None:
        # Dropping the unusable half silently is what failed open; rejecting the
        # whole request when *some* field works would be over-correction.
        await repository.insert_datas([_request("mixed")])

        rows, _ = await repository.select_datas_with_count(
            page=1,
            page_size=10,
            query_filter=QueryFilter(
                search_query="mixed", search_fields=["username", "email"]
            ),
        )

        assert any(r.username == "mixed" for r in rows)


class TestSortFieldResolution:
    @pytest.mark.asyncio
    async def test_an_unknown_sort_field_is_a_400_not_a_500(self, repository) -> None:
        # Previously: bare hasattr/getattr, then .desc() on whatever came back,
        # producing an opaque DB_INTERNAL_ERROR.
        with pytest.raises(DatabaseException) as exc:
            await repository.select_datas_with_count(
                page=1,
                page_size=10,
                query_filter=QueryFilter(sort_field="not_a_column"),
            )

        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_a_non_column_attribute_is_rejected(self, repository) -> None:
        # `hasattr` was true for methods and class attributes too.
        with pytest.raises(DatabaseException) as exc:
            await repository.select_datas_with_count(
                page=1,
                page_size=10,
                query_filter=QueryFilter(sort_field="metadata"),
            )

        assert exc.value.status_code == 400


class TestNoDeadRelationshipHook:
    def test_the_related_entities_branch_is_gone(self) -> None:
        """It passed a list where AsyncSession.refresh takes one instance.

        The repo declares no `relationship()` and nothing defines
        `related_entities`, so the branch was dead — and wrong the moment it was
        not. Asserting on the source keeps it from being reintroduced as
        plausible-looking N+1 mitigation.
        """
        from pathlib import Path

        source = Path(
            "src/_core/infrastructure/persistence/rdb/base_repository.py"
        ).read_text(encoding="utf-8")

        assert "related_entities" not in source


class TestDateGroupedCountAcrossEngines:
    """`count_datas_by_day` must behave identically on every engine (#368).

    Two dialect differences were measured before writing this, and both would
    otherwise have shipped as engine-specific behaviour:

    - `cast(column, Date)` — the obvious expression, and the one the plan for
      this work originally specified — raises `TypeError: fromisoformat:
      argument must be str` on **SQLite**, the quickstart default. `func.date`
      works on both engines tested.
    - `func.date` returns `str` on SQLite and `datetime.date` on PostgreSQL, so
      a caller that formatted the value would work on one engine and raise on
      the other.

    These run on SQLite in CI and on PostgreSQL under `make test-pg`, so the
    parity assertions are exercised on both. Per ADR 058's stated limit, MySQL
    still rests on documentation rather than a test.

    **Each test owns a distinct year and asserts only on that year.** `test_db`
    is session-scoped, so the whole suite shares one database and rows
    accumulate — the same reason the tests above use unique usernames. `since`
    is only a *lower* bound, so every row another test inserts with
    `created_at = now()` also falls inside these windows; anchoring the era
    without filtering the result was the first thing that broke here, and it
    broke only in the full run. Running these with `-k DateGrouped` hides it,
    because then no other rows exist. Use :meth:`_era` and run the full suite on
    both engines.
    """

    @staticmethod
    def _era(rows, year: int):
        """Only this test's own year, so rows from the shared session-scoped
        database cannot leak into the assertion."""
        return [(r.day.isoformat(), r.count) for r in rows if r.day.year == year]

    @staticmethod
    async def _backdate(test_db, username: str, when: datetime) -> None:
        """Force `created_at`, which carries `server_default=func.now()`.

        Naive datetimes on purpose: `user.created_at` is `DateTime` without
        `timezone=True`, and `count_datas_by_day` deliberately does not coerce.
        """
        async with test_db.session() as session:
            await session.execute(
                update(UserModel)
                .where(UserModel.username == username)
                .values(created_at=when)
            )
            await session.commit()

    async def _seed(self, repository, test_db, name: str, when: datetime) -> None:
        await repository.insert_data(_request(name))
        await self._backdate(test_db, name, when)

    @pytest.mark.asyncio
    async def test_day_is_a_date_object_on_every_engine(
        self, repository, test_db
    ) -> None:
        await self._seed(repository, test_db, "dgc_type", datetime(2001, 3, 10, 7, 0))

        rows = await repository.count_datas_by_day(since=datetime(2001, 1, 1))

        mine = [r for r in rows if r.day.year == 2001]
        assert mine, "expected the backdated row to be counted"
        assert isinstance(mine[0].day, date), (
            f"engine leaked {type(mine[0].day).__name__} instead of datetime.date"
        )
        assert not isinstance(mine[0].day, datetime), "a day must not carry a time"

    @pytest.mark.asyncio
    async def test_rows_on_the_same_day_collapse_into_one_entry(
        self, repository, test_db
    ) -> None:
        await self._seed(repository, test_db, "dgc_a", datetime(2002, 3, 11, 7, 0))
        # Same day, late in the day — must not spill into the next one.
        await self._seed(repository, test_db, "dgc_b", datetime(2002, 3, 11, 23, 30))
        await self._seed(repository, test_db, "dgc_c", datetime(2002, 3, 10, 1, 0))

        rows = await repository.count_datas_by_day(since=datetime(2002, 1, 1))

        assert self._era(rows, 2002) == [
            ("2002-03-10", 1),
            ("2002-03-11", 2),
        ], "grouping or ordering differs from oldest-day-first"

    @pytest.mark.asyncio
    async def test_since_excludes_older_rows(self, repository, test_db) -> None:
        await self._seed(repository, test_db, "dgc_old", datetime(2003, 1, 5, 12, 0))
        await self._seed(repository, test_db, "dgc_new", datetime(2003, 6, 20, 12, 0))

        rows = await repository.count_datas_by_day(since=datetime(2003, 6, 1))

        assert self._era(rows, 2003) == [("2003-06-20", 1)]

    @pytest.mark.asyncio
    async def test_days_with_no_rows_are_absent_not_zero_filled(
        self, repository, test_db
    ) -> None:
        """The repository reports what the table holds; gap-filling is the
        caller's policy decision (see DailyCount)."""
        await self._seed(repository, test_db, "dgc_gap1", datetime(2004, 5, 5, 9, 0))
        await self._seed(repository, test_db, "dgc_gap2", datetime(2004, 5, 9, 9, 0))

        rows = await repository.count_datas_by_day(since=datetime(2004, 1, 1))

        assert self._era(rows, 2004) == [("2004-05-05", 1), ("2004-05-09", 1)]

    @pytest.mark.asyncio
    async def test_window_with_no_rows_returns_an_empty_list(self, repository) -> None:
        rows = await repository.count_datas_by_day(
            since=datetime(1990, 1, 1), column_name="created_at"
        )
        # 1990 predates every seeded era, and `since` is a lower bound, so this
        # asserts on a window nothing falls into rather than on an empty table.
        assert [r for r in rows if r.day.year < 2000] == []

    @pytest.mark.asyncio
    async def test_unknown_column_raises_a_curated_400(self, repository) -> None:
        with pytest.raises(DatabaseException) as exc:
            await repository.count_datas_by_day(
                since=datetime(2005, 1, 1), column_name="nope"
            )

        assert exc.value.status_code == 400
        assert exc.value.error_code == "DB_TIME_FIELD_UNUSABLE"

    @pytest.mark.asyncio
    async def test_non_temporal_column_raises_a_curated_400(self, repository) -> None:
        """Fails closed rather than grouping by a string column and returning
        nonsense days — the DB_SEARCH_FIELD_UNUSABLE precedent (ADR 058 D3)."""
        with pytest.raises(DatabaseException) as exc:
            await repository.count_datas_by_day(
                since=datetime(2005, 1, 1), column_name="username"
            )

        assert exc.value.status_code == 400
        assert exc.value.error_code == "DB_TIME_FIELD_UNUSABLE"
