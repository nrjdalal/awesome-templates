from nicegui import ui

from src._core.infrastructure.admin.auth import require_auth_allowlisted
from src._core.infrastructure.admin.base_admin_page import BaseAdminPage
from src._core.infrastructure.admin.error_handler import admin_error_boundary
from src._core.infrastructure.admin.layout import admin_layout

# page_configs is injected by bootstrap_admin() after discovery
page_configs: list[BaseAdminPage] = []


@ui.page("/admin/")
@admin_error_boundary(context="admin_dashboard")
async def dashboard_page():
    session = await require_auth_allowlisted()
    if session is None:
        return
    admin_layout(page_configs, current_domain="", session=session)
    ui.label("Dashboard").classes("text-h4 q-mb-lg")
    ui.label("Welcome to the Admin Dashboard").classes("text-subtitle1 q-mb-lg")

    permissions = set(session.permissions)
    visible_configs = [pc for pc in page_configs if pc.domain_name in permissions]

    with ui.row().classes("q-gutter-md"):
        for pc in visible_configs:
            with (
                ui.card()
                .classes("cursor-pointer")
                .on(
                    "click",
                    lambda p=pc: ui.navigate.to(f"/admin/{p.domain_name}"),
                )
            ):
                with ui.row().classes("items-center q-pa-sm"):
                    ui.icon(pc.icon).classes("text-h4 text-blue-800")
                    ui.label(pc.display_name).classes("text-h6")

        if "accounts" in permissions:
            with (
                ui.card()
                .classes("cursor-pointer")
                .on("click", lambda: ui.navigate.to("/admin/accounts"))
            ):
                with ui.row().classes("items-center q-pa-sm"):
                    ui.icon("manage_accounts").classes("text-h4 text-blue-800")
                    ui.label("Accounts").classes("text-h6")

        if "audit_log" in permissions:
            with (
                ui.card()
                .classes("cursor-pointer")
                .on("click", lambda: ui.navigate.to("/admin/audit-log"))
            ):
                with ui.row().classes("items-center q-pa-sm"):
                    ui.icon("fact_check").classes("text-h4 text-blue-800")
                    ui.label("Audit Log").classes("text-h6")
