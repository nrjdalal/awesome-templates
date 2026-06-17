from typing import Any

import structlog
from taskiq import AsyncBroker, SendTaskError

_logger = structlog.stdlib.get_logger(__name__)


class TaskiqManager:
    def __init__(self, broker: AsyncBroker) -> None:
        self._broker = broker

    async def send_task(
        self,
        task_name: str,
        kwargs: dict[str, Any] | None = None,
        args: list[Any] | None = None,
    ) -> Any:
        try:
            task = await self._broker.kick(task_name, *(args or []), **(kwargs or {}))
            return task
        except SendTaskError:
            _logger.exception("taskiq_send_failed", task_name=task_name)
            raise
