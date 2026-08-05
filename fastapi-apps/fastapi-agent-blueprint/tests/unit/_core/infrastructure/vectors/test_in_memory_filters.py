"""In-memory vector filter semantics (#328 F10).

`_matches_filters` handled `$eq`, `$in`, `$ne` and bare equality. Anything else
fell through every branch and the loop continued to `return True`, so an
unsupported operator was **silently discarded**:

    {"year": {"$gte": 2020}} matched a record with year=2015     # fails OPEN

A top-level `$and` is not a dict-valued *field* condition, so it took the bare
equality branch, compared `metadata.get("$and")` (None) against a list, and
matched nothing:

    {"$and": [...]} matched no record at all                     # fails CLOSED

Fail-open is the dangerous direction. `VectorQuery`'s docstring — the shared VO
both backends consume — advertises `{"year": {"$gte": 2020}}` and `{"$and": [...]}`
as *the* filter contract with no backend qualification, so a consumer writing
tenant or ACL scoping against it would get unfiltered results on the default
backend, with no error. `inmemory` is the default whenever `VECTOR_STORE_TYPE`
is unset, including in prod.

The fix is to be loud, not to implement the operators. That is a scope choice,
not a ceiling: S3 Vectors supports
`$eq/$ne/$gt/$gte/$lt/$lte/$in/$nin/$exists/$and/$or`, and this repo's S3 store
passes `query.filters` through to `query_vectors` untouched — so the in-memory
store implements 3 of 11 and is the *less* capable backend. Widening it later is
fine; silently discarding what is missing is not.

Two things the first attempt got wrong, both caught in review:

- The check lived inside the per-record loop, so "fails loudly" depended on the
  data. An empty store never evaluates a filter, and an earlier condition that
  eliminates every record short-circuits before a later unsupported operator is
  reached. Validation now runs once at `search()` entry.
- It raised `NotImplementedError`, which the generic handler turns into a 500 on
  the public `POST /v1/docs/query`. It is now a curated 400
  (`VECTOR_FILTER_UNSUPPORTED`), so a filter valid against the S3 backend does
  not become a server error purely because of which backend is deployed.
"""

from __future__ import annotations

import pytest

from src._core.infrastructure.vectors.in_memory.base_store import (
    _matches_filters,
    validate_filters,
)
from src._core.infrastructure.vectors.in_memory.exceptions import (
    VectorFilterUnsupportedException,
)

_METADATA = {"category": "tech", "year": 2015, "tenant": "acme"}


class TestSupportedOperators:
    def test_bare_equality_matches(self) -> None:
        assert _matches_filters(_METADATA, {"category": "tech"}) is True

    def test_bare_equality_rejects(self) -> None:
        assert _matches_filters(_METADATA, {"category": "sci"}) is False

    def test_eq(self) -> None:
        assert _matches_filters(_METADATA, {"category": {"$eq": "tech"}}) is True
        assert _matches_filters(_METADATA, {"category": {"$eq": "sci"}}) is False

    def test_in(self) -> None:
        assert (
            _matches_filters(_METADATA, {"category": {"$in": ["tech", "sci"]}}) is True
        )
        assert _matches_filters(_METADATA, {"category": {"$in": ["sci"]}}) is False

    def test_ne(self) -> None:
        assert _matches_filters(_METADATA, {"category": {"$ne": "tech"}}) is False
        assert _matches_filters(_METADATA, {"category": {"$ne": "sci"}}) is True

    def test_multiple_fields_are_conjunctive(self) -> None:
        assert _matches_filters(_METADATA, {"category": "tech", "year": 2015}) is True
        assert _matches_filters(_METADATA, {"category": "tech", "year": 2020}) is False


