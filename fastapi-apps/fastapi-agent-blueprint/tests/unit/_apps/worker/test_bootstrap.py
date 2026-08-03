from taskiq import InMemoryBroker, TaskiqMiddleware

from src._apps.worker.bootstrap import install_task_middleware
from src._apps.worker.broker import container
from src._core.infrastructure.logging.taskiq_middleware import (
    PermanentAwareSmartRetryMiddleware,
    StructlogContextMiddleware,
    TaskErrorLoggingMiddleware,
)
from src._core.infrastructure.notification.taskiq_middleware import (
    TaskFailureNotificationMiddleware,
)


def _middleware_index(
    middlewares: list[TaskiqMiddleware],
    middleware_type: type[TaskiqMiddleware],
) -> int:
    return next(
        index
        for index, middleware in enumerate(middlewares)
        if isinstance(middleware, middleware_type)
    )


def test_install_task_middleware_registers_taskiq_error_handling_order() -> None:
    broker = InMemoryBroker()

    install_task_middleware(broker, error_notifier_provider=container.error_notifier)

    structlog_index = _middleware_index(broker.middlewares, StructlogContextMiddleware)
    retry_index = _middleware_index(
        broker.middlewares,
        PermanentAwareSmartRetryMiddleware,
    )
    logging_index = _middleware_index(broker.middlewares, TaskErrorLoggingMiddleware)
    notifier_index = _middleware_index(
        broker.middlewares,
        TaskFailureNotificationMiddleware,
    )
    # The notifier goes LAST so taskiq's reversed() on_error fan-out runs it
    # FIRST — before the retry middleware increments message.labels["_retries"]
    # in place. Its final-attempt gating reads that counter, so an earlier
    # position silently shifts every worker alert one attempt early (#310).
    assert structlog_index < retry_index < logging_index < notifier_index
