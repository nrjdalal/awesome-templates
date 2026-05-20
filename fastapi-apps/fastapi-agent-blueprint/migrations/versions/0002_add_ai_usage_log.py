"""ai_usage: add usage ledger

Revision ID: 0002_ai_usage_log
Revises: 0001_baseline_current_rdb
Create Date: 2026-04-29

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0002_ai_usage_log"
down_revision: Union[str, None] = "0001_baseline_current_rdb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_usage_log",
        sa.Column(
            "id",
            sa.BigInteger().with_variant(sa.Integer(), "sqlite"),
            autoincrement=True,
            nullable=False,
        ),
        sa.Column("call_id", sa.String(length=64), nullable=False),
        sa.Column("request_id", sa.String(length=128), nullable=True),
        sa.Column("org_id", sa.String(length=64), nullable=True),
        sa.Column("agent_name", sa.String(length=100), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=True),
        sa.Column("model", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("cache_read_tokens", sa.Integer(), nullable=False),
        sa.Column("cache_write_tokens", sa.Integer(), nullable=False),
        sa.Column("reasoning_tokens", sa.Integer(), nullable=False),
        sa.Column("total_tokens", sa.Integer(), nullable=False),
        sa.Column("requests", sa.Integer(), nullable=False),
        sa.Column("provider_cost_amount", sa.Numeric(20, 10), nullable=True),
        sa.Column("provider_cost_currency", sa.String(length=3), nullable=True),
        sa.Column("provider_cost_source", sa.String(length=20), nullable=True),
        sa.Column("prompt_name", sa.String(length=200), nullable=True),
        sa.Column("prompt_version", sa.String(length=50), nullable=True),
        sa.Column("prompt_source", sa.String(length=20), nullable=True),
        sa.Column("external_prompt_ref", sa.String(length=500), nullable=True),
        sa.Column("trace_id", sa.String(length=64), nullable=True),
        sa.Column("span_id", sa.String(length=64), nullable=True),
        sa.Column("error_code", sa.String(length=50), nullable=True),
        sa.Column(
            "usage_metadata",
            sa.JSON(),
            nullable=False,
            comment=(
                "Provider usage metadata only; excludes raw prompts, model outputs, "
                "message bodies, user input, and raw provider error text."
            ),
        ),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('ok', 'error', 'timeout', 'rate_limited')",
            name="ck_ai_usage_log_status",
        ),
        sa.CheckConstraint(
            "prompt_source IS NULL OR prompt_source IN ('inline', 'langfuse', 'self')",
            name="ck_ai_usage_log_prompt_source",
        ),
        sa.CheckConstraint(
            "provider_cost_source IS NULL OR "
            "provider_cost_source IN ('response', 'estimated', 'manual')",
            name="ck_ai_usage_log_provider_cost_source",
        ),
        sa.CheckConstraint(
            "("
            "provider_cost_amount IS NULL "
            "AND provider_cost_currency IS NULL "
            "AND provider_cost_source IS NULL"
            ") OR ("
            "provider_cost_amount IS NOT NULL "
            "AND provider_cost_currency IS NOT NULL "
            "AND provider_cost_source IS NOT NULL"
            ")",
            name="ck_ai_usage_log_provider_cost_all_or_none",
        ),
        sa.CheckConstraint(
            "provider_cost_currency IS NULL OR length(provider_cost_currency) = 3",
            name="ck_ai_usage_log_provider_cost_currency_len",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("call_id", name="uq_ai_usage_log_call_id"),
    )
    op.create_index("ix_ai_usage_log_request_id", "ai_usage_log", ["request_id"])
    op.create_index(
        "ix_ai_usage_log_org_occurred",
        "ai_usage_log",
        ["org_id", "occurred_at"],
    )
    op.create_index(
        "ix_ai_usage_log_agent_occurred",
        "ai_usage_log",
        ["agent_name", "occurred_at"],
    )
    op.create_index(
        "ix_ai_usage_log_model_occurred",
        "ai_usage_log",
        ["model", "occurred_at"],
    )
    op.create_index(
        "ix_ai_usage_log_status_occurred",
        "ai_usage_log",
        ["status", "occurred_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_ai_usage_log_status_occurred", table_name="ai_usage_log")
    op.drop_index("ix_ai_usage_log_model_occurred", table_name="ai_usage_log")
    op.drop_index("ix_ai_usage_log_agent_occurred", table_name="ai_usage_log")
    op.drop_index("ix_ai_usage_log_org_occurred", table_name="ai_usage_log")
    op.drop_index("ix_ai_usage_log_request_id", table_name="ai_usage_log")
    op.drop_table("ai_usage_log")
