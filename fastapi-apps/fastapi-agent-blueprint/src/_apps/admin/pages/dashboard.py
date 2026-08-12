from nicegui import ui

from src._apps.admin.dashboard_metrics import (
    GROWTH_WINDOW_DAYS,
    AiUsageMetrics,
    DashboardMetrics,
    collect_dashboard_metrics,
)
from src._apps.admin.operational_status import InfraState, InfraStatus
from src._core.infrastructure.admin import components as c
from src._core.infrastructure.admin.auth import require_auth_allowlisted
from src._core.infrastructure.admin.base_admin_page import BaseAdminPage
from src._core.infrastructure.admin.error_handler import admin_error_boundary
from src._core.infrastructure.admin.layout import admin_layout
from src._core.infrastructure.admin.theme import AdminClasses, AdminMetrics

# page_configs is injected by bootstrap_admin() after discovery
page_configs: list[BaseAdminPage] = []

_UNAVAILABLE = "Unavailable"

# Gate for the infrastructure panel. `require_auth_allowlisted()` authenticates
# without checking page permissions, so without this every admin — including one
# holding zero grants — would read the deployment's configuration posture. That
# matters beyond tidiness: "Error notification: stub" tells the holder of a
# low-privilege account that failures raise no alert, and "OpenTelemetry:
# disabled" that there are no traces. Both are directly useful to someone who has
# compromised such an account.
#
# `accounts` is the closest thing to a super-admin marker here — the registry
# calls it "the account-management gate", i.e. the permission to create admins and
# grant their permissions. Onboarding is unaffected because the setup wizard
# grants the first admin every key (see AdminPermissionRegistry).
#
# This is a policy choice, not a security law. A deployment that treats every
# authenticated admin as fully trusted can widen it here; the point is that the
# decision is now written down and pinned by a test rather than implicit.
_INFRA_PERMISSION = "accounts"


def may_see_infrastructure(permissions: set[str]) -> bool:
    """Whether this operator may see the infrastructure posture panel."""
    return _INFRA_PERMISSION in permissions


# What an operator can do about each stub, by infra label. Shown only on the
# onboarding view: once there is data, a stub is a deliberate choice rather than
# an unfinished setup, and repeating the hint forever would be nagging.
_NEXT_STEPS: dict[str, str] = {
    "LLM": "Set LLM_PROVIDER + LLM_MODEL to replace the TestModel stub",
    "Embedding": "Set EMBEDDING_PROVIDER + EMBEDDING_MODEL to replace StubEmbedder",
    "Error notification": (
        "Set NOTIFICATION_PROVIDER + the matching webhook URL to receive alerts"
    ),
}

# Cards would otherwise size to their own text, so a column of steps came out
# with ragged right edges that read as a layout bug rather than a choice.
_STEP_WIDTH = "max-width: 720px"

# Infrastructure list geometry. Widest values today are "disabled" and
# "inmemory"; the slots are sized for those with a little slack. The row height
# is the shared grid rhythm rather than a new number, so this list and every
# admin table read at the same density.
# The panel bounds its own width rather than trusting its container. Without it
# the onboarding view — where it is not inside the aside — stretched the list to
# the full 1620px and put each value ~1000px from its label.
_INFRA_WIDTH = "max-width: 480px"

# `q-col-gutter-md` owns the spacing between the two columns, but NiceGUI puts a
# `gap` on every `.nicegui-row` as well, and it is added on top. The columns sum
# to exactly 12/12, so that extra 16px is enough to wrap the aside underneath:
# measured at 1920px, the infrastructure column landed at y=709 instead of y=169
# beside the main column. The populated view happened to survive it only because
# a `q-gutter-md` on its main column contributed a cancelling negative margin —
# an accident, not a layout. Zeroing the gap here makes both views depend on the
# Quasar gutter alone.
_COLUMNS_GAP = "gap: 0"
_STATE_SLOT = "width: 72px"
_DETAIL_SLOT = "width: 84px"
_ROW_HEIGHT = f"min-height: {AdminMetrics.GRID_ROW_HEIGHT}px"


