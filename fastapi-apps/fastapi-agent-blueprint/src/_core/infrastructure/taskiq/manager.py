from typing import Any

from taskiq import AsyncBroker, SendTaskError


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
        except SendTaskError as e:
            # TODO: add logging
            raise e
