"""``AuditLogger`` facade — single entry point for recording admin actions (#196).

Design invariants (codex-reviewed):
- **Audit-write never raises into the caller.** A repository failure is
  swallowed and surfaced via structlog as a warning so that a transient DB
  hiccup cannot break the user action that triggered the log.
- **Actor + correlation auto-fill.** When ``admin_user_id`` / ``admin_username``
  are not passed (typical for instrumentation inside a NiceGUI page callback),
  they are read from ``app.storage.user``. ``correlation_id`` is read from
  ``asgi_correlation_id`` whenever available. Callers may override (e.g. the
  login flow passes ``admin_username=<input>`` for the FAILURE branch where no
  session exists yet).
- **No raw ``str(exc)``.** ``failure_reason`` is the caller-supplied
  ``error_code`` (or a type-name fallback); the exception's message is logged
  via structlog only, never persisted to the audit row.
"""

from __future__ import annotations

import functools
import inspect
from collections.abc import Awaitable, Callable
from typing import Any, ParamSpec, TypeVar

import structlog
from asgi_correlation_id import correlation_id as _correlation_id
from nicegui import app

from src._core.infrastructure.admin.audit.dtos.audit_log_dto import (
    AdminAction,
    AuditLogDTO,
    AuditResult,
)
from src._core.infrastructure.admin.audit.repository import AdminAuditLogRepository

_logger = structlog.stdlib.get_logger(__name__)

# Sentinel — distinguishes "argument not passed" (auto-fill from session) from
# "caller explicitly passed None" (do not auto-fill). Important for the LOGIN
# FAILURE path where the actor genuinely has no session yet, and any stale
# storage value would falsely attribute the failure to a logged-in user.
_UNSET = object()

# Match the ``admin_audit_log.admin_username`` column width. The LOGIN FAILURE
# path logs whatever the operator typed; a hostile / malformed value longer
# than the column would otherwise make the insert fail and (per the never-raise
# invariant) silently drop the audit row for that rejected login.
_ADMIN_USERNAME_MAX = 255


class AuditLogger:
    """Thin facade callers use to record an audit entry."""

    def __init__(self, repository: AdminAuditLogRepository) -> None:
        self._repository = repository

    async def log(
        self,
        *,
        action: AdminAction,
        domain: str,
        result: AuditResult,
        record_id: str | None = None,
        before_state: dict | None = None,
        after_state: dict | None = None,
        failure_reason: str | None = None,
        ip_address: str | None = None,
        admin_user_id: int | None = _UNSET,  # type: ignore[assignment]
        admin_username: str | None = _UNSET,  # type: ignore[assignment]
    ) -> None:
        """Best-effort write of one audit-log entry. Never raises.

        ``admin_user_id`` / ``admin_username`` are auto-filled from
        ``app.storage.user`` only when the caller did not pass them. Passing
        them explicitly (including ``None``) bypasses auto-fill — used by the
        LOGIN failure path where no session yet exists and we must not
        attribute the failure to a stale session.
        """

        # Wrap the ENTIRE operation — actor fill, DTO construction, AND insert —
        # in a single try/except so a malformed input or storage-access bug
        # cannot propagate into the caller and break a login or write action.
        try:
            if admin_user_id is _UNSET:
                admin_user_id = _safe_session_get("user_id")
            if admin_username is _UNSET:
                admin_username = _safe_session_get("username") or "unknown"
            # Defensive: explicit None ⇒ "unknown" (column is NOT NULL).
            if admin_username is None:
                admin_username = "unknown"
            # Clamp to the column width so an overlong / hostile login-failure
            # username cannot make the audit insert silently drop.
            if len(admin_username) > _ADMIN_USERNAME_MAX:
                admin_username = admin_username[:_ADMIN_USERNAME_MAX]

            dto = AuditLogDTO(
                admin_user_id=admin_user_id,
                admin_username=admin_username,
                action=action,
                domain=domain,
                record_id=record_id,
                before_state=before_state,
                after_state=after_state,
                result=result,
                failure_reason=failure_reason,
                ip_address=ip_address,
                correlation_id=_safe_correlation_id(),
            )
            await self._repository.insert(dto)
        except Exception as exc:  # noqa: BLE001 - swallowed by design
            # The dropped event is reconstructable from these non-sensitive
            # fields only (no before_state/after_state/failure_reason — they
            # may contain detail not yet vetted by the whitelist).
            _logger.warning(
                "audit_write_failed",
                exc_info=exc,
                action=getattr(action, "value", str(action)),
                domain=domain,
                result=getattr(result, "value", str(result)),
                error_type=type(exc).__name__,
            )


def _safe_session_get(key: str):
    """Best-effort NiceGUI session storage read; returns ``None`` outside a
    request scope (e.g. background tasks)."""
    try:
        return app.storage.user.get(key)
    except Exception:  # noqa: BLE001 - storage unavailable outside a request
        return None


def _safe_correlation_id() -> str | None:
    rid = _correlation_id.get()
    return rid or None


# ── Noop fallback ───────────────────────────────────────────────────────────