class TestUnsupportedOperatorsAreLoud:
    @pytest.mark.parametrize("operator", ["$gte", "$gt", "$lte", "$lt"])
    def test_comparison_operators_raise_instead_of_matching_everything(
        self, operator: str
    ) -> None:
        # Previously: returned True for year=2015 against {"$gte": 2020}.
        with pytest.raises(VectorFilterUnsupportedException) as exc:
            validate_filters({"year": {operator: 2020}})

        assert operator in str(exc.value)
        assert "year" in str(exc.value)

    def test_the_error_names_what_is_supported(self) -> None:
        with pytest.raises(VectorFilterUnsupportedException) as exc:
            validate_filters({"year": {"$gte": 2020}})

        message = str(exc.value)
        for supported in ("$eq", "$in", "$ne"):
            assert supported in message

    def test_a_supported_operator_beside_an_unsupported_one_still_raises(self) -> None:
        # Silently honouring the half it understands is the same fail-open bug
        # wearing a disguise.
        with pytest.raises(VectorFilterUnsupportedException):
            validate_filters({"year": {"$eq": 2015, "$gte": 2020}})

    @pytest.mark.parametrize("operator", ["$and", "$or", "$not"])
    def test_compound_operators_raise_instead_of_matching_nothing(
        self, operator: str
    ) -> None:
        # Previously: {"$and": [...]} took the bare-equality branch, compared
        # None against a list, and matched nothing — a filter that silently
        # empties every result set.
        with pytest.raises(VectorFilterUnsupportedException) as exc:
            validate_filters({operator: [{"category": "tech"}, {"year": 2015}]})

        assert operator in str(exc.value)


class TestFailureDirection:
    def test_an_unsupported_filter_never_widens_a_result_set(self) -> None:
        """The property that matters, stated directly.

        A tenant-scoping filter that is silently dropped returns other tenants'
        rows. Raising is acceptable; matching more than asked is not.
        """
        with pytest.raises(VectorFilterUnsupportedException):
            validate_filters({"tenant": {"$gte": "zzz"}})

    def test_an_empty_filter_matches(self) -> None:
        # No filter is not an unsupported filter.
        assert _matches_filters(_METADATA, {}) is True
        validate_filters({})
        validate_filters(None)

    def test_the_error_is_a_400_not_a_500(self) -> None:
        # It reaches the store from a public request body; an untranslated
        # error would surface as INTERNAL_SERVER_ERROR.
        with pytest.raises(VectorFilterUnsupportedException) as exc:
            validate_filters({"year": {"$gte": 2020}})

        assert exc.value.status_code == 400
        assert exc.value.error_code == "VECTOR_FILTER_UNSUPPORTED"


class TestSearchLevelGuarantee:
    """The rejection must not depend on what happens to be stored.

    These are the two shapes that slipped past the first attempt, where the
    check lived inside the per-record loop.
    """

    @pytest.fixture
    def store(self):
        from pydantic import BaseModel

        from src._core.domain.value_objects.vector_query import VectorQuery
        from src._core.infrastructure.vectors.in_memory.base_store import (
            BaseInMemoryVectorStore,
        )

        class _Meta(BaseModel):
            category: str = ""
            year: int = 0

        class _Model:
            __vector_meta__ = None

        class _Store(BaseInMemoryVectorStore):
            def _to_model(self, entity):  # pragma: no cover - unused here
                raise NotImplementedError

        return _Store, _Meta, VectorQuery

    @pytest.mark.asyncio
    async def test_empty_store_still_rejects(self, store) -> None:
        # Nothing to iterate, so a per-record check never runs at all.
        _Store, _Meta, VectorQuery = store
        subject = _Store(model=object, return_entity=_Meta)

        with pytest.raises(VectorFilterUnsupportedException):
            await subject.search(
                VectorQuery(vector=[0.1, 0.2], filters={"year": {"$gte": 2020}})
            )

    @pytest.mark.asyncio
    async def test_rejects_even_when_an_earlier_condition_excludes_everything(
        self, store
    ) -> None:
        # `category: missing` eliminates every record before the loop reaches
        # `$gte`, so the per-record check short-circuited and returned an empty
        # result set instead of raising.
        _Store, _Meta, VectorQuery = store
        subject = _Store(model=object, return_entity=_Meta)
        subject._store["a"] = {
            "vector": [0.1, 0.2],
            "metadata": {"category": "tech", "year": 2015},
        }

        with pytest.raises(VectorFilterUnsupportedException):
            await subject.search(
                VectorQuery(
                    vector=[0.1, 0.2],
                    filters={"category": "missing", "year": {"$gte": 2020}},
                )
            )
