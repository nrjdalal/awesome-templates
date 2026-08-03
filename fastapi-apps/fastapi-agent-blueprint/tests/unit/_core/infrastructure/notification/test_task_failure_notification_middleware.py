"""Unit tests for TaskFailureNotificationMiddleware (#310).

Three behaviours are pinned here, because each one is silently wrong if the
implementation drifts:

1. **Synthetic severity** — the worker has no HTTP status, so
   ``BaseCustomException`` contributes its own ``status_code`` and everything
   else is treated as 500. Without this, ``NOTIFICATION_SEVERITY_THRESHOLD``
   would not apply to task failures at all.
2. **Task-scoped cooldown key** — ``ErrorNotifier`` dedupes on ``error_code``
   alone, so a bare code would let one noisy task suppress every other task's
   alert for the whole cooldown window.
3. **Final-attempt gating** — a retried failure must alert once, not once per
   attempt. This depends on reading ``_retries`` *before*
   ``PermanentAwareSmartRetryMiddleware`` increments it, which is an ordering
   contract; see ``TestMiddlewareOrderingContract``.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from taskiq import InMemoryBroker, TaskiqMessage, TaskiqMiddleware, TaskiqResult
from taskiq.exceptions import NoResultError
from taskiq.utils import maybe_awaitable

from src._core.exceptions.base_exception import BaseCustomException
from src._core.infrastructure.logging.taskiq_middleware import (
    PermanentAwareSmartRetryMiddleware,
    StructlogContextMiddleware,
    TaskErrorLoggingMiddleware,
)
from src._core.infrastructure.notification.taskiq_middleware import (
    TaskFailureNotificationMiddleware,
)


class FakeErrorNotifier:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def maybe_dispatch(
        self, *, status_code: int, error_code: str, message: str
    ) -> None:
        self.calls.append(
            {"status_code": status_code, "error_code": error_code, "message": message}
        )


def _make_message(
    *, task_name: str = "src.user.tasks.sync", labels: dict | None = None
) -> TaskiqMessage:
    return TaskiqMessage(
        task_id="task-1",
        task_name=task_name,
        labels=labels if labels is not None else {},
        args=[],
        kwargs={},
    )


def _make_result() -> TaskiqResult:
    return TaskiqResult(is_err=True, return_value=None, execution_time=0.0)


async def _drive_on_error(
    broker: InMemoryBroker, message: TaskiqMessage, exception: BaseException
) -> None:
    """Replay taskiq's own ``on_error`` fan-out for one failed attempt.

    Copied deliberately from ``taskiq/receiver/receiver.py`` — the reversed
    iteration and the "skip middlewares that don't override on_error" check are
    the two behaviours the ordering contract depends on, so the test has to use
    them rather than approximate them.
    """
    for middleware in reversed(broker.middlewares):
        if middleware.__class__.on_error != TaskiqMiddleware.on_error:
            await maybe_awaitable(
                middleware.on_error(message, _make_result(), exception)
            )


def _make_middleware(
    notifier: FakeErrorNotifier,
    *,
    retry_middleware: PermanentAwareSmartRetryMiddleware | None = None,
) -> TaskFailureNotificationMiddleware:
    return TaskFailureNotificationMiddleware(
        error_notifier_provider=lambda: notifier,
        retry_middleware=retry_middleware or PermanentAwareSmartRetryMiddleware(),
    )


class TestSyntheticSeverity:
    """The worker has no HTTP status — one is synthesised for the threshold."""

    async def test_non_custom_exception_is_treated_as_500(self):
        notifier = FakeErrorNotifier()
        middleware = _make_middleware(notifier)

        # ValueError is in PERMANENT_ERROR_TYPES → terminal on first failure.
        await middleware.on_error(
            _make_message(), _make_result(), ValueError("bad config")
        )

        assert len(notifier.calls) == 1
        assert notifier.calls[0]["status_code"] == 500

    async def test_custom_exception_contributes_its_own_status_code(self):
        notifier = FakeErrorNotifier()
        middleware = _make_middleware(notifier)
        exc = BaseCustomException(
            status_code=503, message="db down", error_code="DB_UNAVAILABLE"
        )

        await middleware.on_error(_make_message(), _make_result(), exc)

        assert notifier.calls[0]["status_code"] == 503

    async def test_message_carries_task_name_and_exception(self):
        notifier = FakeErrorNotifier()
        middleware = _make_middleware(notifier)

        await middleware.on_error(
            _make_message(task_name="src.docs.tasks.reindex"),
            _make_result(),
            ValueError("boom"),
        )

        message = notifier.calls[0]["message"]
        assert "src.docs.tasks.reindex" in message
        assert "ValueError" in message
        assert "boom" in message


class TestTaskScopedCooldownKey:
    """ErrorNotifier dedupes on error_code alone — the key must be task-scoped."""

    async def test_key_combines_task_name_and_error_code(self):
        notifier = FakeErrorNotifier()
        middleware = _make_middleware(notifier)
        exc = BaseCustomException(
            status_code=500, message="nope", error_code="DB_INTERNAL_ERROR"
        )

        await middleware.on_error(
            _make_message(task_name="src.user.tasks.sync"), _make_result(), exc
        )

        assert (
            notifier.calls[0]["error_code"] == "src.user.tasks.sync:DB_INTERNAL_ERROR"
        )

    async def test_key_falls_back_to_exception_class_name(self):
        notifier = FakeErrorNotifier()
        middleware = _make_middleware(notifier)

        await middleware.on_error(
            _make_message(task_name="src.user.tasks.sync"),
            _make_result(),
            ValueError("x"),
        )

        assert notifier.calls[0]["error_code"] == "src.user.tasks.sync:ValueError"

    async def test_two_tasks_failing_the_same_way_get_distinct_keys(self):
        """Without this, one noisy task silences every other task's alert."""
        notifier = FakeErrorNotifier()
        middleware = _make_middleware(notifier)

        await middleware.on_error(
            _make_message(task_name="task.a"), _make_result(), ValueError("x")
        )
        await middleware.on_error(
            _make_message(task_name="task.b"), _make_result(), ValueError("x")
        )

        keys = [call["error_code"] for call in notifier.calls]
        assert keys == ["task.a:ValueError", "task.b:ValueError"]