class _NoopAuditLogger:
    """Silent fallback used when ``configure_audit_logger`` has not been called.

    Honours the never-raise invariant — an admin runtime mis-wiring must not
    break logins or other user actions. Emits ONE no-payload warning per
    process so the missing wiring is still visible in logs without spamming and
    without forwarding any caller-supplied audit fields (before_state /
    failure_reason / etc. may contain detail not yet vetted for log emission).
    """

    _warned: bool = False

    async def log(self, **kwargs: object) -> None:  # signature-compatible
        if not _NoopAuditLogger._warned:
            _logger.warning("audit_logger_not_configured")
            _NoopAuditLogger._warned = True


_noop_audit_logger = _NoopAuditLogger()


# ── Module-level provider (auth.py-style configure pattern) ─────────────────

_audit_logger: AuditLogger | None = None


def configure_audit_logger(logger: AuditLogger) -> None:
    """Wire the process-wide audit logger from ``bootstrap_admin``."""
    global _audit_logger
    _audit_logger = logger


# Separate provider for the repository so the audit-log UI page can query
# (list_filtered / get_by_id / delete_older_than) without going through the
# logger facade. Configured alongside the logger in ``bootstrap_admin``.
_audit_repository: AdminAuditLogRepository | None = None


def configure_audit_repository(repository: AdminAuditLogRepository) -> None:
    """Wire the process-wide audit repository (used by the UI + cleanup task)."""
    global _audit_repository
    _audit_repository = repository


def get_audit_repository() -> AdminAuditLogRepository:
    """Return the configured audit repository.

    Raises ``RuntimeError`` when unconfigured — unlike the logger fallback,
    queries are explicit operator actions and a misconfiguration should be
    surfaced (caught by ``@admin_error_boundary`` on the audit-log page).
    """
    if _audit_repository is None:
        raise RuntimeError(
            "AuditLogRepository is not configured; "
            "call configure_audit_repository() in bootstrap_admin."
        )
    return _audit_repository


def get_audit_logger() -> AuditLogger | _NoopAuditLogger:
    """Return the configured audit logger, or a silent noop fallback.

    The noop fallback preserves the never-raise invariant even if
    ``configure_audit_logger`` was not called (e.g. a unit test that does not
    boot the admin runtime). It still surfaces the mis-wiring once via a
    structlog warning so it is discoverable in logs.
    """
    if _audit_logger is None:
        return _noop_audit_logger
    return _audit_logger


# ── @audit_action decorator (#206 Phase 2) ──────────────────────────────────

P = ParamSpec("P")
R = TypeVar("R")

# A capture hook may be sync or async; it receives the same positional/keyword
# arguments as the wrapped callable, plus ``result=`` on the after-hook path.
CaptureHook = Callable[..., Awaitable[dict | None] | dict | None]


async def _safe_capture(
    hook: CaptureHook | None,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    **extra: Any,
) -> dict | None:
    """Run an optional capture hook in best-effort mode.

    Returns ``None`` on any exception so a buggy ``before_fn`` / ``after_fn``
    cannot change the wrapped callable's result or raise.
    """
    if hook is None:
        return None
    try:
        result = hook(*args, **kwargs, **extra)
        if inspect.isawaitable(result):
            result = await result
        return result  # type: ignore[return-value]
    except Exception as exc:  # noqa: BLE001 - capture is best-effort
        _logger.warning(
            "audit_capture_hook_failed",
            exc_info=exc,
            hook=getattr(hook, "__qualname__", repr(hook)),
        )
        return None


def audit_action(
    action: AdminAction,
    domain: str,
    *,
    before_fn: CaptureHook | None = None,
    after_fn: CaptureHook | None = None,
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """Wrap an async write callable with SUCCESS / FAILURE audit logging.

    On exception, logs FAILURE (``failure_reason = exc.error_code`` or the
    exception type name) and **re-raises** so any outer ``@admin_error_boundary``
    still notifies the operator and the error stays visible. Audit-write
    failures are absorbed by :meth:`AuditLogger.log` (Phase 1 invariant).

    Optional ``before_fn`` / ``after_fn`` hooks let callers attach state
    snapshots; their own exceptions are swallowed via :func:`_safe_capture`
    so the audit subsystem cannot break the business operation.
    """

    def decorator(
        func: Callable[P, Awaitable[R]],
    ) -> Callable[P, Awaitable[R]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            before_state = await _safe_capture(before_fn, args, kwargs)
            try:
                result = await func(*args, **kwargs)
            except Exception as exc:  # noqa: BLE001 - boundary, re-raised below
                await get_audit_logger().log(
                    action=action,
                    domain=domain,
                    result=AuditResult.FAILURE,
                    before_state=before_state,
                    failure_reason=getattr(exc, "error_code", None)
                    or type(exc).__name__,
                )
                raise
            after_state = await _safe_capture(after_fn, args, kwargs, result=result)
            await get_audit_logger().log(
                action=action,
                domain=domain,
                result=AuditResult.SUCCESS,
                before_state=before_state,
                after_state=after_state,
            )
            return result

        return wrapper

    return decorator
