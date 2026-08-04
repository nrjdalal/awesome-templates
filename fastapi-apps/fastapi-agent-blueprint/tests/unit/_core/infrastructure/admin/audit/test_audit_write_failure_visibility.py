"""A dropped audit write must be loud (#348, ADR 057).

`AuditLogger.log` never raises — locking an operator out of the dashboard over
an audit hiccup would be worse than the hiccup. That contract is kept. What
changed is everything around it.

Before ADR 057 the fallback logged at `warning` with `action`, `domain`,
`result` and `error_type`, and its own comment claimed the dropped event was
"reconstructable from these non-sensitive fields". It was not: the actor and the
target were both omitted, so the record said *something* failed and nothing
about who or what. Nothing alerted. That is how a wrong foreign key destroyed
every authenticated admin audit write on PostgreSQL for two releases.

These tests pin the three properties that make the swallow survivable:

1. it still does not raise,
2. the log line carries enough identity to reconstruct the entry,
3. a failure reaches `ErrorNotifier`, and a constraint rejection is
   distinguishable from any other failure.
"""

from __future__ import annotations

import pytest
import structlog
from structlog.testing import capture_logs

from src._core.infrastructure.admin.audit.dtos.audit_log_dto import (
    AdminAction,
    AuditResult,
)
from src._core.infrastructure.admin.audit.logger import AuditLogger
from src._core.infrastructure.persistence.rdb.exceptions import DatabaseException


class _ExplodingRepository:
    """Stands in for a repository whose insert fails."""

    def __init__(self, exc: Exception) -> None:
        self._exc = exc
        self.calls = 0

    async def insert(self, dto) -> None:
        self.calls += 1
        raise self._exc


class _RecordingNotifier:
    def __init__(self) -> None:
        self.dispatched: list[dict] = []

    def maybe_dispatch(
        self, *, status_code: int, error_code: str, message: str
    ) -> None:
        self.dispatched.append(
            {"status_code": status_code, "error_code": error_code, "message": message}
        )


class _RaisingNotifier:
    def maybe_dispatch(self, **_kwargs) -> None:
        raise RuntimeError("notifier is broken too")


def _integrity_error() -> DatabaseException:
    """What `Database.session()` actually raises on a constraint violation.

    It translates `IntegrityError` into a curated `DatabaseException` carrying
    this `error_code`, so a raw `IntegrityError` never reaches the logger — the
    same detection `user_repository` and `admin_identity_repository` use.
    """
    return DatabaseException(
        status_code=400,
        message="Data integrity error",
        error_code="DB_INTEGRITY_ERROR",
    )


async def _log_once(repository, notifier=None) -> list[dict]:
    logger = AuditLogger(repository, error_notifier=notifier)
    with capture_logs() as logs:
        await logger.log(
            action=AdminAction.LOGIN,
            domain="auth",
            result=AuditResult.SUCCESS,
            record_id="rec-7",
            admin_user_id=900_002,
            admin_username="someone",
        )
    return logs


@pytest.fixture(autouse=True)
def _reset_structlog():
    # cache_logger_on_first_use=True makes capture_logs order-dependent; the
    # repo-wide fixture does this too, repeated here so this file is honest on
    # its own.
    structlog.reset_defaults()
    yield
    structlog.reset_defaults()


@pytest.mark.asyncio
async def test_write_failure_does_not_raise_into_the_caller():
    repository = _ExplodingRepository(RuntimeError("db down"))

    await _log_once(repository)

    assert repository.calls == 1


@pytest.mark.asyncio
async def test_failure_is_logged_at_error_with_enough_identity():
    logs = await _log_once(_ExplodingRepository(RuntimeError("db down")))

    entry = next(log for log in logs if log["event"] == "audit_write_failed")
    assert entry["log_level"] == "error"
    # The three fields the old version omitted, which is what made the dropped
    # event unreconstructable.
    assert entry["admin_username"] == "someone"
    assert entry["admin_user_id"] == 900_002
    assert entry["record_id"] == "rec-7"
    assert entry["error_type"] == "RuntimeError"