class TestFinalAttemptGating:
    async def test_permanent_error_dispatches_immediately(self):
        notifier = FakeErrorNotifier()
        middleware = _make_middleware(notifier)

        # No _retries label at all → first attempt, but permanent → terminal.
        await middleware.on_error(
            _make_message(), _make_result(), TypeError("wrong type")
        )

        assert len(notifier.calls) == 1

    @pytest.mark.parametrize("permanent", [ValueError, TypeError])
    async def test_every_permanent_type_dispatches_immediately(self, permanent):
        notifier = FakeErrorNotifier()
        middleware = _make_middleware(notifier)

        await middleware.on_error(_make_message(), _make_result(), permanent("x"))

        assert len(notifier.calls) == 1

    async def test_pydantic_validation_error_dispatches_immediately(self):
        """ValidationError is permanent but cannot be constructed with a message."""
        notifier = FakeErrorNotifier()
        middleware = _make_middleware(notifier)
        exc = ValidationError.from_exception_data("Model", [])

        await middleware.on_error(_make_message(), _make_result(), exc)

        assert len(notifier.calls) == 1

    async def test_transient_error_on_a_non_final_attempt_is_not_dispatched(self):
        notifier = FakeErrorNotifier()
        middleware = _make_middleware(notifier)

        # attempt 1 of 3 — the retry middleware will retry this.
        await middleware.on_error(
            _make_message(labels={"_retries": 0, "max_retries": 3}),
            _make_result(),
            RuntimeError("connection reset"),
        )

        assert notifier.calls == []

    async def test_transient_error_on_the_final_attempt_is_dispatched(self):
        notifier = FakeErrorNotifier()
        middleware = _make_middleware(notifier)

        # _retries=2 → this is attempt 3 of 3, the last one.
        await middleware.on_error(
            _make_message(labels={"_retries": 2, "max_retries": 3}),
            _make_result(),
            RuntimeError("connection reset"),
        )

        assert len(notifier.calls) == 1
        assert notifier.calls[0]["status_code"] == 500

    async def test_default_retry_count_comes_from_the_retry_middleware(self):
        """No max_retries label → the retry middleware's default (3) applies."""
        notifier = FakeErrorNotifier()
        retry = PermanentAwareSmartRetryMiddleware(default_retry_count=2)
        middleware = _make_middleware(notifier, retry_middleware=retry)

        await middleware.on_error(
            _make_message(labels={"_retries": 0}),
            _make_result(),
            RuntimeError("transient"),
        )
        assert notifier.calls == []

        await middleware.on_error(
            _make_message(labels={"_retries": 1}),
            _make_result(),
            RuntimeError("transient"),
        )
        assert len(notifier.calls) == 1

    async def test_retry_disabled_task_dispatches_on_first_failure(self):
        notifier = FakeErrorNotifier()
        middleware = _make_middleware(notifier)

        await middleware.on_error(
            _make_message(labels={"retry_on_error": False}),
            _make_result(),
            RuntimeError("transient but never retried"),
        )

        assert len(notifier.calls) == 1

    async def test_no_result_error_is_never_dispatched(self):
        """NoResultError signals 'do not store a result', not a failure."""
        notifier = FakeErrorNotifier()
        middleware = _make_middleware(notifier)

        await middleware.on_error(_make_message(), _make_result(), NoResultError())

        assert notifier.calls == []


