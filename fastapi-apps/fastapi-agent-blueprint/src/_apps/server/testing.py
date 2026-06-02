"""Test helpers for server-level DI overrides.

Import these in ``tests/e2e/conftest.py`` instead of reaching into the
container internals directly. This decouples test code from the container
structure so internal refactors do not break test fixtures.

Usage::

    from src._apps.server.testing import override_database, reset_database_override

    override_database(app, test_db)
    yield
    reset_database_override(app)
"""

from __future__ import annotations

from fastapi import FastAPI

from src._core.infrastructure.persistence.rdb.database import Database
from src.admin_identity.domain.dtos.admin_identity_dto import AdminIdentityDTO
from src.admin_identity.interface.server.dependencies.admin_auth_dependencies import (
    get_current_admin,
)
from src.auth.interface.server.dependencies.auth_dependencies import get_current_user
from src.user.domain.dtos.user_dto import UserDTO


def override_database(app: FastAPI, test_db: Database) -> None:
    """Replace the running app's Database singleton with ``test_db``."""
    _core(app).database.override(test_db)


def reset_database_override(app: FastAPI) -> None:
    """Restore the original Database singleton."""
    _core(app).database.reset_override()


def override_current_user(app: FastAPI, current_user: UserDTO) -> None:
    """Replace the auth dependency with a fixed user for e2e tests."""

    async def _current_user_override() -> UserDTO:
        return current_user

    app.dependency_overrides[get_current_user] = _current_user_override


def reset_current_user_override(app: FastAPI) -> None:
    """Restore the real auth dependency."""
    app.dependency_overrides.pop(get_current_user, None)


def override_current_admin(app: FastAPI, current_admin: AdminIdentityDTO) -> None:
    """Replace the admin-realm dependency with a fixed admin for e2e tests."""

    async def _current_admin_override() -> AdminIdentityDTO:
        return current_admin

    app.dependency_overrides[get_current_admin] = _current_admin_override


def reset_current_admin_override(app: FastAPI) -> None:
    """Restore the real admin-realm dependency."""
    app.dependency_overrides.pop(get_current_admin, None)


def _core(app: FastAPI):
    return app.state.container.core_container()
