from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from src._core.infrastructure.persistence.rdb.database import Base


class AiUsageModel(Base):
    __tablename__ = "ai_usage_log"
    __table_args__ = (
        CheckConstraint(
            "status IN ('ok', 'error', 'timeout', 'rate_limited')",
            name="ck_ai_usage_log_status",
        ),
        CheckConstraint(
            "prompt_source IS NULL OR prompt_source IN ('inline', 'langfuse', 'self')",
            name="ck_ai_usage_log_prompt_source",
        ),
        CheckConstraint(
            "provider_cost_source IS NULL OR "
            "provider_cost_source IN ('response', 'estimated', 'manual')",
            name="ck_ai_usage_log_provider_cost_source",
        ),
        CheckConstraint(
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
        CheckConstraint(
            "provider_cost_currency IS NULL OR length(provider_cost_currency) = 3",
            name="ck_ai_usage_log_provider_cost_currency_len",
        ),
        UniqueConstraint("call_id", name="uq_ai_usage_log_call_id"),
        Index("ix_ai_usage_log_org_occurred", "org_id", "occurred_at"),
        Index(
            "ix_ai_usage_log_agent_occurred",
            "agent_name",
            "occurred_at",
        ),
        Index("ix_ai_usage_log_model_occurred", "model", "occurred_at"),
        Index("ix_ai_usage_log_status_occurred", "status", "occurred_at"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    call_id: Mapped[str] = mapped_column(String(64), nullable=False)
    request_id: Mapped[str | None] = mapped_column(String(128), index=True)
    org_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    agent_name: Mapped[str] = mapped_column(String(100), nullable=False)
    provider: Mapped[str | None] = mapped_column(String(40), nullable=True)
    model: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ok")
    occurred_at: Mapped[DateTime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cache_read_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cache_write_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reasoning_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    requests: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    provider_cost_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(20, 10), nullable=True
    )
    provider_cost_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    provider_cost_source: Mapped[str | None] = mapped_column(String(20), nullable=True)

    prompt_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    prompt_source: Mapped[str | None] = mapped_column(String(20), nullable=True)
    external_prompt_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)

    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    span_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    usage_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        comment=(
            "Provider usage metadata only; excludes raw prompts, model outputs, "
            "message bodies, user input, and raw provider error text."
        ),
    )
    created_at: Mapped[DateTime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
