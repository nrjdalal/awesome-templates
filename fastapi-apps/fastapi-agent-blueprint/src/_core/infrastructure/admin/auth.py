from collections.abc import Callable

import structlog
from nicegui import app, ui
from pydantic import ValidationError

from src._core.exceptions.base_exception import BaseCustomException
from src.auth.application.use_cases.auth_use_case import AuthUseCase
from src.auth.domain.dtos.auth_dto import AdminSessionDTO
from src.auth.domain.exceptions.auth_exceptions import InvalidCredentialsException
from src.auth.interface.server.schemas.auth_schema import LoginRequest
from src.user.domain.dtos.user_dto import USER_ROLE_ADMIN

_logger = structlog.stdlib.get_logger(__name__)
_admin_auth_provider: "AdminAuthProvider | None" = None


class AdminAuthProvider:
    """Auth-domain backed admin authentication provider."""

    def __init__(self, auth_use_case_provider: Callable[[], AuthUseCase]) -> None:
        self._auth_use_case_provider = auth_use_case_provider

    async def authenticate(self, username: str, password: str) -> AdminSessionDTO:
        try:
            request = LoginRequest(username=username or "", password=password or "")
        except ValidationError as exc:
            raise InvalidCredentialsException() from exc
        return await self._auth_use_case_provider().admin_login(request)

    async def refresh_session(self) -> bool:
        user_id = app.storage.user.get("user_id")
        try:
            parsed_user_id = int(user_id)
        except (TypeError, ValueError):
            return False

        try:
            session = await self._auth_use_case_provider().get_admin_session(
                parsed_user_id
            )
        except BaseCustomException as exc:
            _logger.warning(
                "admin_session_denied",
                error_code=exc.error_code,
            )
            return False
        except Exception:
            _logger.exception("admin_session_refresh_failed")
            return False

        self.login(session)
        return True

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
        app.storage.user["authenticated"] = False
        app.storage.user.pop("user_id", None)
        app.storage.user.pop("username", None)
        app.storage.user.pop("role", None)


def configure_admin_auth_provider(provider: AdminAuthProvider) -> None:
    global _admin_auth_provider
    _admin_auth_provider = provider


def get_admin_auth_provider() -> AdminAuthProvider:
    if _admin_auth_provider is None:
        raise RuntimeError("Admin auth provider is not configured")
    return _admin_auth_provider


async def require_auth() -> bool:
    """Guard function. Call at the top of every admin page.

    Returns False and redirects to login if not authenticated.
    """
    if not AdminAuthProvider.is_authenticated():
        AdminAuthProvider.logout()
        ui.navigate.to("/admin/login")
        return False
    if not await get_admin_auth_provider().refresh_session():
        AdminAuthProvider.logout()
        ui.navigate.to("/admin/login")
        return False
    return True
