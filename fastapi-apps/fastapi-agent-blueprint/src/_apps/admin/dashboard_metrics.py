"""What the admin landing page reads (#193, reworked in #368).

A façade that **never raises**: every source is isolated so one failing backend
degrades its own section instead of 500-ing the page. Sources that are absent
report ``None``, which the page renders as "Unavailable" — distinguishable from a
real zero, because "the count is 0" and "the count could not be read" are
different facts and collapsing them hides outages.

What the dashboard answers, and what it stopped answering
---------------------------------------------------------
#368 replaced the questions. The page now reports **what is wired up**, **AI
usage and its failure rate**, and **per-domain growth**. The audit-derived
sections it used to carry (an activity chart and a recent-activity table) are
gone, and so is the collection behind them: ``/admin/audit-log`` is a strict
superset with filtering and pagination, so the landing page was reading audit
data to show a worse version of a page that already existed. Not rendering it is
also one fewer audit read per dashboard load.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date, datetime, timedelta

import structlog

from src._apps.admin.operational_status import InfraStatus, collect_operational_status
from src._core.domain.value_objects.daily_count import DailyCount
from src._core.infrastructure.admin.base_admin_page import BaseAdminPage

_logger = structlog.stdlib.get_logger(__name__)

# Fixed window. An operator-selectable range needs a control plus somewhere to
# keep the selection, which is deferred rather than smuggled in here (#368).
GROWTH_WINDOW_DAYS = 7

# The one status that counts as success. Failures are derived by subtraction
# rather than by summing the known failure states — see _collect_ai_usage.
_OK_STATUS = "ok"


@dataclass(frozen=True)
class DomainCount:
    """Per-domain record count for a stat card. ``count is None`` => unavailable."""

    domain_name: str
    display_name: str
    icon: str
    count: int | None


@dataclass(frozen=True)
class DomainGrowth:
    """Per-domain daily counts over the window. ``points is None`` => unavailable.

    Empty-but-not-None means the window genuinely holds no rows, which is the
    normal state of a fresh install and must not read as a failure.
    """

    domain_name: str
    display_name: str
    points: list[DailyCount] | None

    @property
    def available(self) -> bool:
        return self.points is not None

    @property
    def total(self) -> int:
        return sum(p.count for p in self.points or [])


@dataclass(frozen=True)
class AiUsageMetrics:
    """Agent-call volume and failure rate over the window.

    ``calls is None`` => no domain exposed a usage summary, or the read failed.
    """

    calls: int | None
    failures: int | None
    total_tokens: int | None

    @property
    def available(self) -> bool:
        return self.calls is not None

    @property
    def failure_rate(self) -> float | None:
        """Fraction of calls that did not succeed, or ``None`` when unknowable.

        ``None`` for zero calls rather than ``0.0``: a rate needs a denominator,
        and reporting a healthy 0% for a system that has served nothing is a
        false reassurance.
        """
        if self.calls is None or self.failures is None or self.calls == 0:
            return None
        return self.failures / self.calls


@dataclass(frozen=True)
class DashboardMetrics:
    """Everything the landing page renders. Always fully populated (no raises)."""

    infra: list[InfraStatus]
    domain_counts: list[DomainCount]
    growth: list[DomainGrowth]
    ai_usage: AiUsageMetrics

    @property
    def growth_by_day(self) -> list[DailyCount]:
        """New records per day summed across every visible domain, oldest first.

        One aggregate series rather than one chart per domain. Charting each
        domain separately reproduced the defect #369 had just removed: N fixed
        height charts, each mostly empty, pushing the page past 1700px. The
        per-domain totals are already on the stat cards above; what the chart
        adds is the shape over time, and that reads better as a single line.

        Domains whose read failed contribute nothing rather than zero — see
        ``DomainGrowth.available``.
        """
        totals: dict[date, int] = {}
        for domain in self.growth:
            for point in domain.points or []:
                totals[point.day] = totals.get(point.day, 0) + point.count
        return [DailyCount(day=day, count=totals[day]) for day in sorted(totals)]

    @property
    def has_any_data(self) -> bool:
        """Whether anything worth charting exists yet.

        Drives the onboarding screen. Deliberately ignores ``infra``: a fresh
        install always has infrastructure to report, so counting it would mean
        the onboarding view never appears — which is the state every OSS adopter
        opens first. Unavailable sources (``None``) do not count as data either;
        a broken backend is not evidence of records.
        """
        if any(dc.count for dc in self.domain_counts):
            return True
        return bool(self.ai_usage.calls)


def window_start(now: datetime | None = None) -> datetime:
    """Lower bound for the growth/usage window.

    Naive on purpose: every timestamp column in-tree is naive ``DateTime``, and
    ``BaseRepository.count_datas_by_day`` deliberately does not coerce. ``now`` is
    injectable so tests do not depend on the wall clock.
    """
    base = now or datetime.now()
    return base - timedelta(days=GROWTH_WINDOW_DAYS)


async def _count_for(config: BaseAdminPage) -> DomainCount:
    """Best-effort record count for one domain; ``count=None`` on any failure."""
    count: int | None
    try:
        service = config._get_service()
        # count_datas lives on BaseService but not on AdminCrudServiceProtocol
        # (that contract is scoped to what BaseAdminPage itself uses); probe it
        # dynamically here so the shared CRUD protocol stays minimal and is not
        # coupled to this dashboard-only need.
        count_datas = getattr(service, "count_datas", None)
        if count_datas is None:
            raise AttributeError("service does not implement count_datas")
        count = await count_datas()
    except Exception as exc:  # noqa: BLE001 - per-card isolation, swallowed by design
        _logger.warning(
            "dashboard_count_failed",
            domain=config.domain_name,
            error_type=type(exc).__name__,
        )
        count = None
    return DomainCount(
        domain_name=config.domain_name,
        display_name=config.display_name,
        icon=config.icon,
        count=count,
    )


async def _growth_for(config: BaseAdminPage, since: datetime) -> DomainGrowth:
    """Best-effort daily counts for one domain; ``points=None`` on any failure.

    Probed dynamically for the same reason as ``count_datas``: a domain whose
    model has no temporal column raises a curated 400 from the repository, and a
    domain that predates this method simply does not have it. Neither should cost
    the operator their whole dashboard.
    """
    points: list[DailyCount] | None
    try:
        service = config._get_service()
        by_day = getattr(service, "count_datas_by_day", None)
        if by_day is None:
            raise AttributeError("service does not implement count_datas_by_day")
        points = await by_day(since=since)
    except Exception as exc:  # noqa: BLE001 - per-section isolation, by design
        _logger.warning(
            "dashboard_growth_failed",
            domain=config.domain_name,
            error_type=type(exc).__name__,
        )
        points = None
    return DomainGrowth(
        domain_name=config.domain_name,
        display_name=config.display_name,
        points=points,
    )


async def _collect_ai_usage(
    configs: list[BaseAdminPage], since: datetime
) -> AiUsageMetrics:
    """Agent-call volume and failures from whichever domain exposes a summary.

    Capability-probed rather than importing ``AiUsageService``: a fork that drops
    the domain should lose the panel, not the page. The domain must be in
    ``configs``, so an operator without its permission never causes the read.

    Failures are ``total - ok`` rather than a sum over the known failure states.
    ``UsageStatus`` is ``Literal["ok", "error", "timeout", "rate_limited"]``, and
    summing three of them means a fourth state added later is silently counted as
    success. Subtracting from the total cannot drift that way.
    """
    for config in configs:
        try:
            service = config._get_service()
        except Exception as exc:  # noqa: BLE001 - isolated probe
            _logger.warning(
                "dashboard_ai_usage_service_failed",
                domain=config.domain_name,
                error_type=type(exc).__name__,
            )
            continue
        get_summary = getattr(service, "get_usage_summary", None)
        if get_summary is None:
            continue
        try:
            overall, _ = await get_summary(start_at=since)
            ok, _ = await get_summary(start_at=since, status=_OK_STATUS)
        except Exception as exc:  # noqa: BLE001 - degrade this panel only
            _logger.warning(
                "dashboard_ai_usage_failed",
                domain=config.domain_name,
                error_type=type(exc).__name__,
            )
            return AiUsageMetrics(calls=None, failures=None, total_tokens=None)
        return AiUsageMetrics(
            calls=overall.call_count,
            failures=max(overall.call_count - ok.call_count, 0),
            total_tokens=overall.total_tokens,
        )
    return AiUsageMetrics(calls=None, failures=None, total_tokens=None)


async def collect_dashboard_metrics(
    visible_configs: list[BaseAdminPage],
    *,
    now: datetime | None = None,
) -> DashboardMetrics:
    """Gather all landing-page metrics concurrently, isolating per-source failures.

    ``visible_configs`` must already be permission-filtered by the caller — this
    facade does not enforce authorization, it only reads what it is handed. That
    filtering is also what keeps the AI panel and the growth section scoped: a
    domain the operator may not see is not in the list, so it is never read.

    Infrastructure status is not gathered concurrently because it touches no I/O;
    it is a read over ``settings``.
    """
    since = window_start(now)
    counts, growth, ai_usage = await asyncio.gather(
        asyncio.gather(*(_count_for(cfg) for cfg in visible_configs)),
        asyncio.gather(*(_growth_for(cfg, since) for cfg in visible_configs)),
        _collect_ai_usage(list(visible_configs), since),
    )
    return DashboardMetrics(
        infra=collect_operational_status(),
        domain_counts=list(counts),
        growth=list(growth),
        ai_usage=ai_usage,
    )
