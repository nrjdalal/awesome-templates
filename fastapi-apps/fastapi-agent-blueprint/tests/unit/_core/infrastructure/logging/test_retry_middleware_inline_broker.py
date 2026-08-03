"""Retry behaviour that only matters once the stack runs in the server process.

#324 installed `PermanentAwareSmartRetryMiddleware` on the inline broker, which
runs tasks inside the server process. Two properties that were harmless in a
worker became reachable there, and a post-merge review found both.

**Cancellation spawned a retry.** Taskiq's receiver catches `BaseException`, so
`asyncio.CancelledError` reaches `on_error` like any other error. Being outside
`PERMANENT_ERROR_TYPES`, it scheduled a retry — on a loop that is shutting down.
Probed before the fix:

    CancelledError       retry scheduled: True
    RuntimeError         retry scheduled: True
    BaseCustomException  retry scheduled: False

**The announced backoff was never applied.** `SmartRetryMiddleware` computes a
delay, logs it ("Retrying 1/3 in 5.58 seconds") and writes it to
`labels["delay"]`. Cross-process brokers implement that label; `InMemoryBroker`
ignores it and calls `asyncio.create_task` immediately. Probed: three attempts
finished within 0.1s, at 0.033s and 0.018s intervals, against an announced 5.58s
and 11.37s. So "retry with backoff" meant "hammer three times at once" — the
opposite of what helps a throttled provider.
"""

from __future__ import annotations

import asyncio
import time

import pytest
import taskiq.middlewares.smart_retry_middleware as smart_retry
from pydantic import ValidationError
from taskiq import InMemoryBroker, TaskiqMessage, TaskiqResult

from src._core.exceptions.base_exception import BaseCustomException
from src._core.infrastructure.logging.taskiq_middleware import (
    PermanentAwareSmartRetryMiddleware,
)


@pytest.fixture
def message() -> TaskiqMessage:
    return TaskiqMessage(
        task_id="t1",
        task_name="probe.task",
        labels={"max_retries": 3, "_retries": 0},
        args=[],
        kwargs={},
    )


@pytest.fixture
def result() -> TaskiqResult:
    return TaskiqResult(is_err=True, return_value=None, execution_time=0.0, error=None)


@pytest.fixture
def middleware() -> PermanentAwareSmartRetryMiddleware:
    mw = PermanentAwareSmartRetryMiddleware()
    mw.set_broker(InMemoryBroker())
    return mw


@pytest.fixture
def captured_sends(monkeypatch) -> list:
    """Record `SmartRetryMiddleware.on_send` calls without re-kicking anything."""
    sends: list = []

    async def _record(self, kicker, msg, delay):  # noqa: ANN001
        sends.append(delay)

    monkeypatch.setattr(smart_retry.SmartRetryMiddleware, "on_send", _record)
    return sends


class TestCancellationDoesNotRetry:
    async def test_cancelled_error_schedules_no_retry(
        self, middleware, message, result, captured_sends
    ):
        await middleware.on_error(message, result, asyncio.CancelledError())
        assert captured_sends == [], (
            "a cancelled task scheduled a retry; during loop shutdown that leaves "
            "an orphaned pending task behind"
        )

    async def test_a_transient_error_still_retries(
        self, middleware, message, result, captured_sends
    ):
        """The half that must not regress — suppressing cancellation must not
        suppress the retries the middleware exists for."""
        await middleware.on_error(message, result, RuntimeError("connection reset"))
        assert captured_sends, "a transient error no longer retries"

    @pytest.mark.parametrize(
        "exc",
        [
            BaseCustomException(status_code=400, message="curated"),
            ValueError("bad input"),
            TypeError("bad type"),
        ],
        ids=["custom", "value", "type"],
    )
    async def test_permanent_errors_still_skip_retry(
        self, middleware, message, result, captured_sends, exc
    ):
        await middleware.on_error(message, result, exc)
        assert captured_sends == []

    def test_cancelled_error_is_not_in_the_permanent_set(self):
        """The fix is a separate branch on purpose. Adding `CancelledError` to
        `PERMANENT_ERROR_TYPES` would also change what the notifier treats as a
        terminal failure worth alerting on, which is a different decision.
        """
        assert (
            asyncio.CancelledError
            not in PermanentAwareSmartRetryMiddleware.PERMANENT_ERROR_TYPES
        )
        # Guard the set itself so a future addition is a deliberate act.
        assert set(PermanentAwareSmartRetryMiddleware.PERMANENT_ERROR_TYPES) == {
            BaseCustomException,
            ValueError,
            TypeError,
            ValidationError,
        }


class TestTheAnnouncedDelayIsHonouredOnTheInlineBroker:
    DELAY = 0.3

    async def test_inline_broker_waits(self, middleware, captured_sends):
        started = time.monotonic()
        await middleware.on_send(None, None, self.DELAY)
        elapsed = time.monotonic() - started
        assert elapsed >= self.DELAY * 0.8, (
            f"waited {elapsed:.3f}s for an announced {self.DELAY}s backoff; the "
            "inline broker ignores the delay label, so retries fire immediately"
        )
        assert captured_sends == [self.DELAY], "the re-kick was dropped, not delayed"

    async def test_a_cross_process_broker_is_not_slept_on(self, captured_sends):
        """Those brokers implement the delay label themselves. Sleeping here too
        would double every backoff in production."""
        from taskiq.brokers.shared_broker import AsyncSharedBroker

        mw = PermanentAwareSmartRetryMiddleware()
        mw.set_broker(AsyncSharedBroker())

        started = time.monotonic()
        await mw.on_send(None, None, self.DELAY)
        assert time.monotonic() - started < self.DELAY / 2
        assert captured_sends == [self.DELAY]

    async def test_no_delay_means_no_sleep(self, middleware, captured_sends):
        started = time.monotonic()
        await middleware.on_send(None, None, None)
        assert time.monotonic() - started < 0.05
        assert captured_sends == [None]
