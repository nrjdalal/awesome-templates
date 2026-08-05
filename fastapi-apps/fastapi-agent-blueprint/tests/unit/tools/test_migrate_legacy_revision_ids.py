"""Tests for the pre-#332 revision-id rewrite.

#332 shortened three Alembic revision ids past the hardcoded `String(32)` of
`alembic_version.version_num`. The PR first claimed no database could be holding
the old values; a cross-review disproved it. PostgreSQL and MySQL do reject them
— that was the bug — but SQLite does not enforce VARCHAR length, so a v0.9.0
install that ran migrations on SQLite has a long id stored and would meet
`Can't locate revision identified by ...` on upgrade. Same for anyone who
widened the column by hand.

These tests use real SQLite files rather than mocks, because the whole point is
what a *stored* value does.
"""

from __future__ import annotations

import importlib.util
import sqlite3
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
TOOL_PATH = REPO_ROOT / "tools" / "migrate_legacy_revision_ids.py"


def _load_module():
    """Load by path like the sibling `tools` tests.

    `tools/` is a script directory with no `__init__.py`, so `import tools.x`
    only resolved while pytest happened to put the rootdir on `sys.path`.
    pytest 9.0.3 stopped doing that and the module vanished.
    """
    spec = importlib.util.spec_from_file_location(
        "migrate_legacy_revision_ids", TOOL_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["migrate_legacy_revision_ids"] = module
    spec.loader.exec_module(module)
    return module


_module = _load_module()
_RENAMES = _module._RENAMES
rewrite_legacy_ids = _module.rewrite_legacy_ids

_LEGACY_HEAD = "0009_admin_identity_realm_separation"
_CURRENT_HEAD = "0009_admin_identity_realm"


def _dsn(path: Path) -> str:
    return f"sqlite:///{path}"


def _make_db(path: Path, stored: str | None) -> None:
    connection = sqlite3.connect(path)
    try:
        if stored is not None:
            connection.execute(
                "CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"
            )
            connection.execute(
                "INSERT INTO alembic_version (version_num) VALUES (?)", (stored,)
            )
            connection.commit()
    finally:
        connection.close()


def _stored(path: Path) -> list[str]:
    connection = sqlite3.connect(path)
    try:
        return [
            r[0] for r in connection.execute("SELECT version_num FROM alembic_version")
        ]
    finally:
        connection.close()


def test_rewrites_a_legacy_head(tmp_path: Path) -> None:
    db = tmp_path / "legacy.db"
    _make_db(db, _LEGACY_HEAD)

    found = rewrite_legacy_ids(_dsn(db))

    assert found == [(_LEGACY_HEAD, _CURRENT_HEAD)]
    assert _stored(db) == [_CURRENT_HEAD]


@pytest.mark.parametrize(("legacy", "current"), sorted(_RENAMES.items()))
def test_rewrites_every_renamed_id(tmp_path: Path, legacy: str, current: str) -> None:
    db = tmp_path / f"{current}.db"
    _make_db(db, legacy)

    rewrite_legacy_ids(_dsn(db))

    assert _stored(db) == [current]


def test_is_a_noop_on_a_current_head(tmp_path: Path) -> None:
    db = tmp_path / "current.db"
    _make_db(db, _CURRENT_HEAD)

    assert rewrite_legacy_ids(_dsn(db)) == []
    assert _stored(db) == [_CURRENT_HEAD]


def test_is_a_noop_when_the_table_does_not_exist(tmp_path: Path) -> None:
    # A fresh database: Alembic creates the table itself, so the script must not
    # create it, and must not raise.
    db = tmp_path / "fresh.db"
    _make_db(db, None)

    assert rewrite_legacy_ids(_dsn(db)) == []


def test_is_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "twice.db"
    _make_db(db, _LEGACY_HEAD)

    rewrite_legacy_ids(_dsn(db))
    second = rewrite_legacy_ids(_dsn(db))

    assert second == []
    assert _stored(db) == [_CURRENT_HEAD]


def test_dry_run_reports_without_writing(tmp_path: Path) -> None:
    db = tmp_path / "dry.db"
    _make_db(db, _LEGACY_HEAD)

    found = rewrite_legacy_ids(_dsn(db), dry_run=True)

    assert found == [(_LEGACY_HEAD, _CURRENT_HEAD)]
    assert _stored(db) == [_LEGACY_HEAD]


def test_leaves_an_unknown_value_alone(tmp_path: Path) -> None:
    # Guards against a future edit that rewrites anything not in _RENAMES.
    db = tmp_path / "unknown.db"
    _make_db(db, "9999_someone_elses_revision")

    assert rewrite_legacy_ids(_dsn(db)) == []
    assert _stored(db) == ["9999_someone_elses_revision"]


def test_rename_targets_are_the_ids_that_ship() -> None:
    versions = Path(__file__).resolve().parents[3] / "migrations" / "versions"
    shipped = {p.stem for p in versions.glob("*.py") if p.name != "__init__.py"}

    assert set(_RENAMES.values()) <= shipped
    assert not set(_RENAMES) & shipped
