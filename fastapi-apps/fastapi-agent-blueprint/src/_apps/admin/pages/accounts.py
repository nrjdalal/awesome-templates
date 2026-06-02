from nicegui import ui

from src._core.infrastructure.admin import components as c
from src._core.infrastructure.admin.audit import (
    AdminAction,
    AuditResult,
    safe_user_snapshot,
)
from src._core.infrastructure.admin.audit.logger import get_audit_logger
from src._core.infrastructure.admin.auth import (
    get_admin_account_use_case,
    require_auth,
)
from src._core.infrastructure.admin.base_admin_page import BaseAdminPage
from src._core.infrastructure.admin.error_handler import (
    AdminErrorHandler,
    admin_error_boundary,
)
from src._core.infrastructure.admin.layout import admin_layout, button_loading
from src._core.infrastructure.admin.theme import AdminClasses
from src.admin_identity.domain.dtos.admin_identity_dto import (
    AdminIdentityDTO,
    CreateAdminAccountDTO,
)
from src.admin_identity.domain.exceptions.admin_identity_exceptions import (
    AdminLastAccountsGuardException,
    AdminSelfActionForbiddenException,
)

# page_configs is injected by bootstrap_admin() after discovery
page_configs: list[BaseAdminPage] = []


@ui.page("/admin/accounts")
@admin_error_boundary(context="admin_accounts")
async def accounts_page():
    session = await require_auth(page_key="accounts")
    if session is None:
        return

    use_case = get_admin_account_use_case()
    all_keys = use_case.get_available_permission_keys()

    admin_layout(page_configs, current_domain="accounts", session=session)
    ui.label("Admin Accounts").classes("text-h5 q-mb-md")

    admins_container = ui.column().classes("w-full q-gutter-sm")

    async def refresh_list():
        # Defensive: this also runs after a successful create/update/delete
        # (outside those callbacks' try blocks), so a refresh-time failure must
        # still route through the central handler rather than escaping uncaught.
        try:
            admins = await use_case.list_admin_accounts()
            admins_container.clear()
            with admins_container:
                _render_admin_list(admins, session.user_id, all_keys, refresh_list)
        except Exception as exc:  # noqa: BLE001 - delegated to AdminErrorHandler
            await AdminErrorHandler.handle(exc, context="admin_accounts_refresh")

    # ── Create admin form ──
    with ui.expansion("Create New Admin", icon="person_add").classes("w-full q-mb-md"):
        new_username = c.text_field("Username").classes("full-width")
        new_full_name = c.text_field("Full Name").classes("full-width")
        new_email = c.text_field("Email").classes("full-width")

        ui.label("Permissions").classes("text-subtitle2 q-mt-sm")
        perm_checkboxes: dict[str, ui.checkbox] = {}
        with ui.row().classes("q-gutter-sm"):
            for key in all_keys:
                perm_checkboxes[key] = ui.checkbox(key, value=True)

        temp_pw_label = ui.label("").classes("text-mono text-weight-bold q-mt-sm")
        temp_pw_label.set_visibility(False)

        async def create_account():
            username = new_username.value.strip()
            full_name = new_full_name.value.strip()
            email = new_email.value.strip()
            if not (username and full_name and email):
                ui.notify("All fields are required", type="warning")
                return
            selected = [k for k, cb in perm_checkboxes.items() if cb.value]
            async with button_loading(create_btn):
                try:
                    new_admin, temp_pw = await use_case.create_account(
                        CreateAdminAccountDTO(
                            username=username,
                            full_name=full_name,
                            email=email,
                            permissions=selected,
                        )
                    )
                except Exception as exc:  # noqa: BLE001 - delegated to handler
                    await get_audit_logger().log(
                        action=AdminAction.ACCOUNT_CREATE,
                        domain="user",
                        result=AuditResult.FAILURE,
                        failure_reason=getattr(exc, "error_code", None)
                        or type(exc).__name__,
                    )
                    await AdminErrorHandler.handle(exc, context="admin_account_create")
                    return

            await get_audit_logger().log(
                action=AdminAction.ACCOUNT_CREATE,
                domain="user",
                result=AuditResult.SUCCESS,
                record_id=str(new_admin.id),
                after_state=safe_user_snapshot(new_admin),
            )
            new_username.set_value("")
            new_full_name.set_value("")
            new_email.set_value("")
            msg = "Temp password for " + new_admin.username + " (copy now): " + temp_pw
            temp_pw_label.set_text(msg)
            temp_pw_label.set_visibility(True)
            ui.notify("Admin '" + new_admin.username + "' created", type="positive")
            await refresh_list()

        create_btn = (
            ui.button("Create", on_click=create_account)
            .props("color=primary")
            .classes("q-mt-sm")
        )

    await refresh_list()


