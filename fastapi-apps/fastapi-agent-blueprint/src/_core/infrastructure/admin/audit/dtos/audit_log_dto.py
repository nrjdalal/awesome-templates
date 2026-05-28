"""DTOs and enums for the admin audit log (#196 Phase 1).

`action` is the verb (LOGIN, ACCOUNT_DELETE, ...). `result` is the outcome
(SUCCESS / FAILURE). They are kept orthogonal — no compound enums like
``LOGIN_SUCCESS`` (codex must-fix: action+result normalization).
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class AdminAction(StrEnum):
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    ACCOUNT_CREATE = "ACCOUNT_CREATE"
    ACCOUNT_DELETE = "ACCOUNT_DELETE"
    PERMISSIONS_UPDATE = "PERMISSIONS_UPDATE"
    PASSWORD_CHANGE = "PASSWORD_CHANGE"  # noqa: S105 - action name, not a credential
    FIRST_ADMIN_CREATE = "FIRST_ADMIN_CREATE"
    # Read events (#206 Phase 2). Per-domain opt-in via ``BaseAdminPage.log_reads``.
    VIEW_LIST = "VIEW_LIST"
    VIEW_DETAIL = "VIEW_DETAIL"


class AuditResult(StrEnum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"


class AuditLogDTO(BaseModel):
    """Pydantic carrier for an audit log row. Mirrors ``AdminAuditLog`` columns."""

    id: int | None = None
    admin_user_id: int | None = None
    admin_username: str
    action: AdminAction
    domain: str
    record_id: str | None = None
    before_state: dict | None = None
    after_state: dict | None = None
    result: AuditResult
    # error_code from a domain exception, or a type name fallback. NEVER a raw
    # ``str(exc)`` (codex must-fix: no raw exception messages in audit).
    failure_reason: str | None = None
    ip_address: str | None = None
    correlation_id: str | None = None
    created_at: datetime | None = Field(default=None)


class AuditLogSummaryDTO(BaseModel):
    """Lightweight projection used by the audit-log UI list view (#206 Phase 2).

    Intentionally omits ``before_state`` / ``after_state`` so the AG Grid list
    payload stays small; the detail dialog fetches the full ``AuditLogDTO``
    on demand via ``AdminAuditLogRepository.get_by_id``.
    """

    id: int
    admin_user_id: int | None = None
    admin_username: str
    action: AdminAction
    domain: str
    record_id: str | None = None
    result: AuditResult
    failure_reason: str | None = None
    ip_address: str | None = None
    correlation_id: str | None = None
    created_at: datetime


class AuditLogFilter(BaseModel):
    """Immutable filter VO consumed by ``AdminAuditLogRepository.list_filtered``.

    All fields optional / list-empty means "no constraint on this axis".
    ``since`` / ``until`` are half-open: created_at >= since AND created_at < until.
    """

    model_config = {"frozen": True}

    username_like: str | None = None  # case-insensitive substring match
    actions: tuple[AdminAction, ...] = ()
    domains: tuple[str, ...] = ()
    result: AuditResult | None = None
    since: datetime | None = None
    until: datetime | None = None
