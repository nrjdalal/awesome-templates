"""Rewrite pre-#332 Alembic revision ids stored in ``alembic_version``.

Three revision ids shipped longer than Alembic's ``String(32)``
``alembic_version.version_num`` column and were shortened in #332. PostgreSQL
and MySQL reject the long values outright — ``alembic upgrade head`` had never
completed there — but **SQLite does not enforce VARCHAR length**, so a database
that ran migrations under SQLite (or one whose operator widened the column by
hand) can be holding an id this repo no longer defines. Running the new code
against such a database fails with::

    Can't locate revision identified by '0009_admin_identity_realm_separation'

This script closes that gap. It rewrites any legacy value in place and is a
no-op otherwise, so it is safe to run unconditionally before ``alembic upgrade``
— including on a fresh database, where the table does not exist yet.

It touches exactly one column of one table. It never runs a migration, never
creates the table, and never writes a value that is not in ``_RENAMES``.

Usage::

    uv run python tools/migrate_legacy_revision_ids.py --env local
    uv run python tools/migrate_legacy_revision_ids.py --env local --dry-run

With no ``_env/{env}.env`` file the DATABASE_* process environment is used,
matching the fallback ``migrations/env.py`` gained in the same change.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text

_REPO_ROOT = Path(__file__).resolve().parents[1]

if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Pre-#332 id -> current id. Keep in step with migrations/versions/.
_RENAMES: dict[str, str] = {
    "0006_add_user_admin_permission_fields": "0006_user_admin_permissions",
    "0008_ai_usage_add_guardrail_triggered": "0008_ai_usage_guardrail_flag",
    "0009_admin_identity_realm_separation": "0009_admin_identity_realm",
}

_VERSION_TABLE = "alembic_version"

# Written out rather than interpolated: the pre-commit security hook rejects
# f-string SQL outright, and a constant table name is not worth an exception.
_SELECT_VERSIONS = text("SELECT version_num FROM alembic_version")
_UPDATE_VERSION = text(
    "UPDATE alembic_version SET version_num = :new WHERE version_num = :old"
)


def build_dsn() -> str:
    from src._core.infrastructure.persistence.rdb.database import create_sync_dsn

    return create_sync_dsn(
        engine=os.getenv("DATABASE_ENGINE") or "postgresql",
        database_user=quote_plus(os.getenv("DATABASE_USER") or ""),
        database_password=quote_plus(os.getenv("DATABASE_PASSWORD") or ""),
        database_host=os.getenv("DATABASE_HOST") or "",
        database_port=int(os.getenv("DATABASE_PORT") or "5432"),
        database_name=os.getenv("DATABASE_NAME") or "",
    )


def rewrite_legacy_ids(dsn: str, *, dry_run: bool = False) -> list[tuple[str, str]]:
    """Return the (old, new) pairs found. Applies them unless ``dry_run``."""
    engine = create_engine(dsn)
    try:
        if _VERSION_TABLE not in inspect(engine).get_table_names():
            # Fresh database: Alembic will create the table itself.
            return []

        with engine.begin() as connection:
            stored = [row[0] for row in connection.execute(_SELECT_VERSIONS)]
            found = [(old, _RENAMES[old]) for old in stored if old in _RENAMES]
            if dry_run:
                return found
            for old, new in found:
                connection.execute(_UPDATE_VERSION, {"new": new, "old": old})
        return found
    finally:
        engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Rewrite pre-#332 Alembic revision ids stored in alembic_version."
    )
    parser.add_argument("--env", default=os.getenv("ENV") or "local")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    env_file = _REPO_ROOT / "_env" / f"{args.env}.env"
    if env_file.exists():
        load_dotenv(dotenv_path=env_file, override=True)
    elif not os.getenv("DATABASE_ENGINE"):
        print(
            f"No {env_file} and DATABASE_ENGINE is unset — nothing to connect to.",
            file=sys.stderr,
        )
        return 2

    found = rewrite_legacy_ids(build_dsn(), dry_run=args.dry_run)
    if not found:
        print("No pre-#332 revision ids stored. Nothing to do.")
        return 0

    verb = "Would rewrite" if args.dry_run else "Rewrote"
    for old, new in found:
        print(f"{verb} {old} -> {new}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