def _render_admin_list(
    admins: list[AdminIdentityDTO],
    requesting_admin_id: int,
    all_keys: list[str],
    refresh_cb,
) -> None:
    use_case = get_admin_account_use_case()

    for admin in admins:
        with ui.card().classes("w-full"):
            with ui.row().classes("items-center justify-between full-width"):
                with ui.column():
                    ui.label(admin.username).classes("text-weight-bold")
                    ui.label(admin.full_name).classes("text-caption")
                    ui.label(admin.email).classes(f"text-caption {AdminClasses.MUTED}")
                    flags = []
                    if admin.is_bootstrap_admin:
                        flags.append("bootstrap")
                    if admin.password_temporary:
                        flags.append("temp-pw")
                    if flags:
                        ui.label(", ".join(flags)).classes("text-caption text-warning")
                    perms_text = ", ".join(admin.permissions) or "(none)"
                    ui.label("Permissions: " + perms_text).classes("text-caption")

                with ui.row().classes("q-gutter-sm"):
                    # ── Edit permissions button ──
                    async def open_edit_perms(a=admin):
                        with c.action_dialog("Edit permissions: " + a.username) as (
                            dlg,
                            _card,
                        ):
                            perm_cbs: dict[str, ui.checkbox] = {}
                            with ui.row().classes("q-gutter-sm"):
                                for key in all_keys:
                                    perm_cbs[key] = ui.checkbox(
                                        key,
                                        value=key in (a.permissions or []),
                                    )

                            async def save_perms(a=a):
                                selected = [k for k, cb in perm_cbs.items() if cb.value]
                                before_perms = list(a.permissions or [])
                                async with button_loading(save_btn):
                                    try:
                                        await use_case.update_permissions(
                                            admin_id=a.id,
                                            permissions=selected,
                                            requesting_admin_id=requesting_admin_id,
                                        )
                                    except AdminLastAccountsGuardException as exc:
                                        await get_audit_logger().log(
                                            action=AdminAction.PERMISSIONS_UPDATE,
                                            domain="user",
                                            result=AuditResult.FAILURE,
                                            record_id=str(a.id),
                                            before_state={"permissions": before_perms},
                                            after_state={"permissions": selected},
                                            failure_reason=exc.error_code,
                                        )
                                        ui.notify(
                                            "Cannot remove the last accounts-permission holder",
                                            type="negative",
                                        )
                                        return
                                    except Exception as exc:  # noqa: BLE001 - delegated
                                        await get_audit_logger().log(
                                            action=AdminAction.PERMISSIONS_UPDATE,
                                            domain="user",
                                            result=AuditResult.FAILURE,
                                            record_id=str(a.id),
                                            before_state={"permissions": before_perms},
                                            after_state={"permissions": selected},
                                            failure_reason=getattr(
                                                exc, "error_code", None
                                            )
                                            or type(exc).__name__,
                                        )
                                        await AdminErrorHandler.handle(
                                            exc,
                                            context="admin_account_update_permissions",
                                        )
                                        return
                                await get_audit_logger().log(
                                    action=AdminAction.PERMISSIONS_UPDATE,
                                    domain="user",
                                    result=AuditResult.SUCCESS,
                                    record_id=str(a.id),
                                    before_state={"permissions": before_perms},
                                    after_state={"permissions": selected},
                                )
                                ui.notify("Permissions updated", type="positive")
                                dlg.close()
                                await refresh_cb()

                            with ui.row().classes("q-mt-md justify-end q-gutter-sm"):
                                ui.button("Cancel", on_click=dlg.close).props("flat")
                                save_btn = ui.button("Save", on_click=save_perms).props(
                                    "color=primary"
                                )

                    ui.button(icon="edit", on_click=open_edit_perms).props(
                        "flat round"
                    ).tooltip("Edit permissions")

                    # ── Remove admin button ──
                    async def open_remove_confirm(a=admin):
                        # confirm_dialog owns loading + close/refresh ordering;
                        # on_confirm owns the work, audit, and notifications and
                        # returns success so the dialog closes + refreshes only
                        # then (stays open on failure).
                        async def _on_confirm(a=a) -> bool:
                            success = False
                            audit_failure_reason: str | None = None
                            try:
                                await use_case.delete_account(
                                    admin_id=a.id,
                                    requesting_admin_id=requesting_admin_id,
                                )
                                success = True
                            except AdminSelfActionForbiddenException as exc:
                                audit_failure_reason = exc.error_code
                                c.toast_error("Cannot remove your own account")
                            except AdminLastAccountsGuardException as exc:
                                audit_failure_reason = exc.error_code
                                c.toast_error(
                                    "Cannot remove the last accounts-permission holder"
                                )
                            except Exception as exc:  # noqa: BLE001 - delegated
                                audit_failure_reason = (
                                    getattr(exc, "error_code", None)
                                    or type(exc).__name__
                                )
                                await c.report_error(
                                    exc, context="admin_account_delete"
                                )
                            await get_audit_logger().log(
                                action=AdminAction.ACCOUNT_DELETE,
                                domain="user",
                                result=AuditResult.SUCCESS
                                if success
                                else AuditResult.FAILURE,
                                record_id=str(a.id),
                                before_state=safe_user_snapshot(a),
                                failure_reason=audit_failure_reason,
                            )
                            if success:
                                c.toast_success("Admin '" + a.username + "' removed")
                            return success

                        await c.confirm_dialog(
                            "Remove admin: " + a.username + "?",
                            "This action cannot be undone.",
                            on_confirm=_on_confirm,
                            on_success=refresh_cb,
                            danger=True,
                            confirm_label="Remove",
                        )

                    is_self = admin.id == requesting_admin_id
                    disable_prop = "disable" if is_self else ""
                    tooltip_msg = (
                        "Cannot remove own account" if is_self else "Remove admin"
                    )
                    ui.button(icon="person_remove", on_click=open_remove_confirm).props(
                        "flat round color=negative " + disable_prop
                    ).tooltip(tooltip_msg)
