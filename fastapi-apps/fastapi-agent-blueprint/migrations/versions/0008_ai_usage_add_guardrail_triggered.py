"""ai_usage: add guardrail_triggered column for #197 Phase 5

Revision ID: 0008_ai_usage_add_guardrail_triggered
Revises: 0007_add_admin_audit_log
Create Date: 2026-06-01

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0008_ai_usage_add_guardrail_triggered"
down_revision: str | None = "0007_add_admin_audit_log"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # server_default=false() lets the NOT NULL add succeed on existing rows
    # (SQLite + Postgres). The Python-side default on the ORM column keeps
    # new inserts coherent even before the DB default is read back.
    op.add_column(
        "ai_usage_log",
        sa.Column(
            "guardrail_triggered",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    # Backs the guardrail-observability query (sparse True + time window).
    op.create_index(
        "ix_ai_usage_log_guardrail_occurred",
        "ai_usage_log",
        ["guardrail_triggered", "occurred_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_ai_usage_log_guardrail_occurred", table_name="ai_usage_log")
    op.drop_column("ai_usage_log", "guardrail_triggered")
