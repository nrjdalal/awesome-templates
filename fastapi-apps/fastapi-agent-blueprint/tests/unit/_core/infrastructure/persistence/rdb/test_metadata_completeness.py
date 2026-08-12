"""`Base.metadata` must be complete regardless of which tests are selected (#374).

The `test_db` fixture calls `drop_all` / `create_all` against whatever
`Base.metadata` happens to hold. That used to depend on which test modules the
run collected, because nothing imported the models deliberately — so metadata
varied with `-k`, with a single-file run, and with collection order.

On PostgreSQL that made `drop_all` a coin flip. A selection whose imports omitted
`refresh_token` left metadata unaware that `refresh_token.user_id` references
`user`, so the fixture tried to drop `user` first and PostgreSQL refused:

    DependentObjectsStillExistError: cannot drop table "user" because other
    objects depend on it
    DETAIL: constraint refresh_token_user_id_fkey on table refresh_token ...

Every test in the file then errored at *setup*, which reads as a broken change
rather than a partial-metadata problem. Two things hid it: the full suite
imported enough models by accident, and SQLite enforces no FKs and starts from a
fresh in-memory database. It only surfaced against a PostgreSQL that already had
the schema — from `make dev`, an `alembic upgrade`, or an earlier run.

**Running this file on its own is the reproduction.** In isolation nothing else
imports the models, so if `conftest.py` stops calling `load_models()` these
assertions fail here. In a full-suite run they would pass either way, which is
precisely why the defect survived: a green full run proves nothing about this.
"""

from __future__ import annotations

from src._core.infrastructure.persistence.rdb.database import Base

# Cross-domain FK pairs are the ones that break `drop_all` when metadata is
# partial — a table can only be dropped after its dependants, and metadata is
# the only thing that knows the order.
_FK_DEPENDENT_PAIRS = (
    ("refresh_token", "user"),
    ("admin_refresh_token", "admin_identity"),
)

# One representative table per model-bearing domain, plus the cross-cutting
# `_core` tables that live outside the per-domain layout `load_models` scans by
# convention. A new domain with models belongs here.
_EXPECTED_TABLES = frozenset(
    {
        "user",
        "refresh_token",
        "admin_identity",
        "admin_refresh_token",
        "document",
        "ai_usage_log",
        "admin_audit_log",
    }
)


def test_every_expected_table_is_registered() -> None:
    missing = sorted(_EXPECTED_TABLES - set(Base.metadata.tables))
    assert not missing, (
        f"missing from Base.metadata: {missing}. "
        "conftest.py must call load_models() before any fixture touches the "
        "schema; without it metadata depends on the test selection (#374)."
    )


def test_cross_domain_foreign_keys_are_visible_to_metadata() -> None:
    """Both ends of each FK must be registered, or `drop_all` cannot order them.

    Asserting the tables exist is not enough — the dependency itself has to be in
    metadata, which is what `sorted_tables` uses.
    """
    for dependent, target in _FK_DEPENDENT_PAIRS:
        assert dependent in Base.metadata.tables, f"{dependent} not registered"
        assert target in Base.metadata.tables, f"{target} not registered"

        table = Base.metadata.tables[dependent]
        referenced = {fk.column.table.name for fk in table.foreign_keys}
        assert target in referenced, (
            f"{dependent} does not declare its FK to {target} in metadata; "
            "drop_all would order them arbitrarily and PostgreSQL would refuse"
        )


def test_drop_order_places_dependants_before_their_targets() -> None:
    """The actual invariant `drop_all` relies on.

    `sorted_tables` is create order; drop order is its reverse. This asserts the
    property directly rather than trusting that registering the tables was
    enough.
    """
    order = [table.name for table in Base.metadata.sorted_tables]
    drop_order = list(reversed(order))

    for dependent, target in _FK_DEPENDENT_PAIRS:
        assert drop_order.index(dependent) < drop_order.index(target), (
            f"{dependent} would be dropped after {target}, which PostgreSQL "
            "rejects while the FK constraint exists"
        )
