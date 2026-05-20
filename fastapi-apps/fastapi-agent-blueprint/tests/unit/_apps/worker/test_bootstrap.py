from taskiq import InMemoryBroker, TaskiqMiddleware

from src._apps.worker.bootstrap import _install_middleware
from src._core.infrastructure.logging.taskiq_middleware import (
    PermanentAwareSmartRetryMiddleware,
    StructlogContextMiddleware,
    TaskErrorLoggingMiddleware,
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


def test_install_middleware_registers_taskiq_error_handling_order() -> None:
    broker = InMemoryBroker()

    _install_middleware(broker)

    structlog_index = _middleware_index(broker.middlewares, StructlogContextMiddleware)
    retry_index = _middleware_index(
        broker.middlewares,
        PermanentAwareSmartRetryMiddleware,
    )
    logging_index = _middleware_index(broker.middlewares, TaskErrorLoggingMiddleware)
    assert structlog_index < retry_index < logging_index