@ui.page("/admin/")
@admin_error_boundary(context="admin_dashboard")
async def dashboard_page():
    session = await require_auth_allowlisted()
    if session is None:
        return
    admin_layout(page_configs, current_domain="", session=session)

    permissions = set(session.permissions)
    visible_configs = [pc for pc in page_configs if pc.domain_name in permissions]

    # The facade never raises; failures degrade individual sections in place.
    # `visible_configs` is already permission-filtered, which is what keeps every
    # section below scoped to what this operator may see.
    metrics = await collect_dashboard_metrics(visible_configs)

    show_infra = may_see_infrastructure(permissions)

    if metrics.has_any_data:
        c.page_header("Dashboard", subtitle=f"Last {GROWTH_WINDOW_DAYS} days")
        # Two columns, because the horizontal space was not empty — it was badly
        # spent. Measured at 1920px before this: the growth chart was a 1588px
        # plot holding one bar, and the infrastructure table gave 488px each to
        # `active` and `sqlite`, while the stat tiles sat in a 294px huddle to
        # their left (#380). Stacking those full-width sections is what made the
        # page 1186px tall with a mostly-unused right half.
        #
        # Quasar's own column classes rather than new tokens: `col-md-8` /
        # `col-md-4` also collapses to one column below `md`, which a fixed-width
        # aside would not.
        with (
            ui.row()
            .classes("full-width q-col-gutter-md items-start")
            .style(_COLUMNS_GAP)
        ):
            with ui.column().classes("col-12 col-md-8 q-gutter-md"):
                _render_stat_cards(metrics)
                _render_ai_usage(metrics.ai_usage)
                _render_growth(metrics)
            if show_infra:
                with ui.column().classes("col-12 col-md-4"):
                    _render_infrastructure(metrics.infra)
    else:
        # Every count is 0 on a fresh install, which is what every OSS adopter
        # opens first. Charting zeros there looks broken; naming the next action
        # does not (#368).
        _render_onboarding(metrics, show_infra=show_infra)


# ── Populated view ──


def _render_stat_cards(metrics: DashboardMetrics) -> None:
    with ui.row().classes("q-gutter-md q-mb-md"):
        for dc in metrics.domain_counts:
            value = dc.count if dc.count is not None else _UNAVAILABLE
            c.stat_card(dc.display_name, value, icon=dc.icon)


def _render_ai_usage(usage: AiUsageMetrics) -> None:
    """Agent-call volume and failure rate — the distinctive signal for this stack.

    Omitted entirely when no domain exposes a usage summary: an empty panel would
    imply the capability exists and is broken.
    """
    if not usage.available:
        return
    with c.section(f"Agent Calls ({GROWTH_WINDOW_DAYS}d)"):
        if not usage.calls:
            # A row of four zeros is the "looks broken" shape this rework set out
            # to remove. One line still answers the question — and it is a real
            # answer, unlike a hidden panel, which would be indistinguishable
            # from the domain being absent.
            #
            # A muted label, not `c.empty_state`: that builder is a whole-page
            # placeholder (48px vertical padding, centred) and using it for an
            # inline note spent ~250px on one sentence.
            ui.label(f"No agent calls in the last {GROWTH_WINDOW_DAYS} days").classes(
                AdminClasses.MUTED
            )
            return
        # The three counters are set together by the facade — all int, or all
        # None when the read failed. Narrowing them here enforces that at the
        # boundary rather than assuming it: `or 0` would collapse "no data" into
        # "zero", which is exactly the distinction the facade keeps.
        calls, failures, tokens = usage.calls, usage.failures, usage.total_tokens
        if failures is None or tokens is None:
            ui.label("Agent usage unavailable").classes(AdminClasses.MUTED)
            return

        with ui.row().classes("q-gutter-md"):
            c.stat_card("Calls", calls, icon="smart_toy")
            c.stat_card("Failures", failures, icon="error")
            rate = usage.failure_rate
            c.stat_card(
                "Failure rate",
                f"{rate:.1%}" if rate is not None else "—",
                icon="percent",
            )
            c.stat_card("Tokens", tokens, icon="toll")


def _render_growth(metrics: DashboardMetrics) -> None:
    """One aggregate chart of new records per day across all visible domains.

    Deliberately *not* one chart per domain. That was the first shape and it
    reproduced the defect #369 had just fixed: each chart is a fixed 260px, so
    two domains pushed the page past 1700px with two nearly-empty plots. The
    per-domain totals are already on the stat cards; the chart's job is the shape
    over time.
    """
    points = metrics.growth_by_day
    if points:
        with c.section(f"New Records ({GROWTH_WINDOW_DAYS}d)"):
            c.bar_chart(
                [p.day.strftime("%m-%d") for p in points],
                [p.count for p in points],
            )

    unavailable = [g.display_name for g in metrics.growth if not g.available]
    if unavailable:
        # Named rather than silently dropped: a missing domain in an aggregate is
        # invisible, and "the trend excludes X" is the actionable part.
        ui.label(f"Trend unavailable: {', '.join(unavailable)}").classes(
            AdminClasses.MUTED
        )


