from __future__ import annotations

from typing import TYPE_CHECKING

from nicegui import ui

from src._core.infrastructure.admin.auth import AdminAuthProvider

if TYPE_CHECKING:
    from src._core.infrastructure.admin.base_admin_page import BaseAdminPage


def admin_layout(
    page_configs: list[BaseAdminPage],
    current_domain: str = "",
) -> None:
    """Render the shared admin shell: header + left drawer navigation."""
    with ui.header(elevated=True).classes("items-center justify-between bg-blue-800"):
        ui.label("Admin Dashboard").classes("text-h6 text-white")
        with ui.row().classes("items-center"):
            username = app_username()
            if username:
                ui.label(username).classes("text-white text-caption q-mr-sm")
            ui.button(
                icon="logout",
                on_click=_handle_logout,
            ).props("flat color=white")

    with ui.left_drawer(top_corner=True, bottom_corner=True).classes("bg-blue-50"):
        ui.label("Navigation").classes("text-subtitle1 q-mb-md q-ml-sm")

        with ui.item(on_click=lambda: ui.navigate.to("/admin/")):
            with ui.item_section().props("avatar"):
                ui.icon("dashboard")
            with ui.item_section():
                ui.label("Dashboard")

        ui.separator()

        for page_config in page_configs:
            _is_active = page_config.domain_name == current_domain
            with ui.item(
                on_click=lambda p=page_config: ui.navigate.to(
                    f"/admin/{p.domain_name}"
                ),
            ):
                with ui.item_section().props("avatar"):
                    ui.icon(page_config.icon).classes(
                        "text-blue-800" if _is_active else ""
                    )
                with ui.item_section():
                    _label = ui.label(page_config.display_name)
                    if _is_active:
                        _label.classes("text-weight-bold text-blue-800")


def app_username() -> str | None:
    from nicegui import app

    return app.storage.user.get("username")


def _handle_logout() -> None:
    AdminAuthProvider.logout()
    ui.navigate.to("/admin/login")
