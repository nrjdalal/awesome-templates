"""Admin audit log infrastructure (#196 Phase 1).

Side effect: importing this package registers the ``AdminAuditLog`` model on
``Base.metadata`` so it is picked up by ``Base.metadata.create_all()``
(quickstart / e2e test conftest) and Alembic autogenerate.

This package intentionally does NOT re-export the ``logger`` module — that
module imports ``nicegui`` (admin extra) and would break the minimal-install
boot path. Admin-only callers (`bootstrap_admin`, the admin pages) import
``AuditLogger`` / ``configure_audit_logger`` / ``get_audit_logger`` directly
from :mod:`src._core.infrastructure.admin.audit.logger`.
"""

from src._core.infrastructure.admin.audit.dtos.audit_log_dto import (
    AdminAction,
    AuditLogDTO,
    AuditLogFilter,
    AuditLogSummaryDTO,
    AuditResult,
)
from src._core.infrastructure.admin.audit.models.audit_log_model import AdminAuditLog
from src._core.infrastructure.admin.audit.repository import AdminAuditLogRepository
from src._core.infrastructure.admin.audit.safe_state import safe_user_snapshot

__all__ = [
    "AdminAction",
    "AdminAuditLog",
    "AdminAuditLogRepository",
    "AuditLogDTO",
    "AuditLogFilter",
    "AuditLogSummaryDTO",
    "AuditResult",
    "safe_user_snapshot",
]
