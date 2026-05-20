from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import pytest
import structlog

from src._core.application.usage_tracker import track_agent_usage
from src._core.domain.value_objects.agent_usage_record import AgentUsageRecord
from src._core.domain.value_objects.prompt_snapshot import PromptSnapshot


@dataclass
class FakeUsage:
    input_tokens: int = 10
    output_tokens: int = 5
    cache_read_tokens: int = 2
    cache_write_tokens: int = 1
    reasoning_tokens: int = 3
    requests: int = 1

    def model_dump(self):
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "cache_write_tokens": self.cache_write_tokens,
            "reasoning_tokens": self.reasoning_tokens,
            "requests": self.requests,
        }


class FakeResult:
    def usage(self):
        return FakeUsage()


@dataclass
class FakeUsageWithoutRequests:
    input_tokens: int = 4
    output_tokens: int = 6

    def model_dump(self):
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
        }


class FakeResultWithoutRequests:
    def usage(self):
        return FakeUsageWithoutRequests()


class RecordingRecorder:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.records: list[AgentUsageRecord] = []

    async def record_usage(self, record: AgentUsageRecord) -> AgentUsageRecord:
        if self.fail:
            raise RuntimeError("record failed")
        self.records.append(record)
        return record


@pytest.mark.asyncio
async def test_track_agent_usage_records_success():
    recorder = RecordingRecorder()

    async with track_agent_usage(
        call_id="call-1",
        agent_name="classifier",
        model="gpt-test",
        recorder=recorder,
    ) as capture:
        capture.set_result(FakeResult())

    assert len(recorder.records) == 1
    record = recorder.records[0]
    assert record.status == "ok"
    assert record.input_tokens == 10
    assert record.output_tokens == 5
    assert record.total_tokens == 21


@pytest.mark.asyncio
async def test_track_agent_usage_records_zero_tokens_without_usage():
    recorder = RecordingRecorder()

    async with track_agent_usage(
        call_id="call-1",
        agent_name="classifier",
        model="gpt-test",
        recorder=recorder,
    ):
        pass

    assert recorder.records[0].requests == 0
    assert recorder.records[0].total_tokens == 0


@pytest.mark.asyncio
async def test_track_agent_usage_defaults_requests_when_usage_object_has_tokens():
    recorder = RecordingRecorder()

    async with track_agent_usage(
        call_id="call-1",
        agent_name="classifier",
        model="gpt-test",
        recorder=recorder,
    ) as capture:
        capture.set_result(FakeResultWithoutRequests())

    assert recorder.records[0].requests == 1
    assert recorder.records[0].total_tokens == 10


@pytest.mark.asyncio
async def test_track_agent_usage_records_prompt_snapshot_and_provider_cost():
    recorder = RecordingRecorder()
    prompt = PromptSnapshot(
        name="classify-ticket",
        content="classify this",
        version="v2",
        source="langfuse",
        external_ref="lf-prompt-1",
    )

    async with track_agent_usage(
        call_id="call-1",
        agent_name="classifier",
        model="gpt-test",
        recorder=recorder,
        prompt_snapshot=prompt,
    ) as capture:
        capture.set_provider_cost(
            amount=Decimal("0.0012"), currency="usd", source="response"
        )
        capture.set_result(FakeResult())

    record = recorder.records[0]
    assert record.prompt_name == "classify-ticket"
    assert record.prompt_version == "v2"
    assert record.prompt_source == "langfuse"
    assert record.external_prompt_ref == "lf-prompt-1"
    assert record.provider_cost_amount == Decimal("0.0012")
    assert record.provider_cost_currency == "USD"
    assert record.provider_cost_source == "response"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("exc", "expected_status"),
    [
        (TimeoutError("provider timeout"), "timeout"),
        (RuntimeError("rate limit exceeded"), "rate_limited"),
        (ValueError("agent failed"), "error"),
    ],
)
async def test_track_agent_usage_maps_agent_error_status(exc, expected_status):
    recorder = RecordingRecorder()

    with pytest.raises(type(exc)):
        async with track_agent_usage(
            call_id="call-1",
            agent_name="classifier",
            model="gpt-test",
            recorder=recorder,
        ):
            raise exc

    assert recorder.records[0].status == expected_status
    assert recorder.records[0].error_code == type(exc).__name__


@pytest.mark.asyncio
async def test_track_agent_usage_strict_record_failure_propagates():
    recorder = RecordingRecorder(fail=True)

    with pytest.raises(RuntimeError, match="record failed"):
        async with track_agent_usage(
            call_id="call-1",
            agent_name="classifier",
            model="gpt-test",
            recorder=recorder,
        ):
            pass


@pytest.mark.asyncio
async def test_track_agent_usage_non_strict_record_failure_does_not_propagate():
    recorder = RecordingRecorder(fail=True)

    async with track_agent_usage(
        call_id="call-1",
        agent_name="classifier",
        model="gpt-test",
        recorder=recorder,
        strict_record=False,
    ):
        pass


@pytest.mark.asyncio
async def test_track_agent_usage_preserves_agent_error_when_record_fails():
    recorder = RecordingRecorder(fail=True)

    with pytest.raises(ValueError, match="agent failed"):
        async with track_agent_usage(
            call_id="call-1",
            agent_name="classifier",
            model="gpt-test",
            recorder=recorder,
        ):
            raise ValueError("agent failed")


@pytest.mark.asyncio
async def test_track_agent_usage_uses_structlog_context_request_id():
    recorder = RecordingRecorder()
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(correlation_id="corr-1")
    try:
        async with track_agent_usage(
            call_id="call-1",
            agent_name="classifier",
            model="gpt-test",
            recorder=recorder,
        ):
            pass
    finally:
        structlog.contextvars.clear_contextvars()

    assert recorder.records[0].request_id == "corr-1"
