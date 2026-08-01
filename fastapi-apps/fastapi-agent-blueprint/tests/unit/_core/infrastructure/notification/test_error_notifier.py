"""Unit tests for ErrorNotifier (#17): severity threshold gating, per-error_code
cooldown suppression, and fire-and-forget dispatch (never awaits ``send``
directly from the caller).

``TestNotificationRouterIntegration`` at the bottom covers #286's opt-in
severity-routing behavior; every other test class here constructs
``ErrorNotifier`` without a router, and must keep passing unchanged to prove
#286 does not regress #17's single-target default.
"""

from __future__ import annotations

import asyncio

from src._core.infrastructure.notification.error_notifier import ErrorNotifier
from src._core.infrastructure.notification.notification_router import (
    NotificationRouter,
)


class FakeNotificationClient:
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send(self, message: str) -> None:
        self.sent.append(message)


class FailingNotificationClient:
    async def send(self, message: str) -> None:
        raise RuntimeError("webhook unreachable")


async def _drain(notifier: ErrorNotifier) -> None:
    """Await any in-flight background tasks the notifier scheduled."""
    if notifier._background_tasks:
        await asyncio.gather(*notifier._background_tasks)


class TestSeverityThresholdGating:
    async def test_below_threshold_is_not_dispatched(self):
        client = FakeNotificationClient()
        notifier = ErrorNotifier(
            notification_client=client, severity_threshold=500, cooldown_seconds=60
        )

        notifier.maybe_dispatch(status_code=404, error_code="NOT_FOUND", message="x")
        await _drain(notifier)

        assert client.sent == []

    async def test_at_or_above_threshold_is_dispatched(self):
        client = FakeNotificationClient()
        notifier = ErrorNotifier(
            notification_client=client, severity_threshold=500, cooldown_seconds=60
        )

        notifier.maybe_dispatch(
            status_code=500, error_code="INTERNAL_SERVER_ERROR", message="boom"
        )
        await _drain(notifier)

        assert client.sent == ["boom"]


class TestCooldownSuppression:
    async def test_repeat_error_within_cooldown_is_suppressed(self):
        client = FakeNotificationClient()
        notifier = ErrorNotifier(
            notification_client=client, severity_threshold=500, cooldown_seconds=60
        )

        notifier.maybe_dispatch(status_code=500, error_code="DB_ERROR", message="first")
        notifier.maybe_dispatch(
            status_code=500, error_code="DB_ERROR", message="second"
        )
        await _drain(notifier)

        assert client.sent == ["first"]

    async def test_different_error_codes_are_not_suppressed(self):
        client = FakeNotificationClient()
        notifier = ErrorNotifier(
            notification_client=client, severity_threshold=500, cooldown_seconds=60
        )

        notifier.maybe_dispatch(status_code=500, error_code="DB_ERROR", message="a")
        notifier.maybe_dispatch(status_code=500, error_code="LLM_ERROR", message="b")
        await _drain(notifier)

        assert client.sent == ["a", "b"]

    async def test_cooldown_expired_allows_repeat_notification(self):
        client = FakeNotificationClient()
        notifier = ErrorNotifier(
            notification_client=client, severity_threshold=500, cooldown_seconds=60
        )
        # Simulate the cooldown window having already elapsed.
        notifier._last_notified_at["DB_ERROR"] = 0.0

        notifier.maybe_dispatch(status_code=500, error_code="DB_ERROR", message="again")
        await _drain(notifier)

        assert client.sent == ["again"]


class TestFireAndForgetDispatch:
    async def test_maybe_dispatch_returns_before_send_completes(self):
        """maybe_dispatch must not await the webhook call — the caller (the
        exception handler) needs to get its response back immediately."""

        started = asyncio.Event()
        release = asyncio.Event()

        class SlowClient:
            async def send(self, message: str) -> None:
                started.set()
                await release.wait()

        notifier = ErrorNotifier(
            notification_client=SlowClient(),
            severity_threshold=500,
            cooldown_seconds=60,
        )

        notifier.maybe_dispatch(status_code=500, error_code="SLOW", message="x")
        # maybe_dispatch already returned synchronously; the send is still
        # in flight until we release it below.
        release.set()
        await _drain(notifier)

    async def test_send_failure_is_swallowed_not_raised(self):
        notifier = ErrorNotifier(
            notification_client=FailingNotificationClient(),
            severity_threshold=500,
            cooldown_seconds=60,
        )

        notifier.maybe_dispatch(status_code=500, error_code="X", message="x")
        # Must not raise even though the underlying send() blows up.
        await _drain(notifier)


