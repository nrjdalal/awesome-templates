from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal, Self

from pydantic import Field, model_validator

from src._core.domain.value_objects.value_object import ValueObject

PromptSource = Literal["inline", "langfuse", "self"]
ProviderCostSource = Literal["response", "estimated", "manual"]
UsageStatus = Literal["ok", "error", "timeout", "rate_limited"]


def _utcnow_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class AgentUsageRecord(ValueObject):
    """Append-only record of one logical AI agent call.

    This value object is the core contract between AI call sites and any
    usage recorder. It intentionally stores raw usage facts only; customer
    billing prices are calculated by a later pricing/invoice layer.
    """

    call_id: str = Field(..., min_length=1, max_length=64)
    request_id: str | None = Field(default=None, max_length=128)
    org_id: str | None = Field(default=None, max_length=64)
    agent_name: str = Field(..., min_length=1, max_length=100)
    provider: str | None = Field(default=None, max_length=40)
    model: str = Field(..., min_length=1, max_length=200)
    status: UsageStatus = "ok"
    occurred_at: datetime = Field(default_factory=_utcnow_naive)
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
            "Provider usage metadata only; must not contain raw prompts, model "
            "outputs, message bodies, user input, or raw provider error text."
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
            currency = self.provider_cost_currency.upper()
            object.__setattr__(self, "provider_cost_currency", currency)
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
