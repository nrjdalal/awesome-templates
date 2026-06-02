"""Dashboard read facade for the admin landing page.

Isolates **all** data gathering for ``/admin/`` so the page file
(``pages/dashboard.py``) stays a thin renderer (Codex cross-review: a core
admin landing page must not embed cross-domain orchestration, dynamic service
probing, or error isolation inline).

Design invariants:

* **Never raises into the caller.** Each metric source is fetched in its own
  best-effort block; one failing source degrades *that* section to an explicit
  "unavailable" state (``count=None`` / ``audit_recent=None``) and is recorded
  via structlog. The dashboard as a whole never breaks because one service is
  down.
* **No raw exception text leaves this module.** Failures are logged with
  ``error_type`` only; the UI renders a neutral "Unavailable" marker. This keeps
  the no-``str(exc)``-leak invariant (#195) intact end to end.
* **CRUD contract stays minimal.** ``count_datas`` is implemented by every
  ``BaseService`` but is intentionally *not* on ``AdminCrudServiceProtocol``.
  The single dynamic ``getattr`` probe is quarantined here rather than widening
  the shared CRUD protocol just to feed a dashboard.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass, field

import structlog

from src._core.infrastructure.admin.audit.dtos.audit_log_dto import (
    AuditLogFilter,
    AuditLogSummaryDTO,
    AuditResult,
)
from src._core.infrastructure.admin.audit.logger import get_audit_repository
from src._core.infrastructure.admin.base_admin_page import BaseAdminPage

_logger = structlog.stdlib.get_logger(__name__)

DEFAULT_RECENT_LIMIT = 8


@dataclass(frozen=True)
class DomainCount:
    """Per-domain record count for a stat card. ``count is None`` => unavailable."""

    domain_name: str
    display_name: str
    icon: str
    count: int | None


@dataclass(frozen=True)
class AuditMetrics:
    """Audit-derived metrics for the recent window. ``recent is None`` => unavailable."""

    recent: list[AuditLogSummaryDTO] | None
    total: int | None
    failures: int | None
    by_action: dict[str, int] = field(default_factory=dict)

    @property
    def available(self) -> bool:
        return self.recent is not None


@dataclass(frozen=True)
class DashboardMetrics:
    """Everything the landing page renders. Always fully populated (no raises)."""

    domain_counts: list[DomainCount]
    audit: AuditMetrics


async def _count_for(config: BaseAdminPage) -> DomainCount:
    """Best-effort record count for one domain; ``count=None`` on any failure."""
    count: int | None
    try:
        service = config._get_service()
        # count_datas lives on BaseService but not on AdminCrudServiceProtocol;
        # probe dynamically here so the shared protocol stays a minimal CRUD
        # contract (Codex cross-review).
        count_datas = getattr(service, "count_datas", None)
        if count_datas is None:
            raise AttributeError("service does not implement count_datas")
        count = await count_datas()
    except Exception as exc:  # noqa: BLE001 - per-card isolation, swallowed by design
        _logger.warning(
            "dashboard_count_failed",
            domain=config.domain_name,
            error_type=type(exc).__name__,
        )
        count = None
    return DomainCount(
        domain_name=config.domain_name,
        display_name=config.display_name,
        icon=config.icon,
        count=count,
    )


async def _collect_audit(recent_limit: int) -> AuditMetrics:
    """Best-effort recent-audit metrics; all-``None`` when the repo is unavailable."""
    try:
        repo = get_audit_repository()
        recent, total = await repo.list_filtered(
            AuditLogFilter(), page=1, page_size=recent_limit
        )
    except Exception as exc:  # noqa: BLE001 - isolated, swallowed by design
        _logger.warning("dashboard_audit_failed", error_type=type(exc).__name__)
        return AuditMetrics(recent=None, total=None, failures=None)

    failures = sum(1 for row in recent if row.result == AuditResult.FAILURE)
    by_action: dict[str, int] = {}
    for row in recent:
        key = row.action.value
        by_action[key] = by_action.get(key, 0) + 1
    return AuditMetrics(
        recent=list(recent),
        total=total,
        failures=failures,
        by_action=by_action,
    )


async def collect_dashboard_metrics(
    visible_configs: Sequence[BaseAdminPage],
    *,
    include_audit: bool = True,
    recent_limit: int = DEFAULT_RECENT_LIMIT,
) -> DashboardMetrics:
    """Gather all landing-page metrics concurrently, isolating per-source failures.

    ``visible_configs`` must already be permission-filtered by the caller — this
    facade does not enforce authorization, it only reads what it is handed.

    ``include_audit`` gates the audit read entirely: callers without the
    ``audit_log`` permission pass ``False`` so the audit repository is **never
    touched** (least-privilege / data-minimization — a caller who may not see
    audit data must not cause it to be read server-side, and must not trigger
    audit-backend warnings on their dashboard).
    """
    counts = asyncio.gather(*(_count_for(cfg) for cfg in visible_configs))
    if include_audit:
        domain_counts, audit = await asyncio.gather(
            counts, _collect_audit(recent_limit)
        )
    else:
        domain_counts = await counts
        audit = AuditMetrics(recent=None, total=None, failures=None)
    return DashboardMetrics(domain_counts=list(domain_counts), audit=audit)