class TestNotificationRouterIntegration:
    """#286: ErrorNotifier delegates target resolution to an optional
    NotificationRouter and widens its gate when the router defines a
    warning_threshold below severity_threshold."""

    async def test_no_router_behaves_exactly_like_hash17(self):
        client = FakeNotificationClient()
        notifier = ErrorNotifier(
            notification_client=client, severity_threshold=500, cooldown_seconds=60
        )

        notifier.maybe_dispatch(status_code=404, error_code="NOT_FOUND", message="x")
        notifier.maybe_dispatch(status_code=500, error_code="ERR", message="boom")
        await _drain(notifier)

        assert client.sent == ["boom"]

    async def test_router_without_warning_threshold_only_notifies_critical(self):
        fallback_client = FakeNotificationClient()
        critical = FakeNotificationClient()
        warning = FakeNotificationClient()
        router = NotificationRouter(
            critical_client=critical,
            warning_client=warning,
            severity_threshold=500,
            warning_threshold=None,
        )
        notifier = ErrorNotifier(
            notification_client=fallback_client,
            severity_threshold=500,
            cooldown_seconds=60,
            notification_router=router,
        )

        notifier.maybe_dispatch(status_code=404, error_code="NOT_FOUND", message="x")
        notifier.maybe_dispatch(status_code=500, error_code="ERR", message="boom")
        await _drain(notifier)

        assert critical.sent == ["boom"]
        assert warning.sent == []
        assert fallback_client.sent == []

    async def test_warning_threshold_widens_gate_and_routes_to_warning_client(self):
        critical = FakeNotificationClient()
        warning = FakeNotificationClient()
        router = NotificationRouter(
            critical_client=critical,
            warning_client=warning,
            severity_threshold=500,
            warning_threshold=400,
        )
        notifier = ErrorNotifier(
            notification_client=critical,
            severity_threshold=500,
            cooldown_seconds=60,
            notification_router=router,
        )

        notifier.maybe_dispatch(status_code=404, error_code="NOT_FOUND", message="soft")
        notifier.maybe_dispatch(status_code=500, error_code="ERR", message="hard")
        await _drain(notifier)

        assert warning.sent == ["soft"]
        assert critical.sent == ["hard"]

    async def test_still_below_warning_threshold_is_not_dispatched(self):
        critical = FakeNotificationClient()
        warning = FakeNotificationClient()
        router = NotificationRouter(
            critical_client=critical,
            warning_client=warning,
            severity_threshold=500,
            warning_threshold=400,
        )
        notifier = ErrorNotifier(
            notification_client=critical,
            severity_threshold=500,
            cooldown_seconds=60,
            notification_router=router,
        )

        notifier.maybe_dispatch(status_code=200, error_code="X", message="x")
        await _drain(notifier)

        assert critical.sent == []
        assert warning.sent == []

    async def test_cooldown_is_scoped_per_tier(self):
        """The cooldown key is scoped by severity tier, not the bare
        error_code — a warning-tier 4xx must not mute a critical-tier 5xx
        sharing the same error_code (#313 round-2 HIGH finding)."""
        critical = FakeNotificationClient()
        warning = FakeNotificationClient()
        router = NotificationRouter(
            critical_client=critical,
            warning_client=warning,
            severity_threshold=500,
            warning_threshold=400,
        )
        notifier = ErrorNotifier(
            notification_client=critical,
            severity_threshold=500,
            cooldown_seconds=60,
            notification_router=router,
        )

        notifier.maybe_dispatch(status_code=404, error_code="SAME", message="first")
        notifier.maybe_dispatch(status_code=500, error_code="SAME", message="second")
        await _drain(notifier)

        assert warning.sent == ["first"]
        assert critical.sent == ["second"]

    async def test_cooldown_still_suppresses_within_same_tier(self):
        """Within a single tier, a repeat error_code inside the cooldown
        window is still suppressed — the tier scoping only separates
        different tiers, it doesn't disable the cooldown."""
        critical = FakeNotificationClient()
        warning = FakeNotificationClient()
        router = NotificationRouter(
            critical_client=critical,
            warning_client=warning,
            severity_threshold=500,
            warning_threshold=400,
        )
        notifier = ErrorNotifier(
            notification_client=critical,
            severity_threshold=500,
            cooldown_seconds=60,
            notification_router=router,
        )

        notifier.maybe_dispatch(status_code=500, error_code="SAME", message="first")
        notifier.maybe_dispatch(status_code=503, error_code="SAME", message="second")
        await _drain(notifier)

        assert critical.sent == ["first"]
