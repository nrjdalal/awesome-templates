"""Collection bounds on the user router (#322).

Both endpoints took an unbounded collection. The batch-create one is the sharper
of the two: every element costs one bcrypt round, so an unbounded list is a
request that occupies a worker thread for N x ~220 ms. Bounding it at the schema
layer turns that into a 422 before any work starts.
"""

from __future__ import annotations

from src.user.interface.server.routers import user_router

MAX_BATCH = user_router.MAX_BATCH_SIZE
MAX_IDS = user_router.MAX_IDS_PER_QUERY


def _param(endpoint, name):
    import inspect

    return inspect.signature(endpoint).parameters[name]


class TestBatchCreateIsBounded:
    def test_limit_is_declared_and_sane(self):
        assert 1 < MAX_BATCH <= 1000, (
            f"MAX_BATCH_SIZE={MAX_BATCH} — an unbounded or very large batch is "
            "N x one bcrypt round in a single request"
        )

    def test_items_parameter_carries_the_bound(self):
        annotation = _param(user_router.create_users, "items").annotation
        assert str(MAX_BATCH) in str(annotation) or "max_length" in str(annotation), (
            f"items is not bounded: {annotation}"
        )


class TestByIdsIsBounded:
    def test_limit_is_declared_and_sane(self):
        assert 1 < MAX_IDS <= 1000, f"MAX_IDS_PER_QUERY={MAX_IDS}"

    def test_ids_query_carries_the_bound(self):
        # FastAPI's Query keeps the constraint in `.metadata` as an annotated_types
        # MaxLen, not as a `max_length` attribute — assert on what is actually there.
        default = _param(user_router.get_user_by_ids, "ids").default
        bounds = [
            getattr(m, "max_length", None) for m in getattr(default, "metadata", [])
        ]
        assert MAX_IDS in bounds, f"ids Query is not bounded: {default!r}"
