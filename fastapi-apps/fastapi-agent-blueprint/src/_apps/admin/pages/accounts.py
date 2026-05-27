from nicegui import ui

from src._core.infrastructure.admin.auth import (
    get_admin_account_use_case,
    require_auth,
)
from src._core.infrastructure.admin.base_admin_page import BaseAdminPage
from src._core.infrastructure.admin.layout import admin_layout
from src.auth.domain.exceptions.auth_exceptions import (
    AdminLastAccountsGuardException,
    AdminSelfActionForbiddenException,
)
from src.user.domain.dtos.user_dto import CreateAdminAccountDTO, UserDTO

# page_configs is injected by bootstrap_admin() after discovery
page_configs: list[BaseAdminPage] = []


@ui.page("/admin/accounts")
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
        admins = await use_case.list_admin_accounts()
        admins_container.clear()
        with admins_container:
            _render_admin_list(admins, session.user_id, all_keys, refresh_list)

    # ── Create admin form ──
    with ui.expansion("Create New Admin", icon="person_add").classes("w-full q-mb-md"):
        new_username = ui.input("Username").classes("full-width")
        new_full_name = ui.input("Full Name").classes("full-width")
        new_email = ui.input("Email").classes("full-width")

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
            try:
                new_admin, temp_pw = await use_case.create_account(
                    CreateAdminAccountDTO(
                        username=username,
                        full_name=full_name,
                        email=email,
                        permissions=selected,
                    )
                )
            except Exception as exc:
                ui.notify(str(exc), type="negative")
                return

            new_username.set_value("")
            new_full_name.set_value("")
            new_email.set_value("")
            msg = "Temp password for " + new_admin.username + " (copy now): " + temp_pw
            temp_pw_label.set_text(msg)
            temp_pw_label.set_visibility(True)
            ui.notify("Admin '" + new_admin.username + "' created", type="positive")
            await refresh_list()

        ui.button("Create", on_click=create_account).props("color=primary").classes(
            "q-mt-sm"
        )

    await refresh_list()


def _render_admin_list(
    admins: list[UserDTO],
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
                    ui.label(admin.email).classes("text-caption text-grey-7")
                    flags = []
                    if admin.is_bootstrap_admin:
                        flags.append("bootstrap")
                    if admin.password_temporary:
                        flags.append("temp-pw")
                    if flags:
                        ui.label(", ".join(flags)).classes("text-caption text-orange")
                    perms_text = ", ".join(admin.permissions) or "(none)"
                    ui.label("Permissions: " + perms_text).classes("text-caption")

                with ui.row().classes("q-gutter-sm"):
                    # ── Edit permissions button ──
                    async def open_edit_perms(a=admin):
                        with ui.dialog() as dlg, ui.card():
                            ui.label("Edit permissions: " + a.username).classes(
                                "text-h6 q-mb-sm"
                            )
                            perm_cbs: dict[str, ui.checkbox] = {}
                            with ui.row().classes("q-gutter-sm"):
                                for key in all_keys:
                                    perm_cbs[key] = ui.checkbox(
                                        key,
                                        value=key in (a.permissions or []),
                                    )

                            async def save_perms(a=a):
                                selected = [k for k, cb in perm_cbs.items() if cb.value]
                                try:
                                    await use_case.update_permissions(
                                        admin_id=a.id,
                                        permissions=selected,
                                        requesting_admin_id=requesting_admin_id,
                                    )
                                except AdminLastAccountsGuardException:
                                    ui.notify(
                                        "Cannot remove the last accounts-permission holder",
                                        type="negative",
                                    )
                                    return
                                except Exception as exc:
                                    ui.notify(str(exc), type="negative")
                                    return
                                ui.notify("Permissions updated", type="positive")
                                dlg.close()
                                await refresh_cb()

                            with ui.row().classes("q-mt-md"):
                                ui.button("Save", on_click=save_perms).props(
                                    "color=primary"
                                )
                                ui.button("Cancel", on_click=dlg.close).props("flat")
                        dlg.open()

                    ui.button(icon="edit", on_click=open_edit_perms).props(
                        "flat round"
                    ).tooltip("Edit permissions")

                    # ── Remove admin button ──
                    async def open_remove_confirm(a=admin):
                        with ui.dialog() as dlg, ui.card():
                            ui.label("Remove admin: " + a.username + "?").classes(
                                "text-h6"
                            )
                            ui.label("This action cannot be undone.").classes(
                                "text-caption text-negative q-mb-md"
                            )

                            async def confirm_remove(a=a):
                                try:
                                    await use_case.delete_account(
                                        admin_id=a.id,
                                        requesting_admin_id=requesting_admin_id,
                                    )
                                except AdminSelfActionForbiddenException:
                                    ui.notify(
                                        "Cannot remove your own account",
                                        type="negative",
                                    )
                                    dlg.close()
                                    return
                                except AdminLastAccountsGuardException:
                                    ui.notify(
                                        "Cannot remove the last accounts-permission holder",
                                        type="negative",
                                    )
                                    dlg.close()
                                    return
                                except Exception as exc:
                                    ui.notify(str(exc), type="negative")
                                    dlg.close()
                                    return
                                ui.notify(
                                    "Admin '" + a.username + "' removed",
                                    type="positive",
                                )
                                dlg.close()
                                await refresh_cb()

                            with ui.row():
                                ui.button("Remove", on_click=confirm_remove).props(
                                    "color=negative"
                                )
                                ui.button("Cancel", on_click=dlg.close).props("flat")
                        dlg.open()

                    is_self = admin.id == requesting_admin_id
                    disable_prop = "disable" if is_self else ""
                    tooltip_msg = (
                        "Cannot remove own account" if is_self else "Remove admin"
                    )
                    ui.button(icon="person_remove", on_click=open_remove_confirm).props(
                        "flat round color=negative " + disable_prop
                    ).tooltip(tooltip_msg)
