"""Unit tests for the admin dashboard read facade (#193, reworked in #368).

Focus: the never-raise / per-source isolation invariants. One failing metric
source must degrade only its own section (``count=None`` / ``available=False``)
without raising or affecting the others, and no raw exception text escapes.

The audit-derived sections and their collection were removed in #368 —
``/admin/audit-log`` is a strict superset — so the tests that covered them are
gone with them rather than kept green against dead code.
"""

from __future__ import annotations

from datetime import date, datetime

from src._apps.admin import dashboard_metrics as dm
from src._apps.admin.operational_status import InfraState
from src._core.domain.value_objects.daily_count import DailyCount
from src._core.infrastructure.admin.theme import AdminClasses


class _FakeService:
    """A CRUD service with the two capabilities the dashboard probes for."""

    def __init__(
        self,
        count: int | Exception = 0,
        points: list[DailyCount] | Exception | None = None,
    ) -> None:
        self._count = count
        self._points = points if points is not None else []
        self.since_seen: datetime | None = None

    async def count_datas(self) -> int:
        if isinstance(self._count, Exception):
            raise self._count
        return self._count

    async def count_datas_by_day(
        self, *, since: datetime, column_name: str = "created_at"
    ) -> list[DailyCount]:
        self.since_seen = since
        if isinstance(self._points, Exception):
            raise self._points
        return self._points


class _ServiceWithoutCount:
    """Mimics a CRUD service that implements neither probed capability."""


class _UsageSummary:
    def __init__(self, call_count: int, total_tokens: int = 0) -> None:
        self.call_count = call_count
        self.total_tokens = total_tokens


class _FakeUsageService:
    """Mimics AiUsageService: `get_usage_summary` returns (summary, by_org)."""

    def __init__(
        self,
        total: int,
        ok: int,
        *,
        tokens: int = 0,
        raise_exc: Exception | None = None,
    ) -> None:
        self._total = total
        self._ok = ok
        self._tokens = tokens
        self._raise = raise_exc
        self.calls: list[str | None] = []

    async def get_usage_summary(self, *, start_at=None, status=None, **_):
        if self._raise is not None:
            raise self._raise
        self.calls.append(status)
        count = self._ok if status == "ok" else self._total
        return _UsageSummary(count, self._tokens), []


class _FakeConfig:
    def __init__(self, name: str, service: object) -> None:
        self.domain_name = name
        self.display_name = name.title()
        self.icon = "folder"
        self._service = service

    def _get_service(self) -> object:
        return self._service


def _points(*pairs: tuple[int, int]) -> list[DailyCount]:
    return [DailyCount(day=date(2026, 8, d), count=n) for d, n in pairs]


class TestPerSourceIsolation:
    async def test_one_failing_count_does_not_affect_the_others(self):
        configs = [
            _FakeConfig("user", _FakeService(count=10)),
            _FakeConfig("docs", _FakeService(count=RuntimeError("db down"))),
        ]

        metrics = await dm.collect_dashboard_metrics(configs)  # type: ignore[arg-type]

        by_name = {dc.domain_name: dc.count for dc in metrics.domain_counts}
        assert by_name == {"user": 10, "docs": None}

    async def test_a_service_missing_the_capability_degrades_to_none(self):
        configs = [_FakeConfig("legacy", _ServiceWithoutCount())]

        metrics = await dm.collect_dashboard_metrics(configs)  # type: ignore[arg-type]

        assert metrics.domain_counts[0].count is None
        assert metrics.growth[0].points is None

    async def test_a_failing_growth_read_leaves_the_count_intact(self):
        configs = [
            _FakeConfig("user", _FakeService(count=3, points=RuntimeError("no column")))
        ]

        metrics = await dm.collect_dashboard_metrics(configs)  # type: ignore[arg-type]

        assert metrics.domain_counts[0].count == 3
        assert metrics.growth[0].available is False

    async def test_no_sources_at_all_still_returns_a_full_object(self):
        metrics = await dm.collect_dashboard_metrics([])

        assert metrics.domain_counts == []
        assert metrics.growth == []
        assert metrics.ai_usage.available is False
        assert metrics.infra, "infra is settings-derived and always present"


