"""Integration smoke: ``AdminAuthProvider.authenticate`` emits audit entries.

End-to-end unit test of the LOGIN audit hook — fakes both the auth use case
and the audit logger, then asserts the right ``AdminAction`` / ``AuditResult`` /
``failure_reason`` show up for success and credential-failure paths (#196).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src._core.infrastructure.admin import auth as admin_auth
from src._core.infrastructure.admin.audit import AdminAction, AuditResult
from src._core.infrastructure.admin.audit import logger as audit_logger_module
from src._core.infrastructure.admin.audit.logger import configure_audit_logger
from src.auth.domain.dtos.auth_dto import AdminSessionDTO
from src.auth.domain.exceptions.auth_exceptions import InvalidCredentialsException
from src.user.domain.dtos.user_dto import USER_ROLE_ADMIN


class _RecordingAuditLogger:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def log(self, **kwargs) -> None:
        self.calls.append(kwargs)


class _FakeUseCase:
    def __init__(
        self, session: AdminSessionDTO | None = None, exc: Exception | None = None
    ) -> None:
        self.session = session or AdminSessionDTO(
            user_id=7, username="alice", role=USER_ROLE_ADMIN, permissions=[]
        )
        self.exc = exc

    async def admin_login(self, request):
        if self.exc:
            raise self.exc
        return self.session


@pytest.fixture
def audit_recorder(monkeypatch):
    recorder = _RecordingAuditLogger()
    # Force get_audit_logger() to return our recorder.
    monkeypatch.setattr(audit_logger_module, "_audit_logger", recorder)
    # Also stub nicegui app/ui in admin_auth so authenticate doesn't touch globals.
    monkeypatch.setattr(
        admin_auth, "app", SimpleNamespace(storage=SimpleNamespace(user={}))
    )
    monkeypatch.setattr(
        admin_auth, "ui", SimpleNamespace(navigate=SimpleNamespace(to=lambda *_: None))
    )
    yield recorder
    # Restore unconfigured state for any subsequent tests.
    monkeypatch.setattr(audit_logger_module, "_audit_logger", None)


@pytest.mark.asyncio
async def test_authenticate_success_emits_login_success_audit(audit_recorder):
    provider = admin_auth.AdminAuthProvider(lambda: _FakeUseCase())

    session = await provider.authenticate("alice", "secret", ip_address="192.0.2.5")

    assert session.username == "alice"
    assert len(audit_recorder.calls) == 1
    call = audit_recorder.calls[0]
    assert call["action"] is AdminAction.LOGIN
    assert call["result"] is AuditResult.SUCCESS
    assert call["admin_user_id"] == 7
    assert call["admin_username"] == "alice"
    assert call["ip_address"] == "192.0.2.5"


@pytest.mark.asyncio
async def test_authenticate_invalid_credentials_emits_login_failure_audit(
    audit_recorder,
):
    fake_uc = _FakeUseCase(exc=InvalidCredentialsException())
    provider = admin_auth.AdminAuthProvider(lambda: fake_uc)

    with pytest.raises(InvalidCredentialsException):
        await provider.authenticate("attacker", "wrong", ip_address="192.0.2.6")

    assert len(audit_recorder.calls) == 1
    call = audit_recorder.calls[0]
    assert call["action"] is AdminAction.LOGIN
    assert call["result"] is AuditResult.FAILURE
    # No session yet on failure — actor is the input username, not a user_id.
    assert call["admin_user_id"] is None
    assert call["admin_username"] == "attacker"
    # Only error_code, never the raw exception message:
    assert call["failure_reason"] == "INVALID_CREDENTIALS"
    assert "message" not in str(call.get("failure_reason", ""))


@pytest.mark.asyncio
async def test_authenticate_empty_input_logs_failure_with_invalid_credentials(
    audit_recorder,
):
    provider = admin_auth.AdminAuthProvider(lambda: _FakeUseCase())

    with pytest.raises(InvalidCredentialsException):
        await provider.authenticate("", "")

    assert len(audit_recorder.calls) == 1
    call = audit_recorder.calls[0]
    assert call["action"] is AdminAction.LOGIN
    assert call["result"] is AuditResult.FAILURE
    assert call["failure_reason"] == "INVALID_CREDENTIALS"


def test_configure_audit_logger_smoke():
    """configure_audit_logger replaces the module-level logger reference."""
    sentinel = object()
    configure_audit_logger(sentinel)  # type: ignore[arg-type]
    try:
        assert audit_logger_module._audit_logger is sentinel
    finally:
        configure_audit_logger(None)  # type: ignore[arg-type]
        audit_logger_module._audit_logger = None
