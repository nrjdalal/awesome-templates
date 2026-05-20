from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import structlog

from src._core.domain.protocols.agent_usage_recorder_protocol import (
    AgentUsageRecorderProtocol,
)
from src._core.domain.value_objects.agent_usage_record import (
    AgentUsageRecord,
    ProviderCostSource,
    UsageStatus,
)
from src._core.domain.value_objects.prompt_snapshot import PromptSnapshot

_logger = structlog.stdlib.get_logger("src._core.application.usage_tracker")


RecorderCallable = Callable[[AgentUsageRecord], Awaitable[AgentUsageRecord]]


class AgentUsageCapture:
    def __init__(
        self,
        *,
        call_id: str,
        agent_name: str,
        model: str,
        recorder: AgentUsageRecorderProtocol | RecorderCallable,
        request_id: str | None = None,
        org_id: str | None = None,
        provider: str | None = None,
        prompt_snapshot: PromptSnapshot | None = None,
        trace_id: str | None = None,
        span_id: str | None = None,
        strict_record: bool = True,
    ) -> None:
        self.call_id = call_id
        self.agent_name = agent_name
        self.model = model
        self.recorder = recorder
        self.request_id = request_id or _default_request_id()
        self.org_id = org_id
        self.provider = provider
        self.prompt_snapshot = prompt_snapshot
        self.trace_id = trace_id
        self.span_id = span_id
        self.strict_record = strict_record
        self.result: Any | None = None
        self.provider_cost_amount: Decimal | None = None
        self.provider_cost_currency: str | None = None
        self.provider_cost_source: ProviderCostSource | None = None
        self._started_at = datetime.now(UTC).replace(tzinfo=None)
        self._started_perf = time.perf_counter()

    def set_result(self, result: Any) -> None:
        self.result = result

    def set_provider_cost(
        self,
        *,
        amount: Decimal,
        currency: str,
        source: ProviderCostSource = "manual",
    ) -> None:
        self.provider_cost_amount = amount
        self.provider_cost_currency = currency.upper()
        self.provider_cost_source = source

    async def record(
        self, *, status: UsageStatus, error_code: str | None = None
    ) -> None:
        usage_values = _extract_usage_values(self.result)
        duration_ms = round((time.perf_counter() - self._started_perf) * 1000)
        prompt = self.prompt_snapshot
        record = AgentUsageRecord(
            call_id=self.call_id,
            request_id=self.request_id,
            org_id=self.org_id,
            agent_name=self.agent_name,
            provider=self.provider,
            model=self.model,
            status=status,
            occurred_at=self._started_at,
            duration_ms=duration_ms,
            input_tokens=usage_values["input_tokens"],
            output_tokens=usage_values["output_tokens"],
            cache_read_tokens=usage_values["cache_read_tokens"],
            cache_write_tokens=usage_values["cache_write_tokens"],
            reasoning_tokens=usage_values["reasoning_tokens"],
            requests=usage_values["requests"],
            provider_cost_amount=self.provider_cost_amount,
            provider_cost_currency=self.provider_cost_currency,
            provider_cost_source=self.provider_cost_source,
            prompt_name=prompt.name if prompt else None,
            prompt_version=prompt.version if prompt else None,
            prompt_source=prompt.source if prompt else None,
            external_prompt_ref=prompt.external_ref if prompt else None,
            trace_id=self.trace_id,
            span_id=self.span_id,
            error_code=error_code,
            usage_metadata=usage_values["usage_metadata"],
        )
        await _record_usage(self.recorder, record)


