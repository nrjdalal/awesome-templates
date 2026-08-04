"""Contract tests for Alembic revision identifiers.

Alembic stores the applied revision in `alembic_version.version_num`, and
`DefaultImpl.version_table_impl` hardcodes that column as `String(32)` — there
is no configuration hook for the width (checked against alembic 1.17.2;
`version_table_column_length` does **not** exist, `configure()` swallows it as
an unknown kwarg and the length stays 32).

Three shipped revisions were longer than that: `0006_add_user_admin_permission_fields`
(37), `0008_ai_usage_add_guardrail_triggered` (37) and
`0009_admin_identity_realm_separation` (36). On PostgreSQL the upgrade died the
moment it tried to stamp 0006:

    DataError: (psycopg.errors.StringDataRightTruncation)
    value too long for type character varying(32)
    [SQL: UPDATE alembic_version SET version_num='0006_add_user_admin_permission_fields'
          WHERE alembic_version.version_num = '0005_add_user_role']

so `alembic upgrade head` had never completed against the production engine.
SQLite — the default test engine — does not enforce VARCHAR length, and CI has
never run PostgreSQL (#333), so nothing caught it. Found by bringing the
compose stack up while fixing #332.

The sequence-prefix check is deliberately weaker than "filename equals revision
id": three pre-existing files already break the stronger form
(`0001_baseline_current_rdb_schema.py` declares `0001_baseline_current_rdb`,
and 0002/0003 differ likewise), so that convention was never the repo's. What
*is* held everywhere, and is what a reader relies on to find a revision by
name, is the shared `NNNN_` ordering prefix.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# alembic.ddl.impl.DefaultImpl.version_table_impl:
#   Column("version_num", String(32), nullable=False)
_VERSION_NUM_MAX_LENGTH = 32

_VERSIONS_DIR = Path(__file__).resolve().parents[3] / "migrations" / "versions"

_REVISION_RE = re.compile(
    r"^revision(?::\s*str)?\s*=\s*[\"']([^\"']+)[\"']",
    re.MULTILINE,
)


def _revision_files() -> list[Path]:
    return sorted(p for p in _VERSIONS_DIR.glob("*.py") if p.name != "__init__.py")


def _revision_id(path: Path) -> str:
    match = _REVISION_RE.search(path.read_text())
    assert match is not None, f"{path.name} declares no `revision = ...`"
    return match.group(1)


def test_versions_directory_is_not_empty() -> None:
    # Guards the parametrised tests below against silently passing on an empty
    # collection if the directory is ever moved.
    assert _revision_files()


@pytest.mark.parametrize("path", _revision_files(), ids=lambda p: p.name)
def test_revision_id_fits_alembic_version_column(path: Path) -> None:
    revision = _revision_id(path)

    assert len(revision) <= _VERSION_NUM_MAX_LENGTH, (
        f"revision id {revision!r} is {len(revision)} characters; "
        f"alembic_version.version_num is VARCHAR({_VERSION_NUM_MAX_LENGTH}) and "
        "the width is not configurable, so this fails on PostgreSQL and MySQL "
        "while passing silently on SQLite."
    )


@pytest.mark.parametrize("path", _revision_files(), ids=lambda p: p.name)
def test_revision_id_shares_the_filename_sequence_prefix(path: Path) -> None:
    revision = _revision_id(path)
    sequence = path.stem.split("_", 1)[0]

    assert revision.startswith(f"{sequence}_"), (
        f"{path.name} declares revision {revision!r}, which does not carry the "
        f"file's {sequence!r} ordering prefix."
    )
