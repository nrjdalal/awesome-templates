"""The full notification routing behaviour matrix (#327).

#286's channel routing went through four review rounds and was declared clean by
an 8-permutation × 7-status-code matrix — but that matrix lived in a review
comment, not in the suite. So the semantics the rounds established were protected
by nothing, which is a bad position from which to refactor the provider graph.

This file is that matrix, shipped. For every supported `NOTIFICATION_*`
combination it records, per status code, **which webhook URL** would receive the
alert (or that none would). URLs rather than object types: the type only says
"a Slack adapter", while the URL says *which channel*, which is the entire point
of routing.

Each row needs its own process. `CoreContainer`'s Selector branches capture
`settings.*` at class-body evaluation time, so post-import monkeypatching cannot
flip them — `tests/support/container_env.py` (built for exactly this in #330) runs
each permutation in a subprocess with the env applied before any project import.

These are `slow`: one subprocess per permutation.
"""

from __future__ import annotations

import pytest

from tests.support.container_env import boot_fails, resolve_in_env

pytestmark = pytest.mark.slow

BASE = "https://hooks.slack.com/services/T/B/BASE"
CRITICAL = "https://hooks.slack.com/services/T/B/CRIT"
WARNING = "https://hooks.slack.com/services/T/B/WARN"

# Chosen to straddle every boundary the router can have: below both tiers, at and
# above a 400 warning threshold, just under the 500 severity threshold, and at and
# above it.
STATUS_CODES = [200, 399, 400, 404, 499, 500, 502]

# What the router/notifier pair resolves for each status code, reported as the
# tail of the receiving webhook URL. `None` means "would not dispatch".
_RESOLVE_BODY_TEMPLATE = """
    notifier = container.error_notifier()
    router = container.notification_router()

    def target(status):
        client = router.resolve(status) if router is not None else notifier._client
        return getattr(client, "_webhook_url", None)

    codes = __CODES__
    result = {
        "floor": notifier._effective_min_threshold(),
        "router": type(router).__name__,
        "client_type": type(notifier._client).__name__
        if hasattr(notifier, "_client")
        else None,
        "targets": {
            str(status): (target(status) or "").rsplit("/", 1)[-1] or None
            for status in codes
        },
        "dispatches": {
            str(status): notifier._should_notify(status, "E_" + str(status))
            for status in codes
        },
    }
"""

_RESOLVE_BODY = _RESOLVE_BODY_TEMPLATE.replace("__CODES__", repr(STATUS_CODES))


def _matrix(env: dict[str, str]) -> dict:
    return resolve_in_env(env, _RESOLVE_BODY)


# --- permutations that boot -------------------------------------------------

ENABLED_NO_ROUTING = {
    "NOTIFICATION_PROVIDER": "slack",
    "SLACK_WEBHOOK_URL": BASE,
}
ROUTING_SHARED_TARGET = {**ENABLED_NO_ROUTING, "NOTIFICATION_WARNING_THRESHOLD": "400"}
ROUTING_CRITICAL_ONLY = {
    **ROUTING_SHARED_TARGET,
    "NOTIFICATION_CRITICAL_WEBHOOK_URL": CRITICAL,
}
ROUTING_WARNING_ONLY = {
    **ROUTING_SHARED_TARGET,
    "NOTIFICATION_WARNING_WEBHOOK_URL": WARNING,
}
ROUTING_BOTH_TARGETS = {
    **ROUTING_SHARED_TARGET,
    "NOTIFICATION_CRITICAL_WEBHOOK_URL": CRITICAL,
    "NOTIFICATION_WARNING_WEBHOOK_URL": WARNING,
}
DISABLED = {}


class TestTheSingleTargetPathIsUnchanged:
    """#17 behaviour: only `>= severity_threshold` dispatches, all to one URL.

    This is the row a provider-graph refactor is most likely to break, because it
    is the row that does NOT go through the router today.
    """

    def test_only_5xx_dispatches_and_always_to_the_base_url(self):
        out = _matrix(ENABLED_NO_ROUTING)
        assert out["floor"] == 500
        assert out["dispatches"] == {
            "200": False,
            "399": False,
            "400": False,
            "404": False,
            "499": False,
            "500": True,
            "502": True,
        }
        for status in ("500", "502"):
            assert out["targets"][status] == "BASE"


