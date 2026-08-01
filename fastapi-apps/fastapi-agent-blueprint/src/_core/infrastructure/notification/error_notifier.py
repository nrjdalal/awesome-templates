from __future__ import annotations

import asyncio
import time

import structlog

from src._core.domain.protocols.notification_protocol import BaseNotificationProtocol
from src._core.infrastructure.notification.notification_router import (
    NotificationRouter,
)

_logger = structlog.stdlib.get_logger(__name__)


class ErrorNotifier:
    """Gates outbound Slack/Discord error alerts by severity threshold and
    an in-memory cooldown, and dispatches them fire-and-forget so a slow
    webhook endpoint never adds latency to the request/response path.

    The cooldown is per-process only — it does not dedupe repeated errors
    across multiple worker/server processes.

    ``notification_router`` is optional (#286): when omitted (the default),
    every qualifying error is sent to ``notification_client`` exactly as in
    #17 — a single target, no routing. When a :class:`NotificationRouter`
    is supplied, it is used to resolve the target client per dispatch (and,
    if it defines a lower ``warning_threshold``, may widen the gate below
    ``severity_threshold`` to also notify — opt-in only, see
    :class:`NotificationRouter`).
    """

    def __init__(
        self,
        notification_client: BaseNotificationProtocol,
        severity_threshold: int,
        cooldown_seconds: int,
        notification_router: NotificationRouter | None = None,
    ) -> None:
        self._client = notification_client
        self._severity_threshold = severity_threshold
        self._cooldown_seconds = cooldown_seconds
        self._router = notification_router
        self._last_notified_at: dict[str, float] = {}
        # Keep strong references so asyncio does not GC in-flight tasks.
        self._background_tasks: set[asyncio.Task] = set()

    def maybe_dispatch(
        self, *, status_code: int, error_code: str, message: str
    ) -> None:
        """Fire-and-forget dispatch. Never awaits the webhook call itself."""
        if not self._should_notify(status_code, error_code):
            return
        task = asyncio.create_task(self._safe_send(status_code, error_code, message))
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    def _should_notify(self, status_code: int, error_code: str) -> bool:
        if status_code < self._effective_min_threshold():
            return False
        key = self._cooldown_key(status_code, error_code)
        now = time.monotonic()
        last_notified = self._last_notified_at.get(key)
        if last_notified is not None and (now - last_notified) < self._cooldown_seconds:
            return False
        self._last_notified_at[key] = now
        return True

    def _cooldown_key(self, status_code: int, error_code: str) -> str:
        """Cooldown key, scoped by severity tier when routing is active (#286).

        Without a router the key is the bare ``error_code``, unchanged from
        #17. With one, a warning-tier 4xx and a critical-tier 5xx sharing an
        ``error_code`` must not share a quiet window — otherwise the 4xx
        silently mutes the incident alert. Mirrors #310's
        ``{task_name}:{error_code}`` scoping on the worker path.

        The band test matches ``NotificationRouter.resolve`` exactly, so the
        key and the delivered channel can never disagree.
        """
        if self._router is None:
            return error_code
        tier = "critical" if status_code >= self._severity_threshold else "warning"
        return f"{tier}:{error_code}"

    def _effective_min_threshold(self) -> int:
        """The lowest status code that can qualify for notification.

        Equal to ``severity_threshold`` unless a router with a lower
        ``warning_threshold`` is configured (#286) — in which case the gate
        widens to admit the warning band too. No router, or no
        ``warning_threshold`` set on it, reproduces #17's behavior exactly.
        """
        if self._router is not None and self._router.warning_threshold is not None:
            return min(self._severity_threshold, self._router.warning_threshold)
        return self._severity_threshold

    async def _safe_send(self, status_code: int, error_code: str, message: str) -> None:
        try:
            client = (
                self._router.resolve(status_code)
                if self._router is not None
                else self._client
            )
            if client is None:
                return
            await client.send(message)
        except Exception as exc:
            # exc_info would embed the webhook URL (a credential) via
            # aiohttp's ClientResponseError message — log the failure
            # class only.
            _logger.warning(
                "error_notification_send_failed",
                error_code=error_code,
                exc_type=type(exc).__name__,
            )
