"""admin: add admin_audit_log table for #196 Phase 1

Revision ID: 0007_add_admin_audit_log
Revises: 0006_add_user_admin_permission_fields
Create Date: 2026-05-28

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007_add_admin_audit_log"
down_revision: str | None = "0006_add_user_admin_permission_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "admin_audit_log",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            primary_key=True,
            autoincrement=True,
            nullable=False,
        ),
        sa.Column(
            "admin_user_id",
            sa.Integer(),
            sa.ForeignKey("user.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("admin_username", sa.String(length=255), nullable=False),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("domain", sa.String(length=100), nullable=False),
        sa.Column("record_id", sa.String(length=128), nullable=True),
        sa.Column("before_state", sa.JSON(), nullable=True),
        sa.Column("after_state", sa.JSON(), nullable=True),
        sa.Column("result", sa.String(length=20), nullable=False),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("correlation_id", sa.String(length=36), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    # Composite indexes cover the common filter+sort patterns
    # ((field, created_at DESC)) the Phase-2 audit-log UI will use.
    op.create_index(
        "idx_audit_created_at", "admin_audit_log", ["created_at"]
    )
    op.create_index(
        "idx_audit_user_created",
        "admin_audit_log",
        ["admin_username", "created_at"],
    )
    op.create_index(
        "idx_audit_action_created",
        "admin_audit_log",
        ["action", "created_at"],
    )
    op.create_index(
        "idx_audit_domain_created",
        "admin_audit_log",
        ["domain", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_audit_domain_created", table_name="admin_audit_log")
    op.drop_index("idx_audit_action_created", table_name="admin_audit_log")
    op.drop_index("idx_audit_user_created", table_name="admin_audit_log")
    op.drop_index("idx_audit_created_at", table_name="admin_audit_log")
    op.drop_table("admin_audit_log")
