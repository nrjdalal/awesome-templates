from nicegui import app, ui

from src._core.config import settings
from src._core.infrastructure.admin import components as c
from src._core.infrastructure.admin.audit import (
    AdminAction,
    AuditResult,
    safe_user_snapshot,
)
from src._core.infrastructure.admin.audit.logger import get_audit_logger
from src._core.infrastructure.admin.auth import (
    AdminAuthProvider,
    get_admin_account_use_case,
)
from src._core.infrastructure.admin.error_handler import (
    AdminErrorHandler,
    admin_error_boundary,
)
from src._core.infrastructure.admin.layout import button_loading
from src._core.infrastructure.admin.theme import AdminClasses
from src.admin_identity.domain.exceptions.admin_identity_exceptions import (
    AdminSetupForbiddenException,
)


@ui.page("/admin/setup")
@admin_error_boundary(context="admin_setup")
async def setup_page():
    """One-time first-admin setup wizard.

    Only accessible after authenticating with bootstrap credentials when no
    real admin exists.  A session flag 'setup_granted' is set by login.py
    upon AdminSetupRequiredException; this page checks that flag and also
    re-verifies server-side that setup is still needed.
    """
    if not app.storage.user.get("setup_granted"):
        ui.navigate.to("/admin/login")
        return

    with ui.card().classes("absolute-center w-96"):
        ui.label("Initial Admin Setup").classes("text-h5 q-mb-md")
        ui.label("Create the first administrator account.").classes(
            f"text-subtitle2 q-mb-md {AdminClasses.MUTED}"
        )

        username_input = c.text_field("Username").classes("full-width")
        full_name_input = c.text_field("Full Name").classes("full-width")
        email_input = c.text_field("Email").classes("full-width")

        result_card = ui.card().classes(
            f"w-full q-mt-md {AdminClasses.SUCCESS_SURFACE}"
        )
        result_card.set_visibility(False)

        async def create_first_admin():
            username = username_input.value.strip()
            full_name = full_name_input.value.strip()
            email = email_input.value.strip()
            if not (username and full_name and email):
                ui.notify("All fields are required", type="warning")
                return

            setup_already_complete = False
            async with button_loading(create_btn):
                try:
                    (
                        new_admin,
                        temp_password,
                    ) = await get_admin_account_use_case().create_first_admin(
                        username=username,
                        full_name=full_name,
                        email=email,
                        bootstrap_username=settings.admin_bootstrap_username,
                    )
                except AdminSetupForbiddenException as exc:
                    setup_already_complete = True
                    await get_audit_logger().log(
                        action=AdminAction.FIRST_ADMIN_CREATE,
                        domain="auth",
                        result=AuditResult.FAILURE,
                        admin_username=username,
                        failure_reason=exc.error_code,
                    )
                except Exception as exc:  # noqa: BLE001 - delegated to handler
                    # Includes UserAlreadyExistsException (4xx) → AdminErrorHandler
                    # surfaces exc.message as a warning and logs with context.
                    await get_audit_logger().log(
                        action=AdminAction.FIRST_ADMIN_CREATE,
                        domain="auth",
                        result=AuditResult.FAILURE,
                        admin_username=username,
                        failure_reason=getattr(exc, "error_code", None)
                        or type(exc).__name__,
                    )
                    await AdminErrorHandler.handle(exc, context="admin_setup_create")
                    return
            # Navigate only after loading state is cleared (button not yet torn down).
            if setup_already_complete:
                ui.notify("Setup is already complete. Please log in.", type="warning")
                ui.navigate.to("/admin/login")
                return

            await get_audit_logger().log(
                action=AdminAction.FIRST_ADMIN_CREATE,
                domain="auth",
                result=AuditResult.SUCCESS,
                admin_user_id=new_admin.id,
                admin_username=new_admin.username,
                record_id=str(new_admin.id),
                after_state=safe_user_snapshot(new_admin),
            )

            # Clear bootstrap session flag; user must log in as the new admin.
            AdminAuthProvider.logout()
            app.storage.user.pop("setup_granted", None)

            result_card.clear()
            result_card.set_visibility(True)
            with result_card:
                ui.label("Account created!").classes(
                    "text-weight-bold text-positive q-mb-sm"
                )
                ui.label(f"Username: {new_admin.username}")
                ui.separator().classes("q-my-sm")
                ui.label("Temporary password (copy now — shown once):").classes(
                    f"text-caption {AdminClasses.MUTED}"
                )
                ui.label(temp_password).classes(
                    "text-mono text-weight-bold text-body1 q-mt-xs"
                )
                ui.button(
                    "Copy password",
                    on_click=lambda: ui.run_javascript(
                        f"navigator.clipboard.writeText('{temp_password}')"
                    ),
                ).props("flat size=sm color=primary").classes("q-mt-sm")
                ui.separator().classes("q-my-sm")
                ui.label("You will be redirected to login in 8 seconds.").classes(
                    f"text-caption {AdminClasses.MUTED}"
                )
                ui.timer(8.0, lambda: ui.navigate.to("/admin/login"), once=True)

        create_btn = (
            ui.button("Create Admin Account", on_click=create_first_admin)
            .classes("q-mt-md full-width")
            .props("color=primary")
        )
