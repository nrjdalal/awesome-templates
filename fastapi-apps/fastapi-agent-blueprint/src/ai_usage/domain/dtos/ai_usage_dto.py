from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class AiUsageDTO(BaseModel):
    id: int = Field(..., description="AI usage log identifier")
    call_id: str = Field(..., description="Idempotency key for one logical call")
    request_id: str | None = Field(default=None, description="Request correlation ID")
    org_id: str | None = Field(default=None, description="Optional tenant hint")
    agent_name: str = Field(..., description="Agent or feature name")
    provider: str | None = Field(default=None, description="Model provider")
    model: str = Field(..., description="Model name")
    status: str = Field(..., description="Call status")
    occurred_at: datetime = Field(..., description="Actual call timestamp")
    duration_ms: int | None = Field(default=None, description="Call duration")

    input_tokens: int = Field(..., description="Input token count")
    output_tokens: int = Field(..., description="Output token count")
    cache_read_tokens: int = Field(..., description="Cache-read token count")
    cache_write_tokens: int = Field(..., description="Cache-write token count")
    reasoning_tokens: int = Field(..., description="Reasoning token count")
    total_tokens: int = Field(..., description="Total recorded token count")
    requests: int = Field(..., description="Provider request count")

    provider_cost_amount: Decimal | None = Field(
        default=None, description="Optional provider cost snapshot"
    )
    provider_cost_currency: str | None = Field(
        default=None, description="Provider cost currency"
    )
    provider_cost_source: str | None = Field(
        default=None, description="Provider cost source"
    )

    prompt_name: str | None = Field(default=None, description="Prompt name")
    prompt_version: str | None = Field(default=None, description="Prompt version label")
    prompt_source: str | None = Field(default=None, description="Prompt source")
    external_prompt_ref: str | None = Field(
        default=None, description="External prompt reference"
    )

    trace_id: str | None = Field(default=None, description="Optional trace ID")
    span_id: str | None = Field(default=None, description="Optional span ID")
    error_code: str | None = Field(default=None, description="Sanitized error code")
    usage_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Provider usage metadata only; excludes raw prompts, model outputs, "
            "message bodies, user input, and raw provider error text."
        ),
    )
    created_at: datetime = Field(..., description="Row creation timestamp")


class AiUsageSummaryDTO(BaseModel):
    call_count: int = Field(..., description="Number of usage rows")
    request_count: int = Field(..., description="Total provider requests")
    input_tokens: int = Field(..., description="Total input tokens")
    output_tokens: int = Field(..., description="Total output tokens")
    cache_read_tokens: int = Field(..., description="Total cache-read tokens")
    cache_write_tokens: int = Field(..., description="Total cache-write tokens")
    reasoning_tokens: int = Field(..., description="Total reasoning tokens")
    total_tokens: int = Field(..., description="Total tokens")


class AiUsageByOrgDTO(AiUsageSummaryDTO):
    org_id: str | None = Field(default=None, description="Optional tenant hint")
