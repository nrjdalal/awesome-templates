from __future__ import annotations

from collections.abc import Callable

import structlog
from nicegui import app, ui
from pydantic import ValidationError

from src._core.exceptions.base_exception import BaseCustomException
from src.auth.application.use_cases.admin_account_use_case import AdminAccountUseCase
from src.auth.application.use_cases.auth_use_case import AuthUseCase
from src.auth.domain.dtos.auth_dto import AdminSessionDTO
from src.auth.domain.exceptions.auth_exceptions import InvalidCredentialsException
from src.auth.interface.server.schemas.auth_schema import LoginRequest
from src.user.domain.dtos.user_dto import USER_ROLE_ADMIN

_logger = structlog.stdlib.get_logger(__name__)
_admin_auth_provider: AdminAuthProvider | None = None
_admin_account_use_case_provider: Callable[[], AdminAccountUseCase] | None = None


class AdminAuthProvider:
    """Auth-domain backed admin authentication provider."""

    def __init__(self, auth_use_case_provider: Callable[[], AuthUseCase]) -> None:
        self._auth_use_case_provider = auth_use_case_provider

    async def authenticate(self, username: str, password: str) -> AdminSessionDTO:
        """Authenticate and return session. Raises on bad credentials or setup state."""
        try:
            request = LoginRequest(username=username or "", password=password or "")
        except ValidationError as exc:
            raise InvalidCredentialsException() from exc
        return await self._auth_use_case_provider().admin_login(request)

    async def refresh_session(self) -> AdminSessionDTO | None:
        """Re-derive session from DB. Returns None if user is gone or not admin."""
        user_id = app.storage.user.get("user_id")
        try:
            parsed_user_id = int(user_id)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return None

        try:
            session = await self._auth_use_case_provider().get_admin_session(
                parsed_user_id
            )
        except BaseCustomException as exc:
            _logger.warning("admin_session_denied", error_code=exc.error_code)
            return None
        except Exception:
            _logger.exception("admin_session_refresh_failed")
            return None

        self._write_session(session)
        return session

    @staticmethod
    def is_authenticated() -> bool:
        return (
            app.storage.user.get("authenticated", False) is True
            and app.storage.user.get("role") == USER_ROLE_ADMIN
            and app.storage.user.get("user_id") is not None
        )

    @staticmethod
    def login(session: AdminSessionDTO) -> None:
        app.storage.user["authenticated"] = True
        app.storage.user["user_id"] = session.user_id
        app.storage.user["username"] = session.username
        app.storage.user["role"] = session.role

    @staticmethod
    def logout() -> None:
        for key in ("authenticated", "user_id", "username", "role"):
            app.storage.user.pop(key, None)

    @staticmethod
    def _write_session(session: AdminSessionDTO) -> None:
        """Sync IC-155-1 keys to storage (no new keys added)."""
        app.storage.user["authenticated"] = True
        app.storage.user["user_id"] = session.user_id
        app.storage.user["username"] = session.username
        app.storage.user["role"] = session.role


def configure_admin_auth_provider(provider: AdminAuthProvider) -> None:
    global _admin_auth_provider
    _admin_auth_provider = provider


def get_admin_auth_provider() -> AdminAuthProvider:
    if _admin_auth_provider is None:
        raise RuntimeError("Admin auth provider is not configured")
    return _admin_auth_provider


async def require_auth(*, page_key: str) -> AdminSessionDTO | None:
    """Page-level auth gate. Must be called at the top of every /admin/... page.

    Returns the fresh AdminSessionDTO on success (use it to filter nav / dashboard).
    Returns None and redirects after setting up the redirect response.

    page_key must match an AdminPermissionRegistry key.  Dashboard and other
    allowlisted pages use require_auth_allowlisted() instead.
    """
    if not AdminAuthProvider.is_authenticated():
        AdminAuthProvider.logout()
        ui.navigate.to("/admin/login")
        return None

    provider = get_admin_auth_provider()
    session = await provider.refresh_session()
    if session is None:
        AdminAuthProvider.logout()
        ui.navigate.to("/admin/login")
        return None

    if session.password_temporary:
        ui.navigate.to("/admin/change-password")
        return None

    if page_key not in session.permissions:
        ui.navigate.to("/admin/dashboard")
        return None

    return session


def configure_admin_account_use_case_provider(
    provider: Callable[[], AdminAccountUseCase],
) -> None:
    global _admin_account_use_case_provider
    _admin_account_use_case_provider = provider


def get_admin_account_use_case() -> AdminAccountUseCase:
    if _admin_account_use_case_provider is None:
        raise RuntimeError("Admin account use case provider is not configured")
    return _admin_account_use_case_provider()


async def require_auth_allowlisted() -> AdminSessionDTO | None:
    """Auth gate for pages that don't require a specific page permission.

    Used by: /admin/dashboard, /admin/change-password.
    Redirects unauthenticated users to login.
    Does NOT check page-level permissions.
    """
    if not AdminAuthProvider.is_authenticated():
        AdminAuthProvider.logout()
        ui.navigate.to("/admin/login")
        return None

    provider = get_admin_auth_provider()
    session = await provider.refresh_session()
    if session is None:
        AdminAuthProvider.logout()
        ui.navigate.to("/admin/login")
        return None

    return session
