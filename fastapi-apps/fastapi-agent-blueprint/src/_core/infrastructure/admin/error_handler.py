"""Centralized error handling for NiceGUI admin pages (#195).

Single source of truth for how admin-side errors are surfaced to the operator,
logged, and (for critical failures) escalated to the dedicated ``/admin/error``
page.

Design rules:
- Only ``BaseCustomException`` with ``status_code < 500`` is treated as a
  user-safe message; everything else (>= 500 domain errors and arbitrary
  exceptions) surfaces a generic message. The raw ``str(exc)`` is NEVER shown
  to the UI — full detail goes to the structured server log only.
- The current admin username is read from NiceGUI session storage so every
  error log carries actor context; ``request_id`` is injected automatically by
  the structlog processor pipeline.
- Critical failures redirect to ``/admin/error`` and pass the correlation id as
  a query parameter (``?rid=``) rather than mutating session storage, which is
  reserved for auth keys.
"""

from __future__ import annotations

import functools
from collections.abc import Awaitable, Callable
from typing import TypeVar
from urllib.parse import quote

import structlog
from asgi_correlation_id import correlation_id
from nicegui import app, ui

from src._core.exceptions.base_exception import BaseCustomException

_logger = structlog.stdlib.get_logger(__name__)

_GENERIC_MESSAGE = "An unexpected error occurred. Please try again later."

F = TypeVar("F", bound=Callable[..., Awaitable[object]])


def _is_user_safe(exc: Exception) -> bool:
    """True only for domain (4xx) exceptions whose message is operator-authored."""
    return isinstance(exc, BaseCustomException) and exc.status_code < 500


def _current_admin_user() -> str | None:
    """Best-effort admin username for log context.

    Returns ``None`` when NiceGUI session storage is unavailable — e.g. when the
    global ``on_exception`` handler fires outside a client/request context.
    """
    try:
        return app.storage.user.get("username")
    except Exception:  # noqa: BLE001 - storage unavailable outside a request scope
        return None


class AdminErrorHandler:
    """Shared admin error surface: sanitized notify + structured log + escalate."""

    @staticmethod
    def _safe_message(exc: Exception) -> tuple[str, str]:
        """Return ``(message, notify_type)``; never leak ``str(exc)`` to the UI."""
        if _is_user_safe(exc):
            return exc.message, "warning"  # type: ignore[attr-defined]
        return _GENERIC_MESSAGE, "negative"

    @staticmethod
    def log_error(exc: Exception, context: str = "") -> None:
        """Emit a structured log with actor/page context and full server-side detail."""
        error_code = getattr(exc, "error_code", None)
        if _is_user_safe(exc):
            _logger.warning(
                "admin_page_error",
                context=context,
                admin_user=_current_admin_user(),
                error_type=type(exc).__name__,
                error_code=error_code,
            )
        else:
            _logger.exception(
                "admin_page_error",
                exc_info=exc,
                context=context,
                admin_user=_current_admin_user(),
                error_type=type(exc).__name__,
                error_code=error_code,
            )

    @staticmethod
    def notify_error(exc: Exception, context: str = "") -> None:
        """Surface a sanitized toast to the operator."""
        message, notify_type = AdminErrorHandler._safe_message(exc)
        ui.notify(message, type=notify_type)

    @staticmethod
    async def handle(exc: Exception, context: str = "", critical: bool = False) -> None:
        """Log the error, then either redirect (critical) or notify (non-critical).

        Critical failures escalate to ``/admin/error`` with the correlation id in
        the query string so the operator can quote it to support.
        """
        AdminErrorHandler.log_error(exc, context)
        if critical:
            rid = quote(correlation_id.get() or "", safe="")
            ui.navigate.to(f"/admin/error?rid={rid}")
            return
        AdminErrorHandler.notify_error(exc, context)


def admin_error_boundary(context: str = "", critical: bool = False) -> Callable[[F], F]:
    """Wrap a NiceGUI ``@ui.page`` handler so unhandled errors route through
    :class:`AdminErrorHandler`.

    Apply as the inner decorator (``@ui.page`` stays outermost). ``functools.wraps``
    preserves ``__wrapped__`` so NiceGUI/FastAPI signature introspection still
    injects path/query parameters into the original handler.

    Note: this only covers the page-load call. Event callbacks (button clicks)
    are separate invocations and must call ``AdminErrorHandler.handle`` directly.
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: object, **kwargs: object) -> object:
            try:
                return await func(*args, **kwargs)
            except Exception as exc:  # noqa: BLE001 - last-resort page boundary
                await AdminErrorHandler.handle(exc, context=context, critical=critical)
                return None

        return wrapper  # type: ignore[return-value]

    return decorator


def handle_uncaught_admin_exception(exc: Exception) -> None:
    """Global NiceGUI safety net — structured-log any uncaught admin exception.

    Registered via ``app.on_exception`` in ``bootstrap_admin``. NiceGUI invokes
    every registered handler (its default is ``log.exception``) for exceptions
    that escape page handlers, event callbacks, and timers, so this guarantees
    uniform structured logging even where a local ``try``/``except`` or
    ``@admin_error_boundary`` did not catch (e.g. a post-success ``refresh``).

    Log-only by design: the handler may fire outside a client/slot context where
    ``ui.notify`` / ``ui.navigate`` are invalid, so it never touches the UI.
    """
    AdminErrorHandler.log_error(exc, context="admin_uncaught")