# Which state gets which hue. Keyed off the enum rather than its `.value` so a
# renamed value cannot silently fall through to the muted default.
_STATE_DOT_CLASS: dict[InfraState, str] = {
    InfraState.ACTIVE: "admin-status-active",
    InfraState.STUB: "admin-status-stub",
    # DISABLED deliberately absent: the dot's base colour is already the muted
    # token, and "not configured" is not an outcome worth a hue.
}


def _render_infrastructure(infra: list[InfraStatus]) -> None:
    """A status list, not an AG Grid.

    This was `c.data_grid`, the builder the list pages use, and it brought their
    assumptions with it: `selection="single"` put a **row-selection radio in every
    row** — 122px of clickable control on a panel with no row action, so clicking
    one did nothing — and three columns spread one-word values across 488px each.
    A 10-row list of `label / state / detail` needs none of that; the widest cell
    here is "OpenTelemetry".

    Built inline rather than as a `components/` builder: `admin-design-system.md`
    requires a second real call site first, and there is one panel like this.
    """
    with c.section("Infrastructure") as panel:
        panel.style(_INFRA_WIDTH)
        # No gutter on the container: each row sets its own height from the house
        # grid rhythm, so the list matches the density of every other admin table
        # instead of inheriting the section's inter-block spacing (which put the
        # ten rows 48px apart, airier than anything else on the page).
        with ui.column().classes("full-width q-gutter-none"):
            for row in infra:
                with (
                    ui.row()
                    .classes("items-center no-wrap full-width q-gutter-sm")
                    .style(_ROW_HEIGHT)
                ):
                    dot = _STATE_DOT_CLASS.get(row.state, "")
                    ui.element("span").classes(
                        f"{AdminClasses.STATUS_DOT} {dot}".strip()
                    )
                    ui.label(row.label).classes("col")
                    # Both trailing values live in fixed, right-aligned slots.
                    # Sized by content they did not line up: with `detail` present
                    # on 3 of 10 rows, `state` floated left on those rows and sat
                    # at the edge on the rest, so no column had an edge. The empty
                    # slot below is what keeps the state column straight.
                    ui.label(row.state.value).classes(
                        f"{AdminClasses.MUTED} text-right"
                    ).style(_STATE_SLOT)
                    ui.label(row.detail or "").classes(
                        f"{AdminClasses.FIELD_VALUE} text-right"
                    ).style(_DETAIL_SLOT)


# ── Onboarding view (no data yet) ──


def _render_onboarding(metrics: DashboardMetrics, *, show_infra: bool) -> None:
    c.page_header(
        "Welcome",
        subtitle="No records yet — here is what is wired up and what to do next",
    )

    stubs = [row for row in metrics.infra if row.state is InfraState.STUB]
    active = [row for row in metrics.infra if row.state is InfraState.ACTIVE]

    # Two columns here too. This is the screen every new adopter opens first, and
    # it had the same unused right half as the populated view (#380).
    with ui.row().classes("full-width q-col-gutter-md items-start").style(_COLUMNS_GAP):
        with ui.column().classes("col-12 col-md-8"):
            _render_next_steps(stubs, show_infra=show_infra)
        if show_infra:
            with ui.column().classes("col-12 col-md-4"):
                _render_infrastructure(metrics.infra)
                if active and not stubs:
                    ui.label("Every optional component is configured.").classes(
                        f"{AdminClasses.MUTED} q-mt-md"
                    )


def _render_next_steps(stubs: list[InfraStatus], *, show_infra: bool) -> None:
    with c.section("Next steps"):
        with ui.column().classes("q-gutter-md").style(_STEP_WIDTH):
            # Seeding data first: it is the step that turns this view into the
            # real dashboard, and it needs no credentials.
            _step(
                "play_circle",
                "Create some records",
                "Run make demo for CRUD, or make demo-rag for the RAG walkthrough.",
            )
            # The stub hints disclose the same posture as the panel below — "LLM
            # is running a stub" is the panel's LLM row in prose — so they sit
            # behind the same gate rather than leaking around it.
            if show_infra:
                for row in stubs:
                    hint = _NEXT_STEPS.get(row.label)
                    if hint:
                        _step("build", f"{row.label} is running a stub", hint)


def _step(icon: str, title: str, detail: str) -> None:
    with c.card(classes="full-width"):
        with ui.row().classes("items-center no-wrap q-gutter-md"):
            ui.icon(icon).classes(f"text-h5 {AdminClasses.ACCENT_ICON}")
            with ui.column().classes("q-gutter-none"):
                ui.label(title).classes("text-subtitle2")
                ui.label(detail).classes(f"text-caption {AdminClasses.MUTED}")
