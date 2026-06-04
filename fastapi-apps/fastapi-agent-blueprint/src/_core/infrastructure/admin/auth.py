from __future__ import annotations

from collections.abc import Callable

import structlog
from nicegui import app, ui
from pydantic import ValidationError

from src._core.exceptions.base_exception import BaseCustomException
from src._core.infrastructure.admin.audit import AdminAction, AuditResult
from src._core.infrastructure.admin.audit.logger import get_audit_logger
from src.admin_identity.application.use_cases.admin_account_use_case import (
    AdminAccountUseCase,
)
from src.admin_identity.application.use_cases.admin_auth_use_case import (
    AdminAuthUseCase,
)
from src.admin_identity.domain.dtos.admin_identity_dto import (
    ADMIN_SESSION_ROLE,
    AdminSessionDTO,
)
from src.admin_identity.domain.exceptions.admin_identity_exceptions import (
    AdminCredentialDisabledException,
    AdminInvalidCredentialsException,
    AdminSetupRequiredException,
)
from src.admin_identity.interface.server.schemas.admin_auth_schema import (
    AdminLoginRequest,
)

_logger = structlog.stdlib.get_logger(__name__)
_admin_auth_provider: AdminAuthProvider | None = None
_admin_account_use_case_provider: Callable[[], AdminAccountUseCase] | None = None


class AdminAuthProvider:
    """admin_identity-domain backed admin authentication provider."""

    def __init__(
        self, admin_auth_use_case_provider: Callable[[], AdminAuthUseCase]
    ) -> None:
        self._admin_auth_use_case_provider = admin_auth_use_case_provider

    async def authenticate(
        self,
        username: str,
        password: str,
        *,
        ip_address: str | None = None,
    ) -> AdminSessionDTO:
        """Authenticate and return session. Raises on bad credentials or setup state.

        Records an audit entry (#196 Phase 1): LOGIN success on return,
        LOGIN failure on credential/disabled exceptions (with the exception's
        ``error_code`` as ``failure_reason`` — never the raw message). The
        bootstrap-required path is not audited here; the setup flow logs
        ``FIRST_ADMIN_CREATE`` once the first real admin lands.
        """
        try:
            request = AdminLoginRequest(
                username=username or "", password=password or ""
            )
        except ValidationError as exc:
            # No session yet → actor user_id is explicitly None (don't auto-fill
            # from any stale session storage).
            await get_audit_logger().log(
                action=AdminAction.LOGIN,
                domain="auth",
                result=AuditResult.FAILURE,
                admin_user_id=None,
                admin_username=username or "unknown",
                failure_reason=AdminInvalidCredentialsException().error_code,
                ip_address=ip_address,
            )
            raise AdminInvalidCredentialsException() from exc

        try:
            session = await self._admin_auth_use_case_provider().admin_login(request)
        except (
            AdminInvalidCredentialsException,
            AdminCredentialDisabledException,
        ) as exc:
            await get_audit_logger().log(
                action=AdminAction.LOGIN,
                domain="auth",
                result=AuditResult.FAILURE,
                admin_user_id=None,
                admin_username=username or "unknown",
                failure_reason=exc.error_code,
                ip_address=ip_address,
            )
            raise
        except AdminSetupRequiredException:
            # Bootstrap → setup wizard. The setup flow records FIRST_ADMIN_CREATE
            # itself once the first real admin is created; this branch is not a
            # login event in its own right.
            raise

        await get_audit_logger().log(
            action=AdminAction.LOGIN,
            domain="auth",
            result=AuditResult.SUCCESS,
            admin_user_id=session.user_id,
            admin_username=session.username,
            ip_address=ip_address,
        )
        return session

    async def refresh_session(self) -> AdminSessionDTO | None:
        """Re-derive session from DB. Returns None if user is gone or not admin."""
        user_id = app.storage.user.get("user_id")
        try:
            parsed_user_id = int(user_id)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return None

        try:
            session = await self._admin_auth_use_case_provider().get_admin_session(
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
            and app.storage.user.get("role") == ADMIN_SESSION_ROLE
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
        ui.navigate.to("/admin/")
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

    Used by: /admin/ (dashboard), /admin/change-password.
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
