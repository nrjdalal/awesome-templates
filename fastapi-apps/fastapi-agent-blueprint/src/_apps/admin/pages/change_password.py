from nicegui import ui

from src._core.infrastructure.admin.auth import (
    AdminAuthProvider,
    get_admin_account_use_case,
    require_auth_allowlisted,
)
from src._core.infrastructure.admin.base_admin_page import BaseAdminPage
from src._core.infrastructure.admin.layout import admin_layout
from src.auth.domain.exceptions.auth_exceptions import InvalidCredentialsException

# page_configs is injected by bootstrap_admin() after discovery
page_configs: list[BaseAdminPage] = []


@ui.page("/admin/change-password")
async def change_password_page():
    """Forced or voluntary password change for the current admin."""
    session = await require_auth_allowlisted()
    if session is None:
        return

    is_forced = session.password_temporary

    admin_layout(page_configs, current_domain="", session=session)

    with ui.card().classes("w-96 q-mx-auto q-mt-xl"):
        if is_forced:
            ui.label("Password Change Required").classes("text-h5 q-mb-sm")
            ui.label("You must set a new password before continuing.").classes(
                "text-caption text-warning q-mb-md"
            )
        else:
            ui.label("Change Password").classes("text-h5 q-mb-md")

        current_pw = ui.input(
            "Current password", password=True, password_toggle_button=True
        ).classes("full-width")
        new_pw = ui.input(
            "New password (min 8 chars)", password=True, password_toggle_button=True
        ).classes("full-width")
        confirm_pw = ui.input(
            "Confirm new password", password=True, password_toggle_button=True
        ).classes("full-width")

        async def do_change():
            if len(new_pw.value) < 8:
                ui.notify("New password must be at least 8 characters", type="warning")
                return
            if new_pw.value != confirm_pw.value:
                ui.notify("Passwords do not match", type="warning")
                return

            try:
                await get_admin_account_use_case().change_password(
                    user_id=session.user_id,
                    current_password=current_pw.value,
                    new_password=new_pw.value,
                )
            except InvalidCredentialsException:
                ui.notify("Current password is incorrect", type="negative")
                return
            except Exception as exc:
                ui.notify(f"Error: {exc}", type="negative")
                return

            ui.notify("Password changed successfully", type="positive")
            AdminAuthProvider.logout()
            ui.navigate.to("/admin/login")

        ui.button("Change Password", on_click=do_change).classes(
            "q-mt-md full-width"
        ).props("color=primary")

        if not is_forced:
            ui.button("Cancel", on_click=lambda: ui.navigate.to("/admin/")).classes(
                "full-width"
            ).props("flat")
