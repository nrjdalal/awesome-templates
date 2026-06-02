"""Unit tests for the audit logger facade and safe-state serializer (#196)."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest

from src._core.infrastructure.admin.audit import (
    AdminAction,
    AuditLogDTO,
    AuditResult,
    safe_user_snapshot,
)
from src._core.infrastructure.admin.audit import logger as logger_module
from src._core.infrastructure.admin.audit.logger import (
    AuditLogger,
    configure_audit_logger,
    get_audit_logger,
)
from src.admin_identity.domain.dtos.admin_identity_dto import AdminIdentityDTO

# ── safe_user_snapshot whitelist ─────────────────────────────────────────────


def _user(**overrides) -> AdminIdentityDTO:
    now = datetime.now()
    defaults: dict = {
        "id": 7,
        "username": "alice",
        "full_name": "Alice Doe",
        "email": "alice@example.com",
        "password": "hashed-bcrypt-secret",
        "password_temporary": False,
        "permissions": ["accounts"],
        "is_bootstrap_admin": False,
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)
    return AdminIdentityDTO(**defaults)


def test_safe_user_snapshot_excludes_password_hash():
    snap = safe_user_snapshot(_user())
    assert snap is not None
    assert "password" not in snap
    # Whitelisted fields are present:
    for required in (
        "id",
        "username",
        "full_name",
        "email",
        "permissions",
        "is_bootstrap_admin",
        "password_temporary",
        "created_at",
        "updated_at",
    ):
        assert required in snap


def test_safe_user_snapshot_none_passthrough():
    assert safe_user_snapshot(None) is None


def test_safe_user_snapshot_json_ready_datetime():
    snap = safe_user_snapshot(_user())
    assert isinstance(snap["created_at"], str)  # ISO string, not datetime


# ── AuditLogger.log ──────────────────────────────────────────────────────────


class _RecordingRepository:
    def __init__(self, *, raise_on_insert: bool = False) -> None:
        self.inserted: list[AuditLogDTO] = []
        self._raise = raise_on_insert

    async def insert(self, dto: AuditLogDTO) -> None:
        if self._raise:
            raise RuntimeError("simulated DB outage")
        self.inserted.append(dto)


@pytest.fixture
def session_storage(monkeypatch):
    """Fake NiceGUI ``app.storage.user`` for the logger's auto-fill path."""
    storage: dict[str, object] = {"user_id": 42, "username": "alice"}
    fake_app = SimpleNamespace(storage=SimpleNamespace(user=storage))
    monkeypatch.setattr(logger_module, "app", fake_app)
    monkeypatch.setattr(
        logger_module,
        "_correlation_id",
        SimpleNamespace(get=lambda: "cid-abc"),
    )
    return storage


@pytest.mark.asyncio
async def test_log_persists_dto_with_action_result_and_correlation(session_storage):
    repo = _RecordingRepository()
    logger = AuditLogger(repo)

    await logger.log(
        action=AdminAction.ACCOUNT_CREATE,
        domain="user",
        result=AuditResult.SUCCESS,
        record_id="99",
        after_state={"id": 99},
    )

    assert len(repo.inserted) == 1
    dto = repo.inserted[0]
    assert dto.action is AdminAction.ACCOUNT_CREATE
    assert dto.result is AuditResult.SUCCESS
    assert dto.domain == "user"
    assert dto.record_id == "99"
    assert dto.correlation_id == "cid-abc"
    # auto-filled from session
    assert dto.admin_user_id == 42
    assert dto.admin_username == "alice"


@pytest.mark.asyncio
async def test_log_caller_overrides_session_actor(session_storage):
    repo = _RecordingRepository()
    logger = AuditLogger(repo)

    # Login-failure path: caller passes admin_username from the input form;
    # no session exists yet, so explicit args must take precedence.
    await logger.log(
        action=AdminAction.LOGIN,
        domain="auth",
        result=AuditResult.FAILURE,
        admin_username="attacker",
        admin_user_id=None,
        failure_reason="INVALID_CREDENTIALS",
        ip_address="192.0.2.1",
    )

    dto = repo.inserted[-1]
    assert dto.admin_username == "attacker"
    assert dto.admin_user_id is None
    assert dto.failure_reason == "INVALID_CREDENTIALS"
    assert dto.ip_address == "192.0.2.1"


@pytest.mark.asyncio
async def test_log_clamps_overlong_admin_username(session_storage):
    """LOGIN-failure path can be handed an arbitrary submitted username — the
    audit row must still persist even if the value exceeds the column width."""
    repo = _RecordingRepository()
    logger = AuditLogger(repo)

    overlong = "x" * 1000

    await logger.log(
        action=AdminAction.LOGIN,
        domain="auth",
        result=AuditResult.FAILURE,
        admin_user_id=None,
        admin_username=overlong,
        failure_reason="INVALID_CREDENTIALS",
    )

    dto = repo.inserted[-1]
    assert len(dto.admin_username) == 255
    assert dto.admin_username == overlong[:255]


@pytest.mark.asyncio
async def test_log_swallows_repository_errors(session_storage):
    """Audit write must never raise into the caller (codex must-fix)."""
    repo = _RecordingRepository(raise_on_insert=True)
    logger = AuditLogger(repo)

    # Should not raise — failure is swallowed and surfaced via structlog warning.
    await logger.log(
        action=AdminAction.LOGOUT,
        domain="auth",
        result=AuditResult.SUCCESS,
    )


@pytest.mark.asyncio
async def test_log_handles_unavailable_session_storage(monkeypatch):
    """Outside a request scope, ``app.storage.user`` raises — auto-fill must
    degrade to ``admin_username='unknown'`` rather than crash."""

    class _NoRequest:
        @property
        def user(self):
            raise RuntimeError("no request scope")

    monkeypatch.setattr(logger_module, "app", SimpleNamespace(storage=_NoRequest()))
    monkeypatch.setattr(
        logger_module, "_correlation_id", SimpleNamespace(get=lambda: None)
    )

    repo = _RecordingRepository()
    logger = AuditLogger(repo)

    await logger.log(
        action=AdminAction.LOGIN,
        domain="auth",
        result=AuditResult.SUCCESS,
    )

    dto = repo.inserted[-1]
    assert dto.admin_username == "unknown"
    assert dto.admin_user_id is None
    assert dto.correlation_id is None


# ── Module provider fallback ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_audit_logger_returns_noop_when_unconfigured(monkeypatch):
    """An unconfigured admin runtime must still not break login flows."""
    monkeypatch.setattr(logger_module, "_audit_logger", None)
    # Reset the warned-once flag so the test is independent of order.
    monkeypatch.setattr(logger_module._NoopAuditLogger, "_warned", False, raising=False)

    fallback = get_audit_logger()
    # Calling log() on the noop is a no-op and must not raise.
    await fallback.log(
        action=AdminAction.LOGIN,
        domain="auth",
        result=AuditResult.SUCCESS,
    )


@pytest.mark.asyncio
async def test_configure_audit_logger_replaces_fallback(monkeypatch, session_storage):
    repo = _RecordingRepository()
    real = AuditLogger(repo)
    monkeypatch.setattr(logger_module, "_audit_logger", None)
    configure_audit_logger(real)
    try:
        assert get_audit_logger() is real
        await get_audit_logger().log(
            action=AdminAction.LOGIN,
            domain="auth",
            result=AuditResult.SUCCESS,
        )
        assert len(repo.inserted) == 1
    finally:
        # Restore default unconfigured state so other tests are unaffected.
        monkeypatch.setattr(logger_module, "_audit_logger", None)