class TestGrowthWindow:
    async def test_window_start_is_naive_and_days_back(self):
        now = datetime(2026, 8, 11, 12, 0)

        since = dm.window_start(now)

        assert since == datetime(2026, 8, 4, 12, 0)
        assert since.tzinfo is None, (
            "columns in-tree are naive DateTime; an aware bound would not compare"
        )

    async def test_the_same_window_reaches_every_domain(self):
        svc_a, svc_b = _FakeService(count=1), _FakeService(count=1)
        configs = [_FakeConfig("a", svc_a), _FakeConfig("b", svc_b)]

        await dm.collect_dashboard_metrics(
            configs,  # type: ignore[arg-type]
            now=datetime(2026, 8, 11, 12, 0),
        )

        assert svc_a.since_seen == svc_b.since_seen == datetime(2026, 8, 4, 12, 0)

    async def test_growth_total_sums_the_points(self):
        configs = [
            _FakeConfig("user", _FakeService(count=9, points=_points((9, 2), (10, 3))))
        ]

        metrics = await dm.collect_dashboard_metrics(configs)  # type: ignore[arg-type]

        assert metrics.growth[0].total == 5


class TestAiUsage:
    async def test_failures_are_derived_by_subtraction(self):
        """`UsageStatus` has three failure states, so summing them would let a
        fourth added later count as success. total - ok cannot drift that way."""
        svc = _FakeUsageService(total=10, ok=7, tokens=1234)
        configs = [_FakeConfig("ai_usage", svc)]

        metrics = await dm.collect_dashboard_metrics(configs)  # type: ignore[arg-type]

        assert metrics.ai_usage.calls == 10
        assert metrics.ai_usage.failures == 3
        assert metrics.ai_usage.total_tokens == 1234
        assert svc.calls == [None, "ok"], "one unfiltered read plus one ok-only read"

    async def test_failure_rate_is_none_without_calls(self):
        """A healthy 0% for a system that served nothing is a false reassurance."""
        configs = [_FakeConfig("ai_usage", _FakeUsageService(total=0, ok=0))]

        metrics = await dm.collect_dashboard_metrics(configs)  # type: ignore[arg-type]

        assert metrics.ai_usage.calls == 0
        assert metrics.ai_usage.failure_rate is None

    async def test_failure_rate_when_calls_exist(self):
        configs = [_FakeConfig("ai_usage", _FakeUsageService(total=4, ok=3))]

        metrics = await dm.collect_dashboard_metrics(configs)  # type: ignore[arg-type]

        assert metrics.ai_usage.failure_rate == 0.25

    async def test_absent_domain_means_unavailable_not_zero(self):
        """A fork that drops ai_usage loses the panel, not the page."""
        configs = [_FakeConfig("user", _FakeService(count=1))]

        metrics = await dm.collect_dashboard_metrics(configs)  # type: ignore[arg-type]

        assert metrics.ai_usage.available is False
        assert metrics.ai_usage.calls is None

    async def test_a_failing_summary_degrades_only_that_panel(self):
        configs = [
            _FakeConfig("user", _FakeService(count=2)),
            _FakeConfig(
                "ai_usage", _FakeUsageService(0, 0, raise_exc=RuntimeError("x"))
            ),
        ]

        metrics = await dm.collect_dashboard_metrics(configs)  # type: ignore[arg-type]

        assert metrics.ai_usage.available is False
        assert metrics.domain_counts[0].count == 2


class TestOnboardingDecision:
    async def test_all_zero_counts_means_no_data(self):
        configs = [
            _FakeConfig("user", _FakeService(count=0)),
            _FakeConfig("docs", _FakeService(count=0)),
        ]

        metrics = await dm.collect_dashboard_metrics(configs)  # type: ignore[arg-type]

        assert metrics.has_any_data is False

    async def test_any_nonzero_count_means_data(self):
        configs = [
            _FakeConfig("user", _FakeService(count=0)),
            _FakeConfig("docs", _FakeService(count=1)),
        ]

        metrics = await dm.collect_dashboard_metrics(configs)  # type: ignore[arg-type]

        assert metrics.has_any_data is True

    async def test_agent_calls_alone_count_as_data(self):
        configs = [
            _FakeConfig("user", _FakeService(count=0)),
            _FakeConfig("ai_usage", _FakeUsageService(total=3, ok=3)),
        ]

        metrics = await dm.collect_dashboard_metrics(configs)  # type: ignore[arg-type]

        assert metrics.has_any_data is True

    async def test_unavailable_sources_are_not_evidence_of_data(self):
        """A broken backend must not skip the onboarding view — `None` is not a
        record count."""
        configs = [_FakeConfig("user", _FakeService(count=RuntimeError("db down")))]

        metrics = await dm.collect_dashboard_metrics(configs)  # type: ignore[arg-type]

        assert metrics.domain_counts[0].count is None
        assert metrics.has_any_data is False

    async def test_infrastructure_alone_never_counts_as_data(self):
        """Every install has infra to report, so counting it would mean the
        onboarding view never appears — the state every adopter opens first."""
        metrics = await dm.collect_dashboard_metrics([])

        assert metrics.infra, "settings-derived, always populated"
        assert metrics.has_any_data is False


