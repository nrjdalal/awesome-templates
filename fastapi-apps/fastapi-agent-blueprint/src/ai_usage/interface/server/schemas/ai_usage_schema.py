from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Self

from pydantic import Field, model_validator

from src._core.application.dtos.base_request import BaseRequest
from src._core.application.dtos.base_response import BaseResponse
from src._core.domain.value_objects.agent_usage_record import (
    PromptSource,
    ProviderCostSource,
    UsageStatus,
)


class CreateAiUsageRequest(BaseRequest):
    call_id: str = Field(..., min_length=1, max_length=64)
    request_id: str | None = Field(default=None, max_length=128)
    org_id: str | None = Field(default=None, max_length=64)
    agent_name: str = Field(..., min_length=1, max_length=100)
    provider: str | None = Field(default=None, max_length=40)
    model: str = Field(..., min_length=1, max_length=200)
    status: UsageStatus = "ok"
    occurred_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC).replace(tzinfo=None)
    )
    duration_ms: int | None = Field(default=None, ge=0)

    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    cache_read_tokens: int = Field(default=0, ge=0)
    cache_write_tokens: int = Field(default=0, ge=0)
    reasoning_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    requests: int = Field(default=1, ge=0)

    provider_cost_amount: Decimal | None = Field(default=None, ge=0)
    provider_cost_currency: str | None = Field(default=None, min_length=3, max_length=3)
    provider_cost_source: ProviderCostSource | None = None

    prompt_name: str | None = Field(default=None, max_length=200)
    prompt_version: str | None = Field(default=None, max_length=50)
    prompt_source: PromptSource | None = None
    external_prompt_ref: str | None = Field(default=None, max_length=500)

    trace_id: str | None = Field(default=None, max_length=64)
    span_id: str | None = Field(default=None, max_length=64)
    error_code: str | None = Field(default=None, max_length=50)
    usage_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Provider usage metadata only; excludes raw prompts, model outputs, "
            "message bodies, user input, and raw provider error text."
        ),
    )

    @model_validator(mode="after")
    def _validate_provider_cost(self) -> Self:
        cost_values = (
            self.provider_cost_amount,
            self.provider_cost_currency,
            self.provider_cost_source,
        )
        has_any = any(value is not None for value in cost_values)
        has_all = all(value is not None for value in cost_values)
        if has_any and not has_all:
            raise ValueError(
                "provider cost amount, currency, and source must be set together"
            )
        if self.provider_cost_currency is not None:
            object.__setattr__(
                self, "provider_cost_currency", self.provider_cost_currency.upper()
            )
        if self.total_tokens == 0:
            total_tokens = (
                self.input_tokens
                + self.output_tokens
                + self.cache_read_tokens
                + self.cache_write_tokens
                + self.reasoning_tokens
            )
            object.__setattr__(self, "total_tokens", total_tokens)
        return self


class AiUsageResponse(BaseResponse):
    id: int
    call_id: str
    request_id: str | None = None
    org_id: str | None = None
    agent_name: str
    provider: str | None = None
    model: str
    status: str
    occurred_at: datetime
    duration_ms: int | None = None

    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    reasoning_tokens: int
    total_tokens: int
    requests: int

    provider_cost_amount: Decimal | None = None
    provider_cost_currency: str | None = None
    provider_cost_source: str | None = None

    prompt_name: str | None = None
    prompt_version: str | None = None
    prompt_source: str | None = None
    external_prompt_ref: str | None = None

    trace_id: str | None = None
    span_id: str | None = None
    error_code: str | None = None
    usage_metadata: dict[str, Any] = Field(
        ...,
        description=(
            "Provider usage metadata only; excludes raw prompts, model outputs, "
            "message bodies, user input, and raw provider error text."
        ),
    )
    created_at: datetime


class AiUsageByOrgResponse(BaseResponse):
    org_id: str | None = None
    call_count: int
    request_count: int
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    reasoning_tokens: int
    total_tokens: int


class AiUsageSummaryResponse(BaseResponse):
    call_count: int
    request_count: int
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    reasoning_tokens: int
    total_tokens: int
    by_org: list[AiUsageByOrgResponse]