@asynccontextmanager
async def track_agent_usage(
    *,
    call_id: str,
    agent_name: str,
    model: str,
    recorder: AgentUsageRecorderProtocol | RecorderCallable,
    request_id: str | None = None,
    org_id: str | None = None,
    provider: str | None = None,
    prompt_snapshot: PromptSnapshot | None = None,
    trace_id: str | None = None,
    span_id: str | None = None,
    strict_record: bool = True,
):
    """Track one agent call and record append-only raw usage facts.

    The caller must call ``capture.set_result(result)`` after a successful
    agent run so token usage can be extracted without importing provider SDKs.
    """

    capture = AgentUsageCapture(
        call_id=call_id,
        agent_name=agent_name,
        model=model,
        recorder=recorder,
        request_id=request_id,
        org_id=org_id,
        provider=provider,
        prompt_snapshot=prompt_snapshot,
        trace_id=trace_id,
        span_id=span_id,
        strict_record=strict_record,
    )
    try:
        yield capture
    except Exception as exc:
        try:
            await capture.record(
                status=_status_from_exception(exc), error_code=type(exc).__name__
            )
        except Exception:
            _logger.exception(
                "agent_usage_record_failed",
                call_id=call_id,
                agent_name=agent_name,
                status="agent_error",
            )
        raise
    else:
        try:
            await capture.record(status="ok")
        except Exception:
            if strict_record:
                raise
            _logger.exception(
                "agent_usage_record_failed",
                call_id=call_id,
                agent_name=agent_name,
                status="agent_success",
            )


async def _record_usage(
    recorder: AgentUsageRecorderProtocol | RecorderCallable,
    record: AgentUsageRecord,
) -> AgentUsageRecord:
    if callable(recorder):
        return await recorder(record)
    return await recorder.record_usage(record)


def _default_request_id() -> str | None:
    context = structlog.contextvars.get_contextvars()
    for key in ("request_id", "correlation_id", "taskiq_task_id"):
        value = context.get(key)
        if value:
            return str(value)
    return None


def _status_from_exception(exc: Exception) -> UsageStatus:
    type_name = type(exc).__name__.lower()
    message = str(exc).lower()
    if "timeout" in type_name or "timeout" in message:
        return "timeout"
    if "ratelimit" in type_name or ("rate" in message and "limit" in message):
        return "rate_limited"
    return "error"


def _extract_usage_values(result: Any | None) -> dict[str, Any]:
    usage = _get_usage(result)
    if usage is None:
        return {
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_read_tokens": 0,
            "cache_write_tokens": 0,
            "reasoning_tokens": 0,
            "requests": 0,
            "usage_metadata": {},
        }

    usage_metadata = _usage_to_metadata(usage)
    details = usage_metadata.get("details")
    if not isinstance(details, dict):
        details = {}

    input_tokens = _int_attr(usage, "input_tokens", "request_tokens", "prompt_tokens")
    output_tokens = _int_attr(
        usage, "output_tokens", "response_tokens", "completion_tokens"
    )
    cache_read_tokens = _int_attr(usage, "cache_read_tokens") or _int_from_dict(
        details, "cache_read_tokens", "cached_tokens"
    )
    cache_write_tokens = _int_attr(usage, "cache_write_tokens") or _int_from_dict(
        details, "cache_write_tokens", "cache_creation_input_tokens"
    )
    reasoning_tokens = _int_attr(usage, "reasoning_tokens") or _int_from_dict(
        details, "reasoning_tokens"
    )

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_read_tokens": cache_read_tokens,
        "cache_write_tokens": cache_write_tokens,
        "reasoning_tokens": reasoning_tokens,
        "requests": _int_attr(usage, "requests") or 1,
        "usage_metadata": usage_metadata,
    }


def _get_usage(result: Any | None) -> Any | None:
    if result is None:
        return None
    usage = getattr(result, "usage", None)
    if callable(usage):
        return usage()
    return usage


def _usage_to_metadata(usage: Any) -> dict[str, Any]:
    if hasattr(usage, "model_dump"):
        data = usage.model_dump()
        return data if isinstance(data, dict) else {}
    if hasattr(usage, "__dict__"):
        return dict(usage.__dict__)
    return {}


def _int_attr(obj: Any, *names: str) -> int:
    for name in names:
        value = getattr(obj, name, None)
        if isinstance(value, int):
            return max(value, 0)
    return 0


def _int_from_dict(data: dict[str, Any], *names: str) -> int:
    for name in names:
        value = data.get(name)
        if isinstance(value, int):
            return max(value, 0)
    return 0