@pytest.mark.asyncio
async def test_failure_log_still_excludes_unvetted_state():
    logs = await _log_once(_ExplodingRepository(RuntimeError("db down")))

    entry = next(log for log in logs if log["event"] == "audit_write_failed")
    for field in ("before_state", "after_state", "failure_reason"):
        assert field not in entry


@pytest.mark.asyncio
async def test_constraint_rejection_has_its_own_event_name():
    logs = await _log_once(_ExplodingRepository(_integrity_error()))

    events = {log["event"] for log in logs}
    assert "audit_write_rejected_by_constraint" in events
    assert "audit_write_failed" not in events


@pytest.mark.asyncio
async def test_failure_is_dispatched_to_the_error_notifier():
    notifier = _RecordingNotifier()

    await _log_once(_ExplodingRepository(_integrity_error()), notifier)

    assert len(notifier.dispatched) == 1
    dispatched = notifier.dispatched[0]
    # 500 regardless of the DatabaseException's own 400: losing an audit record
    # is an operational incident, and the default
    # NOTIFICATION_SEVERITY_THRESHOLD is 500.
    assert dispatched["status_code"] == 500
    assert dispatched["error_code"] == "audit_write_rejected_by_constraint"
    assert "DatabaseException" in dispatched["message"]


@pytest.mark.asyncio
async def test_dispatch_is_skipped_when_no_notifier_is_wired():
    # Unit tests and notification-disabled deployments construct the logger
    # without one; that must not become a second failure.
    logs = await _log_once(_ExplodingRepository(RuntimeError("db down")), None)

    assert any(log["event"] == "audit_write_failed" for log in logs)


@pytest.mark.asyncio
async def test_a_broken_notifier_cannot_break_the_audit_path():
    logs = await _log_once(
        _ExplodingRepository(RuntimeError("db down")), _RaisingNotifier()
    )

    events = {log["event"] for log in logs}
    assert "audit_write_failed" in events
    assert "audit_write_failure_notify_failed" in events


@pytest.mark.asyncio
async def test_unset_actor_is_rendered_readably():
    """A failure before actor auto-fill is diagnostically different.

    Omitting the parameters entirely leaves them as the `_UNSET` sentinel. A raw
    `object()` repr in a log line tells the reader nothing, so it renders as
    `<unset>` — which distinguishes "failed before we knew the actor" from
    "actor was genuinely unknown" (the login-failure path, which passes None).
    """
    logger = AuditLogger(_ExplodingRepository(RuntimeError("db down")))
    with capture_logs() as logs:
        await logger.log(
            action=AdminAction.LOGIN, domain="auth", result=AuditResult.FAILURE
        )

    entry = next(log for log in logs if log["event"] == "audit_write_failed")
    assert entry["admin_user_id"] in ("<unset>", None)


@pytest.mark.asyncio
async def test_a_provider_is_resolved_lazily_not_at_construction():
    """Regression guard for the ordering trap this wiring first fell into.

    `bootstrap_admin` passes the container *provider*, not a resolved notifier.
    Resolving at construction builds the shared `_noop_notification_client`
    Singleton, which logs `notification_client_disabled` from `__init__` — so an
    eager resolve consumed that one-time warning at boot and
    `test_noop_notification_client_disabled_warning_emitted_once` observed zero
    instead of one. `bootstrap.py` warns about exactly this for the database
    provider; the notifier has the same hazard plus a side effect.
    """
    resolved: list[int] = []
    notifier = _RecordingNotifier()

    def provider():
        resolved.append(1)
        return notifier

    logger = AuditLogger(_ExplodingRepository(RuntimeError("db down")), provider)
    assert resolved == [], "provider was resolved at construction time"

    with capture_logs():
        await logger.log(
            action=AdminAction.LOGIN, domain="auth", result=AuditResult.SUCCESS
        )

    assert resolved == [1]
    assert len(notifier.dispatched) == 1
