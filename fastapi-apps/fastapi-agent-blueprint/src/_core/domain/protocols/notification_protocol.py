from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class BaseNotificationProtocol(Protocol):
    """Backend-agnostic error-notification protocol.

    Abstraction boundary for Slack/Discord webhook adapters (and the
    no-op fallback used when no provider is configured). Domain-facing
    infra (``ErrorNotifier``) depends on this protocol, not on a
    specific provider.
    """

    async def send(self, message: str) -> None: ...
