"""SQLAlchemy model for the admin audit log table (#196 Phase 1).

Append-only — the Phase-1 repository only inserts. Querying (filters / detail
diff) ships in Phase 2 alongside the ``/admin/audit-log`` UI.
"""

from sqlalchemy import (
    BigInteger,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from src._core.infrastructure.persistence.rdb.database import Base


class AdminAuditLog(Base):
    """Persistent record of every admin action — login/logout, account
    management, password change, etc. (#196).

    ``admin_username`` is the durable actor reference — denormalized so entries
    survive deletion of the acting admin. ``admin_user_id`` is correlation-only
    and carries no foreign key; see the column comment and ADR 057 (#348).
    """

    __tablename__ = "admin_audit_log"
    __table_args__ = (
        # Common access patterns: list ordered by time, filtered by actor /
        # action / domain. Composite indexes cover both the filter column and
        # the time ordering used by the (Phase-2) audit-log page.
        Index("idx_audit_created_at", "created_at"),
        Index("idx_audit_user_created", "admin_username", "created_at"),
        Index("idx_audit_action_created", "action", "created_at"),
        Index("idx_audit_domain_created", "domain", "created_at"),
    )

    # BigInteger for prod (Postgres) so the audit log doesn't outgrow INT range;
    # SQLite variant uses INTEGER because SQLite autoincrement is gated to that
    # type. Mirrors the pattern in ``ai_usage.AIUsageLogModel``.
    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )

    # Deliberately unconstrained. This carried a foreign key to ``user.id`` with
    # ``ON DELETE SET NULL`` until ADR 057 (#348), which was wrong twice over:
    #
    # - The value is an ``admin_identity.id`` (ADR 049 / #218), not a customer
    #   id. Migration 0009 copied admins across *preserving ids* and advanced
    #   only ``admin_identity``'s sequence, so the two id spaces overlap — a
    #   constraint against either table can be satisfied by the wrong row and
    #   certify that a customer performed an admin action.
    # - ``SET NULL`` let a non-audit code path rewrite append-only evidence.
    #   0009's ``DELETE FROM "user" WHERE role = 'admin'`` ran *after* 0007
    #   created the constraint, nulling the actor on every pre-#218 row on
    #   PostgreSQL/MySQL while SQLite (which does not enforce foreign keys)
    #   kept them.
    #
    # Integrity now lives on the read side and in CI, not in the DDL — see
    # tests/unit/_core/infrastructure/admin/audit/test_audit_actor_fk.py.
    admin_user_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment=(
            "admin_identity.id of the actor. Realm-scoped and correlation-only:"
            " never join to user. admin_username is the durable reference."
        ),
    )
    admin_username: Mapped[str] = mapped_column(String(255), nullable=False)

    action: Mapped[str] = mapped_column(String(50), nullable=False)
    domain: Mapped[str] = mapped_column(String(100), nullable=False)
    # String so non-int IDs (UUIDs, slugs) fit without schema change.
    record_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    before_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    result: Mapped[str] = mapped_column(String(20), nullable=False)
    # Error code only — never raw exception messages (codex must-fix).
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    # asgi-correlation-id UUID4 hex / dashed.
    correlation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    created_at: Mapped[DateTime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
