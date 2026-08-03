"""Seed a demo admin that the admin-realm HTTP token API will accept.

Why this exists
---------------
`/v1/user*` is gated on `Depends(require_admin)` (#199, re-pointed to the admin
realm by #218/ADR 049), so `scripts/demo.sh` needs an admin-realm token. There is
no way to obtain one with curl alone:

- The only admin-realm HTTP routes are `/v1/admin/login|refresh|logout`. Real
  admins are created through the NiceGUI setup wizard, which has no HTTP
  equivalent.
- The quickstart bootstrap admin cannot stand in. `require_admin` rejects
  `is_bootstrap_admin` outright, and `AdminAuthUseCase.login` rejects both
  bootstrap and `password_temporary` admins before issuing a token pair.

So `make demo` died at the first `/v1/user` call with `INVALID_TOKEN`, and had
done since 2026-05-27 while the script was last touched 2026-05-06.

Rather than change the runtime — auto-seeding a privileged account with known
credentials into a shipped env profile is a security-posture decision, not a
demo fix — this script performs the two steps the wizard performs, explicitly
and only when a developer runs it:

1. `create_admin_account(...)` — a non-bootstrap admin with every page
   permission. It lands with `password_temporary=True`.
2. `change_admin_password(...)` — rewrites the credential through
   `_PasswordChangeClearTempDTO`, which clears the temporary flag. Without this
   second step `login` still refuses the account.

Guards
------
Refuses to run in `stg`/`prod`. The account it creates is a real, fully
privileged admin whose credentials are committed in `scripts/demo.sh`, so it
must never exist in an environment that matters.

Idempotent: a re-run resets the existing demo admin's credential instead of
failing on the unique-username check, so `make demo` works on a warm
`quickstart.db`.

Usage
-----
    uv run python scripts/seed_demo_admin.py --env quickstart
    uv run python scripts/seed_demo_admin.py --env quickstart --username someone
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parents[1]

# Running a file under scripts/ puts scripts/ on sys.path[0], not the repo root,
# and the project declares no [build-system] so it is never installed as a
# distribution. Without this, `import src...` raises ModuleNotFoundError even
# from an activated .venv at the repo root.
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Fixed cross-cutting keys pre-seeded in AdminPermissionRegistry. Mirrored here
# because the registry is populated during NiceGUI admin bootstrap, which this
# script deliberately does not run (it must work without the `admin` extra).
_FIXED_PERMISSION_KEYS = ("accounts", "audit_log")

_STRICT_ENVS = frozenset({"stg", "prod"})

DEFAULT_USERNAME = "demoadmin"
DEFAULT_SECRET = "demoadmin123"  # noqa: S105 - demo credential, guarded above
DEFAULT_EMAIL = "demoadmin@example.com"
DEFAULT_FULL_NAME = "Demo Administrator"


def _admin_page_permission_keys() -> list[str]:
    """Page keys an admin can be granted, without importing NiceGUI.

    `_discover_and_register_pages` registers `cfg.domain_name` for every domain
    exposing `interface/admin/configs/{d}_admin_config.py`. Detecting those
    files on disk rather than importing them keeps this script runnable on a
    minimal install, where the `admin` extra is absent.
    """
    from src._core.infrastructure.discovery import discover_domains

    keys = set(_FIXED_PERMISSION_KEYS)
    for domain in discover_domains():
        config = (
            _REPO_ROOT
            / "src"
            / domain
            / "interface"
            / "admin"
            / "configs"
            / f"{domain}_admin_config.py"
        )
        if config.is_file():
            keys.add(domain)
    return sorted(keys)


async def _seed(username: str, secret: str, email: str, full_name: str) -> int:
    from src._apps.server.di.container import create_server_container
    from src.admin_identity.domain.dtos.admin_identity_dto import CreateAdminAccountDTO

    container = create_server_container()
    service = container.admin_identity_container.admin_identity_service()
    repository = container.admin_identity_container.admin_repository()

    try:
        existing = await repository.select_data_by_username(username)
        if existing is not None:
            # Re-running the demo on a warm quickstart.db. Rewriting the
            # credential through change_admin_password also clears
            # password_temporary, which is what a token login needs.
            admin = await service.change_admin_password(existing.id, secret)
            print(f"Demo admin '{admin.username}' already existed — credential reset.")
            return admin.id

        admin = await service.create_admin_account(
            CreateAdminAccountDTO(
                username=username,
                full_name=full_name,
                email=email,
                permissions=_admin_page_permission_keys(),
            ),
            temp_password=secret,
        )
        # create_admin_account always lands password_temporary=True; login()
        # refuses such accounts, so clear the flag by rewriting the credential.
        admin = await service.change_admin_password(admin.id, secret)
        print(
            f"Demo admin '{admin.username}' created with permissions "
            f"{admin.permissions}."
        )
        return admin.id
    finally:
        # Nothing in src/ calls Database.dispose() — there is no FastAPI
        # lifespan handler — so the async engine's pool keeps the process
        # alive after the coroutine returns. A long-lived server exits by
        # process teardown; a one-shot script would just hang. Observed:
        # seeding printed its success line and never returned.
        await container.core_container.database().dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed a demo admin for make demo.")
    parser.add_argument("--env", default="quickstart")
    parser.add_argument("--username", default=DEFAULT_USERNAME)
    parser.add_argument("--secret", default=DEFAULT_SECRET)
    parser.add_argument("--email", default=DEFAULT_EMAIL)
    parser.add_argument("--full-name", default=DEFAULT_FULL_NAME)
    args = parser.parse_args()

    if args.env in _STRICT_ENVS:
        print(
            f"Refusing to seed a demo admin in '{args.env}': this creates a fully "
            "privileged account whose credentials are committed in "
            "scripts/demo.sh.",
            file=sys.stderr,
        )
        return 2

    load_dotenv(dotenv_path=_REPO_ROOT / "_env" / f"{args.env}.env", override=True)

    from src._core.config import settings

    if settings.env in _STRICT_ENVS:
        print(
            f"Refusing to seed a demo admin: _env/{args.env}.env resolves to "
            f"ENV={settings.env}.",
            file=sys.stderr,
        )
        return 2

    asyncio.run(
        _seed(
            username=args.username,
            secret=args.secret,
            email=args.email,
            full_name=args.full_name,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
