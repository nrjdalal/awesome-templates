from nicegui import ui

from src._core.infrastructure.admin.auth import require_auth
from src._core.infrastructure.admin.base_admin_page import BaseAdminPage
from src._core.infrastructure.admin.layout import admin_layout

# page_configs is injected by bootstrap_admin() after discovery
page_configs: list[BaseAdminPage] = []


@ui.page("/admin/")
async def dashboard_page():
    if not await require_auth():
        return
    admin_layout(page_configs, current_domain="")
    ui.label("Dashboard").classes("text-h4 q-mb-lg")
    ui.label("Welcome to the Admin Dashboard").classes("text-subtitle1 q-mb-lg")

    with ui.row().classes("q-gutter-md"):
        for pc in page_configs:
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
