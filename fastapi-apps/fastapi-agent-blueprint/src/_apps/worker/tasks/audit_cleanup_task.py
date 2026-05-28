"""Scheduled admin-audit retention cleanup (#206 Phase 2).

Delete ``admin_audit_log`` rows older than ``AUDIT_LOG_RETENTION_DAYS``. The
task is a regular ``@broker.task`` so it can be triggered three ways:

1. Automatically by ``TaskiqScheduler`` (preferred — run as a separate
   ``make scheduler`` process).
2. Manually enqueued by an external cron / k8s CronJob calling Taskiq from
   the deployment's own scheduler — useful for envs that don't run the
   Taskiq scheduler process (e.g. serverless workers).
3. From a one-off REPL / management command for ad-hoc cleanup.

The ``schedule`` label below is what ``LabelScheduleSource`` reads when the
Taskiq scheduler is up.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import structlog
from dependency_injector.wiring import Provide, inject

from src._apps.worker.broker import broker
from src._core.config import settings
from src._core.infrastructure.admin.audit import AdminAuditLogRepository
from src._core.infrastructure.di.core_container import CoreContainer
from src._core.infrastructure.persistence.rdb.database import Database

_logger = structlog.stdlib.get_logger(__name__)


def _naive_utc_now() -> datetime:
    """Naive UTC ``now()`` for comparison against ``AdminAuditLog.created_at``,
    which is a timezone-naive ``DateTime`` column. Avoids
    asyncpg/Postgres binding errors for aware datetimes against
    ``timestamp without time zone``."""
    return datetime.now(UTC).replace(tzinfo=None)


@broker.task(
    task_name=f"{settings.task_name_prefix}._core.admin.audit_cleanup",
    # Daily at 03:00 UTC. Adjust by env if needed; the schedule label is what
    # the Taskiq LabelScheduleSource reads, so external cron triggers ignore
    # it. NOTE: only effective when ``make scheduler`` is running.
    schedule=[{"cron": "0 3 * * *"}],
)
@inject
async def audit_cleanup_task(
    database: Database = Provide[CoreContainer.database],
) -> int:
    """Delete audit rows older than ``settings.audit_log_retention_days``.

    Returns the number of rows deleted (also logged as ``audit_log_cleanup``).
    """
    cutoff = _naive_utc_now() - timedelta(days=settings.audit_log_retention_days)
    repo = AdminAuditLogRepository(database)
    deleted = await repo.delete_older_than(cutoff)
    _logger.info(
        "audit_log_cleanup",
        deleted=deleted,
        cutoff=cutoff.isoformat(),
        retention_days=settings.audit_log_retention_days,
    )
    return deleted