class TestDispatchNeverBreaksTheTaskPipeline:
    async def test_notifier_resolution_failure_does_not_raise(self):
        def exploding_provider():
            raise RuntimeError("container not wired")

        middleware = TaskFailureNotificationMiddleware(
            error_notifier_provider=exploding_provider,
            retry_middleware=PermanentAwareSmartRetryMiddleware(),
        )

        # Must not raise — a notification failure cannot become a second
        # task failure.
        await middleware.on_error(_make_message(), _make_result(), ValueError("x"))

    async def test_dispatch_failure_does_not_raise(self):
        class ExplodingNotifier:
            def maybe_dispatch(self, **kwargs):
                raise RuntimeError("notifier blew up")

        middleware = TaskFailureNotificationMiddleware(
            error_notifier_provider=lambda: ExplodingNotifier(),
            retry_middleware=PermanentAwareSmartRetryMiddleware(),
        )

        await middleware.on_error(_make_message(), _make_result(), ValueError("x"))


class TestMiddlewareOrderingContract:
    """Taskiq runs ``on_error`` over ``reversed(broker.middlewares)``, and
    ``SmartRetryMiddleware`` mutates ``message.labels`` in place through an
    ``AsyncKicker`` that holds the dict by reference. So the notifier must be
    registered LAST to have its ``on_error`` run FIRST — before ``_retries`` is
    incremented. Reorder it and the final-attempt check reads an already-bumped
    counter, which silently shifts every alert one attempt earlier.
    """

    # The positional assertion (notifier registered last) lives in
    # tests/unit/_apps/worker/test_bootstrap.py, which already owns the
    # "what does install_task_middleware register, in what order" contract for the
    # whole chain. Kept there rather than duplicated so there is one canonical
    # order assertion. What follows is notifier-specific.

    def test_install_task_middleware_shares_one_retry_middleware_instance(self):
        """The notifier reads retry defaults off the registered instance, so a
        second instance would let the two disagree about max_retries."""
        from src._apps.worker.bootstrap import install_task_middleware
        from src._apps.worker.broker import container

        broker = InMemoryBroker()
        install_task_middleware(
            broker, error_notifier_provider=container.error_notifier
        )

        registered_retry = next(
            m
            for m in broker.middlewares
            if isinstance(m, PermanentAwareSmartRetryMiddleware)
        )
        notifier_middleware = next(
            m
            for m in broker.middlewares
            if isinstance(m, TaskFailureNotificationMiddleware)
        )

        assert notifier_middleware._retry_middleware is registered_retry

    async def test_registered_order_alerts_once_on_the_final_attempt(self):
        """End-to-end through the REAL ``install_task_middleware`` wiring.

        Drives three attempts the way taskiq's receiver does and asserts
        exactly one alert lands, on the last. This is the test that actually
        catches a reorder: build the list from production code, then only swap
        the notifier provider for a fake. With the notifier ahead of the retry
        middleware it reads an already-incremented ``_retries`` and fires on
        attempt 2 instead of 3.
        """
        from src._apps.worker.bootstrap import install_task_middleware
        from src._apps.worker.broker import container

        notifier = FakeErrorNotifier()
        broker = InMemoryBroker()
        install_task_middleware(
            broker, error_notifier_provider=container.error_notifier
        )

        retry = next(
            m
            for m in broker.middlewares
            if isinstance(m, PermanentAwareSmartRetryMiddleware)
        )
        notifier_middleware = next(
            m
            for m in broker.middlewares
            if isinstance(m, TaskFailureNotificationMiddleware)
        )
        # Only the outbound edges are faked — the ordering and the gating logic
        # under test are the production ones.
        notifier_middleware._error_notifier_provider = lambda: notifier

        # Stop the retry middleware from actually re-queueing; the label
        # mutation we care about happens before on_send is reached.
        async def _no_send(kicker, message, delay):
            return None

        retry.on_send = _no_send  # type: ignore[method-assign]

        message = _make_message(labels={"max_retries": 3})
        exception = RuntimeError("connection reset")

        alerts_per_attempt = []
        for _ in range(3):
            before = len(notifier.calls)
            await _drive_on_error(broker, message, exception)
            alerts_per_attempt.append(len(notifier.calls) - before)

        assert alerts_per_attempt == [0, 0, 1], (
            f"expected one alert on the final attempt only, got {alerts_per_attempt}"
        )
