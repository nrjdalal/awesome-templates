from __future__ import annotations

import asyncio
import time

import structlog

from src._core.domain.protocols.notification_protocol import BaseNotificationProtocol

_logger = structlog.stdlib.get_logger(__name__)


class ErrorNotifier:
    """Gates outbound Slack/Discord error alerts by severity threshold and
    an in-memory cooldown, and dispatches them fire-and-forget so a slow
    webhook endpoint never adds latency to the request/response path.

    The cooldown is per-process only — it does not dedupe repeated errors
    across multiple worker/server processes.
    """

    def __init__(
        self,
        notification_client: BaseNotificationProtocol,
        severity_threshold: int,
        cooldown_seconds: int,
    ) -> None:
        self._client = notification_client
        self._severity_threshold = severity_threshold
        self._cooldown_seconds = cooldown_seconds
        self._last_notified_at: dict[str, float] = {}
        # Keep strong references so asyncio does not GC in-flight tasks.
        self._background_tasks: set[asyncio.Task] = set()

    def maybe_dispatch(
        self, *, status_code: int, error_code: str, message: str
    ) -> None:
        """Fire-and-forget dispatch. Never awaits the webhook call itself."""
        if not self._should_notify(status_code, error_code):
            return
        task = asyncio.create_task(self._safe_send(error_code, message))
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    def _should_notify(self, status_code: int, error_code: str) -> bool:
        if status_code < self._severity_threshold:
            return False
        now = time.monotonic()
        last_notified = self._last_notified_at.get(error_code)
        if last_notified is not None and (now - last_notified) < self._cooldown_seconds:
            return False
        self._last_notified_at[error_code] = now
        return True

    async def _safe_send(self, error_code: str, message: str) -> None:
        try:
            await self._client.send(message)
        except Exception as exc:
            # exc_info would embed the webhook URL (a credential) via
            # aiohttp's ClientResponseError message — log the failure
            # class only.
            _logger.warning(
                "error_notification_send_failed",
                error_code=error_code,
                exc_type=type(exc).__name__,
            )
