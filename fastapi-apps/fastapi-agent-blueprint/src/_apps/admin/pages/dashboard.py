from nicegui import ui

from src._apps.admin.dashboard_metrics import (
    DashboardMetrics,
    collect_dashboard_metrics,
)
from src._core.infrastructure.admin import components as c
from src._core.infrastructure.admin.auth import require_auth_allowlisted
from src._core.infrastructure.admin.base_admin_page import BaseAdminPage
from src._core.infrastructure.admin.error_handler import admin_error_boundary
from src._core.infrastructure.admin.layout import admin_layout

# page_configs is injected by bootstrap_admin() after discovery
page_configs: list[BaseAdminPage] = []

# Audit-derived sections (event totals, activity chart, recent table) are only
# rendered for operators holding the audit_log permission — the landing page
# must not surface audit data more broadly than the dedicated audit-log page.
_AUDIT_PERMISSION = "audit_log"

_UNAVAILABLE = "Unavailable"


@ui.page("/admin/")
@admin_error_boundary(context="admin_dashboard")
async def dashboard_page():
    session = await require_auth_allowlisted()
    if session is None:
        return
    admin_layout(page_configs, current_domain="", session=session)
    c.page_header("Dashboard", subtitle="Welcome to the Admin Dashboard")

    permissions = set(session.permissions)
    visible_configs = [pc for pc in page_configs if pc.domain_name in permissions]
    show_audit = _AUDIT_PERMISSION in permissions

    # The facade never raises; failures degrade individual sections in place.
    # Audit reads are gated on the permission so unauthorized operators never
    # cause audit data to be read server-side.
    metrics = await collect_dashboard_metrics(visible_configs, include_audit=show_audit)

    _render_stat_cards(metrics, show_audit=show_audit)
    if show_audit:
        _render_activity_chart(metrics)
        _render_recent_activity(metrics)
    _render_quick_actions(visible_configs, permissions)


def _render_stat_cards(metrics: DashboardMetrics, *, show_audit: bool) -> None:
    with ui.row().classes("q-gutter-md q-mb-md"):
        for dc in metrics.domain_counts:
            value = dc.count if dc.count is not None else _UNAVAILABLE
            c.stat_card(dc.display_name, value, icon=dc.icon)
        if show_audit:
            # Always render the card when permitted; a backend failure shows
            # "Unavailable" rather than silently dropping the card, so the
            # operator can tell "no permission" apart from "audit down".
            total = metrics.audit.total
            c.stat_card(
                "Audit Events",
                total if total is not None else _UNAVAILABLE,
                icon="fact_check",
            )
            if metrics.audit.failures:
                c.stat_card("Recent Failures", metrics.audit.failures, icon="error")


def _render_activity_chart(metrics: DashboardMetrics) -> None:
    by_action = metrics.audit.by_action
    if not metrics.audit.available or not by_action:
        return  # unavailable or empty window: omit the chart rather than show a blank axis
    actions = list(by_action.keys())
    counts = [by_action[a] for a in actions]
    with c.section("Recent Activity by Action"):
        c.bar_chart(actions, counts)


def _render_recent_activity(metrics: DashboardMetrics) -> None:
    with c.section("Recent Activity"):
        if not metrics.audit.available:
            with c.empty_state("cloud_off"):
                ui.label("Audit data unavailable")
            return
        recent = metrics.audit.recent or []
        if not recent:
            with c.empty_state("inbox"):
                ui.label("No recent activity")
            return
        rows = [
            {
                "time": row.created_at.strftime("%Y-%m-%d %H:%M"),
                "action": row.action.value,
                "result": row.result.value,
                "user": row.admin_username,
                "domain": row.domain,
            }
            for row in recent
        ]
        c.data_grid(
            [
                {"headerName": "Time", "field": "time"},
                {"headerName": "Action", "field": "action"},
                {"headerName": "Result", "field": "result"},
                {"headerName": "User", "field": "user"},
                {"headerName": "Domain", "field": "domain"},
            ],
            rows,
            compact=True,
        )


def _render_quick_actions(
    visible_configs: list[BaseAdminPage], permissions: set[str]
) -> None:
    def _nav_card(icon: str, label: str, target: str) -> None:
        with c.card(clickable_to=target):
            with ui.row().classes("items-center q-pa-sm"):
                ui.icon(icon).classes("text-h4 text-primary")
                ui.label(label).classes("text-h6")

    with c.section("Quick Actions"):
        with ui.row().classes("q-gutter-md"):
            for pc in visible_configs:
                _nav_card(pc.icon, pc.display_name, f"/admin/{pc.domain_name}")
            if "accounts" in permissions:
                _nav_card("manage_accounts", "Accounts", "/admin/accounts")
            if _AUDIT_PERMISSION in permissions:
                _nav_card("fact_check", "Audit Log", "/admin/audit-log")