class TestRoutingWithNoPerTierOverrides:
    """`NOTIFICATION_WARNING_THRESHOLD` alone lowers the floor and splits the band,
    with both tiers landing on the single configured webhook."""

    def test_the_floor_drops_to_the_warning_threshold(self):
        out = _matrix(ROUTING_SHARED_TARGET)
        assert out["floor"] == 400
        assert out["dispatches"] == {
            "200": False,
            "399": False,
            "400": True,
            "404": True,
            "499": True,
            "500": True,
            "502": True,
        }

    def test_both_tiers_share_the_base_url(self):
        out = _matrix(ROUTING_SHARED_TARGET)
        for status in ("400", "404", "499", "500", "502"):
            assert out["targets"][status] == "BASE", status


class TestRoutingWithPerTierOverrides:
    @pytest.mark.parametrize(
        "env,expected",
        [
            (
                ROUTING_CRITICAL_ONLY,
                {"400": "BASE", "499": "BASE", "500": "CRIT", "502": "CRIT"},
            ),
            (
                ROUTING_WARNING_ONLY,
                {"400": "WARN", "499": "WARN", "500": "BASE", "502": "BASE"},
            ),
            (
                ROUTING_BOTH_TARGETS,
                {"400": "WARN", "499": "WARN", "500": "CRIT", "502": "CRIT"},
            ),
        ],
        ids=["critical-override", "warning-override", "both-overrides"],
    )
    def test_each_tier_resolves_to_its_own_channel(self, env, expected):
        out = _matrix(env)
        for status, tail in expected.items():
            assert out["targets"][status] == tail, (
                f"status {status} routed to {out['targets'][status]}, expected {tail}"
            )

    def test_below_both_tiers_never_dispatches(self):
        out = _matrix(ROUTING_BOTH_TARGETS)
        assert out["dispatches"]["200"] is False
        assert out["dispatches"]["399"] is False
        assert out["targets"]["200"] is None
        assert out["targets"]["399"] is None


class TestTheDisabledPath:
    def test_nothing_is_delivered_and_the_floor_is_the_default(self):
        out = _matrix(DISABLED)
        assert out["floor"] == 500
        # The Noop client has no webhook URL, which is what "delivered nowhere"
        # looks like from the outside.
        assert out["targets"]["500"] is None
        assert out["targets"]["502"] is None


class TestTheCombinationsThatMustNotBoot:
    """#315: a per-tier URL without the threshold used to boot and silently send
    everything to the base webhook. Pinned here so the collapse cannot relax it."""

    @pytest.mark.parametrize(
        "env",
        [
            {**ENABLED_NO_ROUTING, "NOTIFICATION_CRITICAL_WEBHOOK_URL": CRITICAL},
            {**ENABLED_NO_ROUTING, "NOTIFICATION_WARNING_WEBHOOK_URL": WARNING},
        ],
        ids=["critical-url-without-threshold", "warning-url-without-threshold"],
    )
    def test_a_per_tier_url_without_the_threshold_is_rejected(self, env):
        error = boot_fails(env)
        assert error is not None, "the combination booted; #315 has regressed"
        assert "NOTIFICATION_WARNING_THRESHOLD" in error or "Routing" in error


