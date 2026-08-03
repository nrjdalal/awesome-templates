"""Taskiq middleware for worker context, failure logging, and retry (#9/#120).

``StructlogContextMiddleware`` binds the task identifier into the current
async context so every log emitted from within the task carries
``taskiq_task_id`` / ``taskiq_task_name``. If the dispatcher attached a
``correlation_id`` label (e.g. the HTTP request that kicked the task), it is
re-bound here too. That's how request-to-task correlation is preserved across
the process boundary.

``TaskErrorLoggingMiddleware`` emits one structured ``taskiq_task_failed``
record for every failed execution attempt. ``PermanentAwareSmartRetryMiddleware``
uses Taskiq's smart retry path for transient errors and lets permanent errors
fail immediately.

On ``post_execute`` the keys ``StructlogContextMiddleware`` owns are cleared so
the next task picked up by the same worker loop starts with a clean context.
Middleware registration:

```python
# src/_apps/worker/app.py
broker.add_middlewares(
    StructlogContextMiddleware(),
    PermanentAwareSmartRetryMiddleware(),
    TaskErrorLoggingMiddleware(),
)
```

Dispatcher side, pass the correlation ID through labels:

```python
await my_task.kicker().with_labels(
    correlation_id=correlation_id.get() or "",
).kiq(arg)
```

Background: https://github.com/orgs/taskiq-python/discussions/273
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from typing import Any

import structlog
from pydantic import ValidationError
from taskiq import InMemoryBroker, TaskiqMessage, TaskiqMiddleware, TaskiqResult
from taskiq.middlewares.smart_retry_middleware import SmartRetryMiddleware

from src._core.exceptions.base_exception import BaseCustomException


class StructlogContextMiddleware(TaskiqMiddleware):
    """Bind/unbind task-scoped context for structured logging."""

    async def pre_execute(self, message: TaskiqMessage) -> TaskiqMessage:
        # Wipe anything that leaked from the previous task on this loop.
        structlog.contextvars.clear_contextvars()

        bindings: dict[str, Any] = {
            "taskiq_task_id": message.task_id,
            "taskiq_task_name": message.task_name,
        }
        correlation_id = message.labels.get("correlation_id")
        if correlation_id:
            bindings["correlation_id"] = correlation_id
        structlog.contextvars.bind_contextvars(**bindings)
        return message

    async def post_execute(
        self, message: TaskiqMessage, result: TaskiqResult[Any]
    ) -> None:
        structlog.contextvars.clear_contextvars()


class TaskErrorLoggingMiddleware(TaskiqMiddleware):
    """Emit one structured failure event for each failed task execution."""

    def __init__(self) -> None:
        super().__init__()
        self._logger = structlog.stdlib.get_logger("src._core.infrastructure.logging")

    async def on_error(
        self,
        message: TaskiqMessage,
        result: TaskiqResult[Any],
        exception: BaseException,
    ) -> None:
        self._logger.error(
            "taskiq_task_failed",
            taskiq_task_id=message.task_id,
            taskiq_task_name=message.task_name,
            exception_type=type(exception).__name__,
            exc_info=exception,
        )


class PermanentAwareSmartRetryMiddleware(SmartRetryMiddleware):
    """Retry transient task errors while letting permanent errors fail."""

    # ValueError and TypeError are treated as programming/configuration errors
    # that retry cannot repair. Transient task failures should raise exceptions
    # outside this permanent set.
    PERMANENT_ERROR_TYPES: tuple[type[BaseException], ...] = (
        BaseCustomException,
        ValueError,
        TypeError,
        ValidationError,
    )

    def __init__(
        self,
        *,
        default_retry_count: int = 3,
        default_retry_label: bool = True,
        no_result_on_retry: bool = True,
        default_delay: float = 5,
        use_jitter: bool = True,
        use_delay_exponent: bool = True,
        max_delay_exponent: float = 60,
        schedule_source: Any | None = None,
        types_of_exceptions: Iterable[type[BaseException]] | None = None,
    ) -> None:
        super().__init__(
            default_retry_count=default_retry_count,
            default_retry_label=default_retry_label,
            no_result_on_retry=no_result_on_retry,
            default_delay=default_delay,
            use_jitter=use_jitter,
            use_delay_exponent=use_delay_exponent,
            max_delay_exponent=max_delay_exponent,
            schedule_source=schedule_source,
            types_of_exceptions=types_of_exceptions,
        )

    async def on_error(
        self,
        message: TaskiqMessage,
        result: TaskiqResult[Any],
        exception: BaseException,
    ) -> None:
        # A cancelled task is not a transient failure. Taskiq's receiver catches
        # `BaseException`, so `asyncio.CancelledError` arrives here like any other
        # error and — being outside PERMANENT_ERROR_TYPES — used to schedule a
        # retry. Probed: `CancelledError -> retry scheduled: True`.
        #
        # This was latent while the stack ran only in a worker, where cancellation
        # means the process is going away anyway. It became reachable when #324
        # installed the stack in the server process, where loop shutdown (uvicorn
        # reload, test teardown) cancels the inline tasks: each cancellation
        # spawned a fresh task on a loop that is closing, leaving orphaned
        # pending tasks behind.
        #
        # Deliberately only suppressing the *retry*. Cancellation is still handed
        # to the error-logging and notification middlewares, which decide for
        # themselves whether it is worth reporting.
        if isinstance(exception, asyncio.CancelledError):
            return

        if isinstance(exception, self.PERMANENT_ERROR_TYPES):
            return

        await super().on_error(message, result, exception)

    async def on_send(
        self,
        kicker: Any,
        message: TaskiqMessage,
        delay: float | None,
    ) -> None:
        """Honour the announced retry delay when the broker will not.

        `SmartRetryMiddleware` computes a backoff, logs it ("Retrying 1/3 in 5.58
        seconds") and writes it into `labels["delay"]`. Cross-process brokers
        implement that label; `InMemoryBroker` does not — `kick()` ignores it and
        goes straight to `asyncio.create_task`. Probed: three attempts completed
        within 0.1s, at 0.033s and 0.018s intervals, against an announced 5.58s
        and 11.37s.

        That made "retry with backoff" mean "hammer three times immediately",
        which is worse than useless for the transient failures retrying exists
        for — a throttled LLM call gets three more requests inside 100ms. Sleeping
        here is safe because this runs inside the detached task the inline broker
        already created, not in the request path.
        """
        if delay is not None and isinstance(self.broker, InMemoryBroker):
            await asyncio.sleep(delay)
        await super().on_send(kicker, message, delay)
