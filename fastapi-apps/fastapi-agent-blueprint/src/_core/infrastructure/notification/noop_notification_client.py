from __future__ import annotations

import structlog

_logger = structlog.stdlib.get_logger(__name__)


class NoopNotificationClient:
    """No-op fallback used when no NOTIFICATION_PROVIDER is configured.

    Lets ``ErrorNotifier`` run unconditionally regardless of whether Slack/
    Discord is wired up. Logs once at construction so operators know error
    alerts are not actually being delivered.
    """

    def __init__(self) -> None:
        _logger.warning(
            "notification_client_disabled",
            hint="Set NOTIFICATION_PROVIDER + SLACK_WEBHOOK_URL/DISCORD_WEBHOOK_URL "
            "to enable Slack/Discord alerts.",
        )

    async def send(self, message: str) -> None:
        _logger.info("notification_suppressed", message=message)