class TestOneAdapterPerDistinctChannel:
    """The provider-graph half of #327.

    Both tier targets fall back to the single provider webhook, and the per-tier
    Selectors used to be two-way enabled/disabled — so a tier with no override
    still built its own adapter against the same URL. Probed before the change,
    with routing on and no overrides: `distinct adapter objects: 3`.

    That footprint produced both defects found in round 1 of PR #313 — three
    `NoopNotificationClient` instances instead of one, and an injected client the
    router short-circuits. The symptoms were patched then; this asserts the shape
    is gone, so the instance count is now exactly the number of distinct channels.
    """

    _IDENTITY_BODY = """
        names = (
            "notification_client",
            "notification_critical_client",
            "notification_warning_client",
        )
        objs = {name: getattr(container, name)() for name in names}
        result = {
            "distinct": len({id(o) for o in objs.values()}),
            "urls": {
                name: (getattr(o, "_webhook_url", None) or "").rsplit("/", 1)[-1] or None
                for name, o in objs.items()
            },
        }
    """

    @pytest.mark.parametrize(
        "env,expected_adapters,expected_urls",
        [
            (ENABLED_NO_ROUTING, 1, ("BASE", "BASE", "BASE")),
            (ROUTING_SHARED_TARGET, 1, ("BASE", "BASE", "BASE")),
            (ROUTING_CRITICAL_ONLY, 2, ("BASE", "CRIT", "BASE")),
            (ROUTING_WARNING_ONLY, 2, ("BASE", "BASE", "WARN")),
            (ROUTING_BOTH_TARGETS, 3, ("BASE", "CRIT", "WARN")),
        ],
        ids=["no-routing", "shared", "critical-only", "warning-only", "both"],
    )
    def test_the_instance_count_equals_the_channel_count(
        self, env, expected_adapters, expected_urls
    ):
        out = resolve_in_env(env, self._IDENTITY_BODY)
        base, critical, warning = expected_urls

        # URLs first: collapsing instances must not change where anything is sent.
        assert out["urls"]["notification_client"] == base
        assert out["urls"]["notification_critical_client"] == critical
        assert out["urls"]["notification_warning_client"] == warning

        assert out["distinct"] == expected_adapters, (
            f"{out['distinct']} adapter instances for {expected_adapters} distinct "
            f"channel(s): {out['urls']}"
        )

    def test_the_disabled_path_shares_one_noop(self):
        """Already true, and load-bearing: `NoopNotificationClient` logs its warning
        from `__init__`, so a separate instance per tier means the
        `notification_client_disabled` line appears once per tier instead of once
        per process."""
        out = resolve_in_env(DISABLED, self._IDENTITY_BODY)
        assert out["distinct"] == 1


class TestTheSameHoldsForDiscord:
    """The matrix above is Slack-only, which a review flagged: it does not directly
    guard a Discord regression. The three-way selector is provider-agnostic — it
    branches on which URL is configured, not on the transport — so this pins that
    for the one other supported provider rather than leaving it inferred.
    """

    # Placeholder id shape, not a digit id: the `discord-webhook-url` gitleaks rule
    # this repo added in #320 matches `webhooks/\d+/[\w-]+`, and a realistic
    # fixture trips it. Learned the same lesson twice — #320 had to clean five
    # existing fixtures for exactly this, and the rule then caught these two.
    D_BASE = "https://discord.com/api/webhooks/<base-id>/base-token"
    D_CRIT = "https://discord.com/api/webhooks/<crit-id>/crit-token"

    def _env(self, **extra) -> dict[str, str]:
        return {
            "NOTIFICATION_PROVIDER": "discord",
            "DISCORD_WEBHOOK_URL": self.D_BASE,
            **extra,
        }

    def test_the_adapter_is_the_discord_one_and_shared_when_untiered(self):
        out = resolve_in_env(
            self._env(NOTIFICATION_WARNING_THRESHOLD="400"),
            TestOneAdapterPerDistinctChannel._IDENTITY_BODY,
        )
        assert out["distinct"] == 1, (
            f"{out['distinct']} adapters for one Discord channel: {out['urls']}"
        )

    def test_a_discord_per_tier_override_still_splits(self):
        out = resolve_in_env(
            self._env(
                NOTIFICATION_WARNING_THRESHOLD="400",
                NOTIFICATION_CRITICAL_WEBHOOK_URL=self.D_CRIT,
            ),
            TestOneAdapterPerDistinctChannel._IDENTITY_BODY,
        )
        assert out["distinct"] == 2
        assert out["urls"]["notification_critical_client"] == "crit-token"
        assert out["urls"]["notification_warning_client"] == "base-token"

    def test_the_delivered_target_matches_the_tier(self):
        out = _matrix(
            self._env(
                NOTIFICATION_WARNING_THRESHOLD="400",
                NOTIFICATION_CRITICAL_WEBHOOK_URL=self.D_CRIT,
            )
        )
        assert out["targets"]["502"] == "crit-token"
        assert out["targets"]["404"] == "base-token"
        assert out["targets"]["200"] is None
