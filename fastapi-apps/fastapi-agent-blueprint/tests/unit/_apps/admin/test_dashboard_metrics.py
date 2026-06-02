"""Unit tests for the admin dashboard read facade.

Focus: the never-raise / per-source isolation invariants. One failing metric
source must degrade only its own section (``count=None`` / ``available=False``)
without raising or affecting the others, and no raw exception text escapes.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from src._apps.admin import dashboard_metrics as dm
from src._core.infrastructure.admin.audit.dtos.audit_log_dto import (
    AdminAction,
    AuditLogSummaryDTO,
    AuditResult,
)


class _FakeService:
    def __init__(self, count: int | Exception) -> None:
        self._count = count

    async def count_datas(self) -> int:
        if isinstance(self._count, Exception):
            raise self._count
        return self._count


class _ServiceWithoutCount:
    """Mimics a CRUD service that does not implement count_datas."""


class _FakeConfig:
    def __init__(self, name: str, service: object) -> None:
        self.domain_name = name
        self.display_name = name.title()
        self.icon = "folder"
        self._service = service

    def _get_service(self) -> object:
        return self._service


class _FakeRepo:
    def __init__(
        self,
        rows: list[AuditLogSummaryDTO],
        total: int,
        *,
        raise_exc: Exception | None = None,
    ) -> None:
        self._rows = rows
        self._total = total
        self._raise = raise_exc

    async def list_filtered(self, filter_vo, *, page: int, page_size: int):
        if self._raise is not None:
            raise self._raise
        return self._rows[:page_size], self._total


def _row(action: AdminAction, result: AuditResult) -> AuditLogSummaryDTO:
    return AuditLogSummaryDTO(
        id=1,
        admin_username="alice",
        action=action,
        domain="user",
        result=result,
        created_at=datetime(2026, 6, 2, 10, 0),
    )


def _patch_audit(monkeypatch: pytest.MonkeyPatch, repo: _FakeRepo) -> None:
    monkeypatch.setattr(dm, "get_audit_repository", lambda: repo)


async def test_happy_path_aggregates_counts_and_audit(monkeypatch):
    rows = [
        _row(AdminAction.LOGIN, AuditResult.SUCCESS),
        _row(AdminAction.LOGIN, AuditResult.FAILURE),
        _row(AdminAction.ACCOUNT_CREATE, AuditResult.SUCCESS),
    ]
    _patch_audit(monkeypatch, _FakeRepo(rows, total=42))
    configs = [
        _FakeConfig("user", _FakeService(10)),
        _FakeConfig("docs", _FakeService(5)),
    ]

    metrics = await dm.collect_dashboard_metrics(configs)  # type: ignore[arg-type]

    assert [(c.domain_name, c.count) for c in metrics.domain_counts] == [
        ("user", 10),
        ("docs", 5),
    ]
    assert metrics.audit.available is True
    assert metrics.audit.total == 42
    assert metrics.audit.failures == 1
    assert metrics.audit.by_action == {"LOGIN": 2, "ACCOUNT_CREATE": 1}


async def test_one_failing_count_is_isolated(monkeypatch):
    _patch_audit(monkeypatch, _FakeRepo([], total=0))
    configs = [
        _FakeConfig("user", _FakeService(10)),
        _FakeConfig("docs", _FakeService(RuntimeError("db down"))),
    ]

    metrics = await dm.collect_dashboard_metrics(configs)  # type: ignore[arg-type]

    counts = {c.domain_name: c.count for c in metrics.domain_counts}
    assert counts == {"user": 10, "docs": None}
    # Audit still works despite the count failure.
    assert metrics.audit.available is True


async def test_service_without_count_datas_degrades(monkeypatch):
    _patch_audit(monkeypatch, _FakeRepo([], total=0))
    configs = [_FakeConfig("legacy", _ServiceWithoutCount())]

    metrics = await dm.collect_dashboard_metrics(configs)  # type: ignore[arg-type]

    assert metrics.domain_counts[0].count is None


async def test_audit_unavailable_does_not_break_counts(monkeypatch):
    _patch_audit(
        monkeypatch, _FakeRepo([], total=0, raise_exc=RuntimeError("not configured"))
    )
    configs = [_FakeConfig("user", _FakeService(7))]

    metrics = await dm.collect_dashboard_metrics(configs)  # type: ignore[arg-type]

    assert metrics.domain_counts[0].count == 7
    assert metrics.audit.available is False
    assert metrics.audit.total is None
    assert metrics.audit.failures is None
    assert metrics.audit.by_action == {}


async def test_audit_not_read_when_not_included(monkeypatch):
    """Least privilege: include_audit=False must not touch the audit repository."""
    calls = {"count": 0}

    def _boom():
        calls["count"] += 1
        raise AssertionError("audit repository must not be accessed")

    monkeypatch.setattr(dm, "get_audit_repository", _boom)
    configs = [_FakeConfig("user", _FakeService(3))]

    metrics = await dm.collect_dashboard_metrics(configs, include_audit=False)  # type: ignore[arg-type]

    assert calls["count"] == 0
    assert metrics.domain_counts[0].count == 3
    assert metrics.audit.available is False
    assert metrics.audit.by_action == {}


async def test_empty_inputs(monkeypatch):
    _patch_audit(monkeypatch, _FakeRepo([], total=0))

    metrics = await dm.collect_dashboard_metrics([])

    assert metrics.domain_counts == []
    assert metrics.audit.available is True
    assert metrics.audit.total == 0
    assert metrics.audit.failures == 0
    assert metrics.audit.by_action == {}
