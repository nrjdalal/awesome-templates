from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from src._core.domain.value_objects.agent_usage_record import (
    AgentUsageRecord,
    ProviderCostSource,
)
from src.ai_usage.domain.dtos.ai_usage_dto import AiUsageDTO
from src.ai_usage.interface.server.schemas.ai_usage_schema import CreateAiUsageRequest


def make_agent_usage_record(
    call_id: str = "call-1",
    request_id: str | None = "req-1",
    org_id: str | None = "org-1",
    agent_name: str = "classification",
    provider: str | None = "openai",
    model: str = "gpt-test",
    input_tokens: int = 10,
    output_tokens: int = 5,
    cache_read_tokens: int = 2,
    cache_write_tokens: int = 1,
    reasoning_tokens: int = 3,
    provider_cost_amount: Decimal | None = None,
    provider_cost_currency: str | None = None,
    provider_cost_source: ProviderCostSource | None = None,
    usage_metadata: dict[str, Any] | None = None,
) -> AgentUsageRecord:
    return AgentUsageRecord(
        call_id=call_id,
        request_id=request_id,
        org_id=org_id,
        agent_name=agent_name,
        provider=provider,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_tokens=cache_read_tokens,
        cache_write_tokens=cache_write_tokens,
        reasoning_tokens=reasoning_tokens,
        provider_cost_amount=provider_cost_amount,
        provider_cost_currency=provider_cost_currency,
        provider_cost_source=provider_cost_source,
        usage_metadata=usage_metadata or {},
    )


def make_create_ai_usage_request(
    call_id: str = "call-1",
    org_id: str | None = "org-1",
    agent_name: str = "classification",
    model: str = "gpt-test",
    occurred_at: datetime | None = None,
    provider_cost_amount: Decimal | None = None,
    provider_cost_currency: str | None = None,
    provider_cost_source: ProviderCostSource | None = None,
) -> CreateAiUsageRequest:
    return CreateAiUsageRequest(
        call_id=call_id,
        org_id=org_id,
        agent_name=agent_name,
        provider="openai",
        model=model,
        occurred_at=occurred_at or _utcnow_naive(),
        input_tokens=10,
        output_tokens=5,
        cache_read_tokens=2,
        cache_write_tokens=1,
        reasoning_tokens=3,
        requests=1,
        provider_cost_amount=provider_cost_amount,
        provider_cost_currency=provider_cost_currency,
        provider_cost_source=provider_cost_source,
    )


def make_ai_usage_dto(
    id: int = 1,
    call_id: str = "call-1",
    org_id: str | None = "org-1",
    created_at: datetime | None = None,
) -> AiUsageDTO:
    now = _utcnow_naive()
    return AiUsageDTO(
        id=id,
        call_id=call_id,
        request_id="req-1",
        org_id=org_id,
        agent_name="classification",
        provider="openai",
        model="gpt-test",
        status="ok",
        occurred_at=now,
        duration_ms=100,
        input_tokens=10,
        output_tokens=5,
        cache_read_tokens=2,
        cache_write_tokens=1,
        reasoning_tokens=3,
        total_tokens=21,
        requests=1,
        usage_metadata={},
        created_at=created_at or now,
    )


def _utcnow_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)
