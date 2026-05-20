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

from collections.abc import Iterable
from typing import Any

import structlog
from pydantic import ValidationError
from taskiq import TaskiqMessage, TaskiqMiddleware, TaskiqResult
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
        if isinstance(exception, self.PERMANENT_ERROR_TYPES):
            return

        await super().on_error(message, result, exception)