class TestInfrastructurePanelGate:
    """Who may see the deployment's configuration posture (#368 security review).

    `require_auth_allowlisted()` authenticates the dashboard without checking page
    permissions, so without an explicit gate every admin — including one holding
    zero grants — would read which components are stubbed. That is not a tidiness
    concern: "Error notification: stub" tells the holder of a low-privilege
    account that failures raise no alert.

    The pre-#368 dashboard enforced the equivalent principle for its audit
    sections, but only in a code comment — which is why removing it broke no rule
    and failed no test. This test is that missing enforcement.
    """

    def test_accounts_permission_grants_the_panel(self):
        from src._apps.admin.pages.dashboard import may_see_infrastructure

        assert may_see_infrastructure({"accounts"}) is True

    def test_zero_permission_admin_is_refused(self):
        from src._apps.admin.pages.dashboard import may_see_infrastructure

        assert may_see_infrastructure(set()) is False

    def test_domain_permissions_alone_do_not_grant_it(self):
        """A page grant is not a trust signal about infrastructure."""
        from src._apps.admin.pages.dashboard import may_see_infrastructure

        assert may_see_infrastructure({"user", "docs", "ai_usage"}) is False

    def test_audit_permission_alone_does_not_grant_it(self):
        from src._apps.admin.pages.dashboard import may_see_infrastructure

        assert may_see_infrastructure({"audit_log"}) is False

    def test_the_gate_is_a_registry_key(self):
        """A typo'd key would silently refuse everyone; the registry is the
        canonical source of valid permission keys."""
        from src._apps.admin.pages.dashboard import _INFRA_PERMISSION
        from src._core.infrastructure.admin.permission_registry import (
            AdminPermissionRegistry,
        )

        assert AdminPermissionRegistry().is_valid_key(_INFRA_PERMISSION)


class TestEveryInfraStateHasADecidedAppearance:
    """A new `InfraState` must not inherit a hue by omission (#380).

    The dashboard's infrastructure panel stopped being an AG Grid — the list-page
    builder brought `selection="single"`, which put a row-selection radio in every
    row of a panel with no row action, and spread one-word values across 488px
    columns. It is now a status list whose leading dot carries the state, mapped
    per enum member.

    `DISABLED` is deliberately absent from that map: the dot's base colour is
    already the muted token, and "not configured" is not an outcome worth a hue.
    That is a decision, so it is asserted rather than left to look like an
    oversight — and a member added later fails here until someone decides.
    """

    def test_the_map_covers_exactly_the_states_with_a_hue(self):
        from src._apps.admin.pages.dashboard import _STATE_DOT_CLASS

        assert set(_STATE_DOT_CLASS) == {InfraState.ACTIVE, InfraState.STUB}

    def test_disabled_falls_through_to_the_muted_default(self):
        from src._apps.admin.pages.dashboard import _STATE_DOT_CLASS

        assert _STATE_DOT_CLASS.get(InfraState.DISABLED, "") == ""

    def test_every_enum_member_is_accounted_for(self):
        """Mapped with a hue, or explicitly listed as intentionally unmapped."""
        from src._apps.admin.pages.dashboard import _STATE_DOT_CLASS

        deliberately_unmapped = {InfraState.DISABLED}
        unaccounted = set(InfraState) - set(_STATE_DOT_CLASS) - deliberately_unmapped
        assert not unaccounted, (
            f"{sorted(s.value for s in unaccounted)} would render with the muted "
            "default by accident. Give each a hue in _STATE_DOT_CLASS, or add it "
            "to this test's deliberately_unmapped set with a reason."
        )

    def test_the_hue_classes_exist_in_the_emitted_css(self):
        """A class name typo would silently render the muted default."""
        from src._apps.admin.pages.dashboard import _STATE_DOT_CLASS
        from src._core.infrastructure.admin.theme import build_admin_css

        css = build_admin_css()
        for state, cls in _STATE_DOT_CLASS.items():
            assert f".{AdminClasses.STATUS_DOT}.{cls}" in css, (
                f"{state.value} maps to .{cls}, which theme.py does not emit"
            )
