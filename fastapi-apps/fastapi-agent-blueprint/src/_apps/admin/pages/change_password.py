from nicegui import ui

from src._core.infrastructure.admin import components as c
from src._core.infrastructure.admin.audit import AdminAction, AuditResult
from src._core.infrastructure.admin.audit.logger import get_audit_logger
from src._core.infrastructure.admin.auth import (
    AdminAuthProvider,
    get_admin_account_use_case,
    require_auth_allowlisted,
)
from src._core.infrastructure.admin.base_admin_page import BaseAdminPage
from src._core.infrastructure.admin.error_handler import (
    AdminErrorHandler,
    admin_error_boundary,
)
from src._core.infrastructure.admin.layout import admin_layout, button_loading
from src.admin_identity.domain.exceptions.admin_identity_exceptions import (
    AdminInvalidCredentialsException,
)

# page_configs is injected by bootstrap_admin() after discovery
page_configs: list[BaseAdminPage] = []


@ui.page("/admin/change-password")
@admin_error_boundary(context="admin_change_password")
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

        current_pw = c.text_field("Current password", password=True).classes(
            "full-width"
        )
        new_pw = c.text_field("New password (min 8 chars)", password=True).classes(
            "full-width"
        )
        confirm_pw = c.text_field("Confirm new password", password=True).classes(
            "full-width"
        )

        async def do_change():
            # Widget values are `str | None`; read them once, coerced.
            current_value = current_pw.value or ""
            new_value = new_pw.value or ""
            confirm_value = confirm_pw.value or ""
            if len(new_value) < 8:
                ui.notify("New password must be at least 8 characters", type="warning")
                return
            if new_value != confirm_value:
                ui.notify("Passwords do not match", type="warning")
                return

            async with button_loading(change_btn):
                try:
                    await get_admin_account_use_case().change_password(
                        admin_id=session.user_id,
                        current_password=current_value,
                        new_password=new_value,
                    )
                except AdminInvalidCredentialsException as exc:
                    await get_audit_logger().log(
                        action=AdminAction.PASSWORD_CHANGE,
                        domain="auth",
                        result=AuditResult.FAILURE,
                        record_id=str(session.user_id),
                        failure_reason=exc.error_code,
                    )
                    ui.notify("Current password is incorrect", type="negative")
                    return
                except Exception as exc:  # noqa: BLE001 - delegated to handler
                    await get_audit_logger().log(
                        action=AdminAction.PASSWORD_CHANGE,
                        domain="auth",
                        result=AuditResult.FAILURE,
                        record_id=str(session.user_id),
                        failure_reason=getattr(exc, "error_code", None)
                        or type(exc).__name__,
                    )
                    await AdminErrorHandler.handle(exc, context="admin_change_password")
                    return

            await get_audit_logger().log(
                action=AdminAction.PASSWORD_CHANGE,
                domain="auth",
                result=AuditResult.SUCCESS,
                record_id=str(session.user_id),
            )
            ui.notify("Password changed successfully", type="positive")
            AdminAuthProvider.logout()
            ui.navigate.to("/admin/login")

        change_btn = (
            ui.button("Change Password", on_click=do_change)
            .classes("q-mt-md full-width")
            .props("color=primary")
        )

        if not is_forced:
            ui.button("Cancel", on_click=lambda: ui.navigate.to("/admin/")).classes(
                "full-width"
            ).props("flat")
