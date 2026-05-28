"""Phase 2 (#206) tests — repository query/delete, ``@audit_action`` decorator,
permission registry, scheduler discovery, and retention setting validation.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from src._core.infrastructure.admin.audit import (
    AdminAction,
    AdminAuditLogRepository,
    AuditLogDTO,
    AuditLogFilter,
    AuditResult,
)
from src._core.infrastructure.admin.audit import logger as audit_logger_module
from src._core.infrastructure.admin.audit.logger import (
    AuditLogger,
    audit_action,
    configure_audit_repository,
    get_audit_repository,
)
from src._core.infrastructure.admin.audit.models.audit_log_model import AdminAuditLog
from src._core.infrastructure.admin.permission_registry import (
    _FIXED_KEYS,
    AdminPermissionRegistry,
)
from src.user.infrastructure.database.models.user_model import (  # noqa: F401
    UserModel,
)

# ── Recording fixtures ──────────────────────────────────────────────────────


class _RecordingAuditLogger:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def log(self, **kwargs) -> None:
        self.calls.append(kwargs)


@pytest.fixture
def audit_recorder(monkeypatch):
    recorder = _RecordingAuditLogger()
    monkeypatch.setattr(audit_logger_module, "_audit_logger", recorder)
    yield recorder
    monkeypatch.setattr(audit_logger_module, "_audit_logger", None)


# ── Repository: list_filtered / get_by_id / delete_older_than ───────────────


async def _insert_row(repo, **overrides) -> None:
    base = {
        "admin_user_id": 1,
        "admin_username": "alice",
        "action": AdminAction.LOGIN,
        "domain": "auth",
        "result": AuditResult.SUCCESS,
    }
    base.update(overrides)
    await repo.insert(AuditLogDTO(**base))


@pytest.mark.asyncio
async def test_list_filtered_by_action_and_pagination(test_db):
    repo = AdminAuditLogRepository(test_db)

    # seed: 3 LOGIN, 2 ACCOUNT_DELETE, 1 LOGOUT
    for _ in range(3):
        await _insert_row(repo, action=AdminAction.LOGIN)
    for _ in range(2):
        await _insert_row(repo, action=AdminAction.ACCOUNT_DELETE, domain="user")
    await _insert_row(repo, action=AdminAction.LOGOUT)

    rows, total = await repo.list_filtered(
        AuditLogFilter(actions=(AdminAction.LOGIN,)), page=1, page_size=2
    )
    assert total >= 3  # at least the three LOGIN entries we inserted in this session
    assert len(rows) == 2
    assert all(r.action is AdminAction.LOGIN for r in rows)


@pytest.mark.asyncio
async def test_list_filtered_username_like_and_result(test_db):
    repo = AdminAuditLogRepository(test_db)
    await _insert_row(repo, admin_username="alice_p2", result=AuditResult.FAILURE)
    await _insert_row(repo, admin_username="bob_p2", result=AuditResult.FAILURE)
    await _insert_row(repo, admin_username="alice_p2", result=AuditResult.SUCCESS)

    rows, _total = await repo.list_filtered(
        AuditLogFilter(username_like="alice_p2", result=AuditResult.FAILURE)
    )
    assert all(r.admin_username == "alice_p2" for r in rows)
    assert all(r.result is AuditResult.FAILURE for r in rows)


@pytest.mark.asyncio
async def test_list_filtered_omits_before_after_state(test_db):
    repo = AdminAuditLogRepository(test_db)
    await _insert_row(
        repo,
        admin_username="hassnap",
        action=AdminAction.ACCOUNT_DELETE,
        domain="user",
        before_state={"id": 7, "username": "victim"},
        after_state=None,
    )

    rows, _ = await repo.list_filtered(AuditLogFilter(username_like="hassnap"))
    row = rows[0]
    # AuditLogSummaryDTO must not expose JSON snapshots (codex must-fix 3).
    assert not hasattr(row, "before_state")
    assert not hasattr(row, "after_state")


@pytest.mark.asyncio
async def test_get_by_id_returns_full_dto_with_state(test_db):
    repo = AdminAuditLogRepository(test_db)
    await _insert_row(
        repo,
        admin_username="detail_target",
        action=AdminAction.PERMISSIONS_UPDATE,
        domain="user",
        before_state={"permissions": ["accounts"]},
        after_state={"permissions": ["accounts", "audit_log"]},
    )

    # find the row id via list_filtered (small DB)
    rows, _ = await repo.list_filtered(AuditLogFilter(username_like="detail_target"))
    audit_id = rows[0].id
    full = await repo.get_by_id(audit_id)

    assert full is not None
    assert full.before_state == {"permissions": ["accounts"]}
    assert full.after_state == {"permissions": ["accounts", "audit_log"]}


@pytest.mark.asyncio
async def test_get_by_id_returns_none_for_missing(test_db):
    repo = AdminAuditLogRepository(test_db)
    assert await repo.get_by_id(99_999_999) is None


@pytest.mark.asyncio
async def test_list_filtered_accepts_timezone_aware_since(test_db):
    """codex must-fix: tz-aware datetimes must be normalized to naive UTC
    before binding against the tz-naive ``created_at`` column."""
    repo = AdminAuditLogRepository(test_db)
    await _insert_row(repo, admin_username="tzcheck")

    aware_since = datetime.now(UTC) - timedelta(hours=1)  # tz-aware
    rows, _total = await repo.list_filtered(
        AuditLogFilter(username_like="tzcheck", since=aware_since)
    )
    # Should not raise; the inserted row from the last hour is included.
    assert any(r.admin_username == "tzcheck" for r in rows)


@pytest.mark.asyncio
async def test_delete_older_than_only_removes_old(test_db):
    repo = AdminAuditLogRepository(test_db)

    # Seed a fresh row.
    await _insert_row(repo, admin_username="fresh_p2")
    fresh_count_before, _ = (
        (await repo.list_filtered(AuditLogFilter(username_like="fresh_p2"))),
        None,
    )

    # Backdate one row directly to ensure something is older than cutoff.
    async with test_db.session() as session:
        old = AdminAuditLog(
            admin_user_id=2,
            admin_username="old_p2",
            action=AdminAction.LOGIN.value,
            domain="auth",
            result=AuditResult.SUCCESS.value,
            created_at=datetime.now(UTC) - timedelta(days=400),
        )
        session.add(old)
        await session.commit()

    cutoff = datetime.now(UTC) - timedelta(days=180)
    deleted = await repo.delete_older_than(cutoff)
    assert deleted >= 1

    # Fresh row survives.
    rows, _ = await repo.list_filtered(AuditLogFilter(username_like="fresh_p2"))
    assert any(r.admin_username == "fresh_p2" for r in rows)
    rows_old, _ = await repo.list_filtered(AuditLogFilter(username_like="old_p2"))
    assert all(r.admin_username != "old_p2" for r in rows_old)


# ── @audit_action decorator ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_audit_action_logs_success_and_returns_value(audit_recorder):
    @audit_action(action=AdminAction.ACCOUNT_CREATE, domain="user")
    async def create_account(name: str) -> str:
        return f"ok:{name}"

    result = await create_account("alice")

    assert result == "ok:alice"
    assert len(audit_recorder.calls) == 1
    call = audit_recorder.calls[0]
    assert call["action"] is AdminAction.ACCOUNT_CREATE
    assert call["result"] is AuditResult.SUCCESS


@pytest.mark.asyncio
async def test_audit_action_logs_failure_then_reraises(audit_recorder):
    class _BizError(Exception):
        error_code = "BIZ_X"

    @audit_action(action=AdminAction.ACCOUNT_DELETE, domain="user")
    async def delete_account() -> None:
        raise _BizError("boom")

    with pytest.raises(_BizError):
        await delete_account()

    assert len(audit_recorder.calls) == 1
    call = audit_recorder.calls[0]
    assert call["result"] is AuditResult.FAILURE
    assert call["failure_reason"] == "BIZ_X"


@pytest.mark.asyncio
async def test_audit_action_before_fn_failure_swallowed(audit_recorder):
    async def bad_before(*_args, **_kwargs):
        raise RuntimeError("before broke")

    @audit_action(
        action=AdminAction.PERMISSIONS_UPDATE, domain="user", before_fn=bad_before
    )
    async def update_perms() -> str:
        return "ok"

    result = await update_perms()  # must not raise
    assert result == "ok"
    assert audit_recorder.calls[-1]["result"] is AuditResult.SUCCESS
    # Hook failure ⇒ before_state stays None
    assert audit_recorder.calls[-1].get("before_state") is None


@pytest.mark.asyncio
async def test_audit_action_after_fn_failure_swallowed(audit_recorder):
    async def bad_after(*_args, **_kwargs):
        raise RuntimeError("after broke")

    @audit_action(action=AdminAction.ACCOUNT_CREATE, domain="user", after_fn=bad_after)
    async def create_account() -> str:
        return "value"

    assert await create_account() == "value"
    assert audit_recorder.calls[-1].get("after_state") is None


# ── Permission registry ─────────────────────────────────────────────────────


def test_audit_log_is_fixed_permission_key():
    assert "audit_log" in _FIXED_KEYS
    assert "audit_log" in AdminPermissionRegistry().all_keys()


# ── Repository provider ─────────────────────────────────────────────────────


def test_get_audit_repository_raises_when_unconfigured(monkeypatch):
    monkeypatch.setattr(audit_logger_module, "_audit_repository", None)
    with pytest.raises(RuntimeError, match="not configured"):
        get_audit_repository()


def test_configure_audit_repository_replaces(monkeypatch):
    repo_sentinel = SimpleNamespace(name="sentinel")
    monkeypatch.setattr(audit_logger_module, "_audit_repository", None)
    configure_audit_repository(repo_sentinel)  # type: ignore[arg-type]
    try:
        assert get_audit_repository() is repo_sentinel
    finally:
        monkeypatch.setattr(audit_logger_module, "_audit_repository", None)


# ── Scheduler discovery ─────────────────────────────────────────────────────


def test_scheduler_registers_audit_cleanup_task():
    """Importing the scheduler must surface the audit cleanup task's schedule
    label so ``LabelScheduleSource`` finds it."""
    from src._apps.worker import scheduler as scheduler_module

    assert scheduler_module.scheduler is not None
    # The task module must be importable and decorated — the @broker.task call
    # is what registers the task on the broker. Direct attribute check:
    from src._apps.worker.tasks import audit_cleanup_task as task_mod

    fn = task_mod.audit_cleanup_task
    # Taskiq stores labels on the decorated task (the wrapped object has a
    # ``labels`` attribute mapping); the exact shape is internal, so we assert
    # it exists with the expected ``schedule`` entry.
    labels = getattr(fn, "labels", None) or getattr(
        getattr(fn, "_taskiq_task", None), "labels", None
    )
    if labels is None:
        # Fallback: inspect broker._tasks for the registered name.
        from src._apps.worker.broker import broker

        names = list(getattr(broker, "_tasks", {}) or {}) + list(
            getattr(broker, "tasks", {}) or {}
        )
        assert any("audit_cleanup" in n for n in names), (
            "audit_cleanup_task not registered on broker"
        )
    else:
        assert "schedule" in labels


# ── Retention setting validation ────────────────────────────────────────────


def test_retention_setting_default_is_90():
    from src._core.config import Settings

    settings = Settings()
    assert settings.audit_log_retention_days == 90


def test_retention_setting_rejects_out_of_range(monkeypatch):
    from pydantic import ValidationError

    from src._core.config import Settings

    monkeypatch.setenv("AUDIT_LOG_RETENTION_DAYS", "0")
    with pytest.raises(ValidationError):
        Settings()

    monkeypatch.setenv("AUDIT_LOG_RETENTION_DAYS", "99999")
    with pytest.raises(ValidationError):
        Settings()
