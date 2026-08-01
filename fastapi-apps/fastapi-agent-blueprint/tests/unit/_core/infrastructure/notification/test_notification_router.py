"""Unit tests for NotificationRouter (#286): severity-tier client
resolution built on top of #17's single-target ErrorNotifier."""

from __future__ import annotations

from src._core.infrastructure.notification.notification_router import (
    NotificationRouter,
)


class FakeClient:
    def __init__(self, name: str) -> None:
        self.name = name

    async def send(self, message: str) -> None:  # pragma: no cover - unused here
        raise NotImplementedError


class TestNoWarningThresholdConfigured:
    """warning_threshold=None must reproduce #17's single-target gate
    exactly: only the critical tier ever resolves."""

    def test_at_or_above_severity_threshold_resolves_critical(self):
        critical = FakeClient("critical")
        warning = FakeClient("warning")
        router = NotificationRouter(
            critical_client=critical,
            warning_client=warning,
            severity_threshold=500,
            warning_threshold=None,
        )

        assert router.resolve(500) is critical
        assert router.resolve(503) is critical

    def test_below_severity_threshold_resolves_nothing(self):
        critical = FakeClient("critical")
        warning = FakeClient("warning")
        router = NotificationRouter(
            critical_client=critical,
            warning_client=warning,
            severity_threshold=500,
            warning_threshold=None,
        )

        assert router.resolve(499) is None
        assert router.resolve(404) is None


class TestWarningThresholdConfigured:
    def test_warning_band_resolves_warning_client(self):
        critical = FakeClient("critical")
        warning = FakeClient("warning")
        router = NotificationRouter(
            critical_client=critical,
            warning_client=warning,
            severity_threshold=500,
            warning_threshold=400,
        )

        assert router.resolve(404) is warning
        assert router.resolve(400) is warning

    def test_critical_band_still_resolves_critical_client(self):
        critical = FakeClient("critical")
        warning = FakeClient("warning")
        router = NotificationRouter(
            critical_client=critical,
            warning_client=warning,
            severity_threshold=500,
            warning_threshold=400,
        )

        assert router.resolve(500) is critical
        assert router.resolve(503) is critical

    def test_below_warning_threshold_resolves_nothing(self):
        critical = FakeClient("critical")
        warning = FakeClient("warning")
        router = NotificationRouter(
            critical_client=critical,
            warning_client=warning,
            severity_threshold=500,
            warning_threshold=400,
        )

        assert router.resolve(399) is None
        assert router.resolve(200) is None

    def test_same_client_for_both_tiers_when_no_channel_override(self):
        """Shared-fallback case: both tiers point at the same client
        (settings-level fallback to the single-target webhook)."""
        shared = FakeClient("shared")
        router = NotificationRouter(
            critical_client=shared,
            warning_client=shared,
            severity_threshold=500,
            warning_threshold=400,
        )

        assert router.resolve(404) is shared
        assert router.resolve(500) is shared
