"""Tests for the Taskiq structlog-context middleware (#9)."""

from __future__ import annotations

from typing import Any

import pytest
import structlog
from pydantic import BaseModel, ValidationError
from structlog.testing import capture_logs
from taskiq import InMemoryBroker, TaskiqMessage, TaskiqResult
from taskiq.exceptions import NoResultError

from src._core.exceptions.base_exception import BaseCustomException
from src._core.infrastructure.logging.taskiq_middleware import (
    PermanentAwareSmartRetryMiddleware,
    StructlogContextMiddleware,
    TaskErrorLoggingMiddleware,
)


@pytest.fixture(autouse=True)
def _cleanup_contextvars():
    yield
    structlog.contextvars.clear_contextvars()


def _make_message(
    *,
    task_id: str = "t_1",
    task_name: str = "sample_task",
    labels: dict[str, Any] | None = None,
) -> TaskiqMessage:
    return TaskiqMessage(
        task_id=task_id,
        task_name=task_name,
        labels=labels or {},
        labels_types=None,
        args=[],
        kwargs={},
    )


def _make_result(error: BaseException | None = None) -> TaskiqResult[Any]:
    return TaskiqResult(
        is_err=error is not None,
        return_value=None,
        execution_time=0.0,
        labels={},
        error=error,
        log=None,
    )


def _make_validation_error() -> ValidationError:
    class ProbeModel(BaseModel):
        count: int

    with pytest.raises(ValidationError) as exc_info:
        ProbeModel.model_validate({"count": "not-an-int"})
    return exc_info.value


class RecordingRetryMiddleware(PermanentAwareSmartRetryMiddleware):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.sent: list[tuple[TaskiqMessage, float]] = []

    async def on_send(
        self,
        kicker: Any,
        message: TaskiqMessage,
        delay: float,
    ) -> None:
        self.sent.append((message, delay))


class TestStructlogContextMiddleware:
    @pytest.mark.asyncio
    async def test_pre_execute_binds_task_metadata(self):
        mw = StructlogContextMiddleware()
        await mw.pre_execute(_make_message(task_id="abc", task_name="do_thing"))

        ctx = structlog.contextvars.get_contextvars()
        assert ctx["taskiq_task_id"] == "abc"
        assert ctx["taskiq_task_name"] == "do_thing"

    @pytest.mark.asyncio
    async def test_pre_execute_binds_correlation_id_from_labels(self):
        mw = StructlogContextMiddleware()
        await mw.pre_execute(_make_message(labels={"correlation_id": "req_parent_123"}))

        ctx = structlog.contextvars.get_contextvars()
        assert ctx["correlation_id"] == "req_parent_123"

    @pytest.mark.asyncio
    async def test_pre_execute_omits_correlation_id_when_absent(self):
        mw = StructlogContextMiddleware()
        await mw.pre_execute(_make_message(labels={}))

        ctx = structlog.contextvars.get_contextvars()
        assert "correlation_id" not in ctx

    @pytest.mark.asyncio
    async def test_pre_execute_clears_stale_context_from_previous_task(self):
        """Prev-task leakage guard — critical when a worker loop reuses tasks."""
        structlog.contextvars.bind_contextvars(leftover="stale_value")

        mw = StructlogContextMiddleware()
        await mw.pre_execute(_make_message(task_id="fresh"))

        ctx = structlog.contextvars.get_contextvars()
        assert "leftover" not in ctx
        assert ctx["taskiq_task_id"] == "fresh"

    @pytest.mark.asyncio
    async def test_post_execute_clears_context(self):
        mw = StructlogContextMiddleware()
        await mw.pre_execute(_make_message())

        await mw.post_execute(
            _make_message(),
            TaskiqResult(
                is_err=False,
                return_value=None,
                execution_time=0.0,
                labels={},
                error=None,
                log=None,
            ),
        )

        assert structlog.contextvars.get_contextvars() == {}


class TestTaskErrorLoggingMiddleware:
    @pytest.mark.asyncio
    async def test_on_error_emits_structured_failure_event(self):
        mw = TaskErrorLoggingMiddleware()
        message = _make_message(task_id="task-123", task_name="docs.ingest")
        exception = RuntimeError("boom")
        result = _make_result(exception)

        structlog.contextvars.bind_contextvars(correlation_id="corr-123")

        with capture_logs(processors=[structlog.contextvars.merge_contextvars]) as logs:
            await mw.on_error(message, result, exception)

        assert len(logs) == 1
        event = logs[0]
        assert event["event"] == "taskiq_task_failed"
        assert event["taskiq_task_id"] == "task-123"
        assert event["taskiq_task_name"] == "docs.ingest"
        assert event["correlation_id"] == "corr-123"
        assert event["exc_info"] is exception
        assert event["exception_type"] == "RuntimeError"
        assert "args" not in event
        assert "kwargs" not in event
        assert "labels" not in event
        assert "payload" not in event


class TestPermanentAwareSmartRetryMiddleware:
    @pytest.mark.asyncio
    async def test_transient_exception_schedules_retry_and_suppresses_result(self):
        mw = RecordingRetryMiddleware()
        mw.set_broker(InMemoryBroker())
        exception = RuntimeError("temporary outage")
        result = _make_result(exception)

        await mw.on_error(_make_message(), result, exception)

        assert len(mw.sent) == 1
        assert isinstance(result.error, NoResultError)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "exception",
        [
            BaseCustomException(message="domain error"),
            ValueError("bad value"),
            TypeError("bad type"),
            _make_validation_error(),
        ],
    )
    async def test_permanent_exception_does_not_schedule_retry(
        self, exception: BaseException
    ):
        mw = RecordingRetryMiddleware()
        mw.set_broker(InMemoryBroker())
        result = _make_result(exception)

        await mw.on_error(_make_message(), result, exception)

        assert mw.sent == []
        assert result.error is exception

    @pytest.mark.asyncio
    async def test_retry_on_error_false_disables_retry(self):
        mw = RecordingRetryMiddleware()
        mw.set_broker(InMemoryBroker())
        exception = RuntimeError("do not retry")
        result = _make_result(exception)

        await mw.on_error(
            _make_message(labels={"retry_on_error": False}),
            result,
            exception,
        )

        assert mw.sent == []
        assert result.error is exception

    @pytest.mark.asyncio
    async def test_max_retries_label_overrides_default_retry_count(self):
        mw = RecordingRetryMiddleware(default_retry_count=1)
        mw.set_broker(InMemoryBroker())
        exception = RuntimeError("temporary outage")
        result = _make_result(exception)

        await mw.on_error(
            _make_message(labels={"max_retries": 3}),
            result,
            exception,
        )

        assert len(mw.sent) == 1
        assert isinstance(result.error, NoResultError)

    @pytest.mark.asyncio
    async def test_retries_threshold_stops_scheduling(self):
        mw = RecordingRetryMiddleware()
        mw.set_broker(InMemoryBroker())
        exception = RuntimeError("still failing")
        result = _make_result(exception)

        # _retries is SmartRetryMiddleware's retry-counter label.
        await mw.on_error(
            _make_message(labels={"_retries": 2, "max_retries": 3}),
            result,
            exception,
        )

        assert mw.sent == []
        assert result.error is exception
