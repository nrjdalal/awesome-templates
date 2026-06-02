from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from nicegui import app, ui

from src._core.config import settings
from src._core.infrastructure.admin.audit import AdminAction, AuditResult
from src._core.infrastructure.admin.audit.logger import get_audit_logger
from src._core.infrastructure.admin.auth import AdminAuthProvider
from src._core.infrastructure.admin.theme import AdminClasses
from src.admin_identity.domain.dtos.admin_identity_dto import AdminSessionDTO

# Session key holding the operator's explicit dark-mode override (#193). Unset
# means "no preference" → defer to ``admin_dark_mode_default`` (which may itself
# be None = follow the browser's prefers-color-scheme).
_DARK_MODE_KEY = "admin_dark_mode"

if TYPE_CHECKING:
    from src._core.infrastructure.admin.base_admin_page import BaseAdminPage


@asynccontextmanager
async def button_loading(button: ui.button) -> AsyncIterator[None]:
    """Show Quasar ``loading`` + ``disable`` on a button while an async op runs.

    Gives immediate feedback on slow admin write actions and blocks duplicate
    submits. Cleanup runs in ``finally`` so the button is always re-enabled —
    even when the wrapped block raises or returns early.

    Usage::

        async def on_click() -> None:
            async with button_loading(submit_btn):
                await slow_operation()
    """
    button.props("loading disable")
    try:
        yield
    finally:
        button.props(remove="loading disable")


def admin_layout(
    page_configs: list[BaseAdminPage],
    current_domain: str = "",
    session: AdminSessionDTO | None = None,
) -> None:
    """Render the shared admin shell: header + left drawer navigation.

    Pass the AdminSessionDTO returned by require_auth() so nav and dashboard
    cards are filtered to the current user's permissions.
    """
    permissions: set[str] | None = set(session.permissions) if session else None
    visible_configs = [
        pc
        for pc in page_configs
        if permissions is None or pc.domain_name in permissions
    ]

    # Create the drawer first so the header hamburger can toggle it. Quasar
    # auto-overlays the drawer below its breakpoint (narrow viewports); the
    # hamburger also lets desktop users collapse it.
    drawer = ui.left_drawer(top_corner=True, bottom_corner=True).classes(
        AdminClasses.DRAWER
    )

    with ui.header(elevated=True).classes(
        f"items-center justify-between {AdminClasses.HEADER}"
    ):
        # Brand: a hamburger (responsive toggle) + an icon standing in for a
        # project logo (swap for ui.image in a fork) + the brand name.
        with ui.row().classes(f"items-center q-gutter-sm {AdminClasses.BRAND}"):
            ui.button(icon="menu", on_click=drawer.toggle).props("flat dense")
            ui.icon("smart_toy").classes("text-h5")
            ui.label(settings.admin_brand_name).classes("text-h6")
        with ui.row().classes("items-center q-gutter-xs"):
            _render_dark_mode_toggle()
            username = session.username if session else _app_username()
            if username:
                with ui.button(username, icon="account_circle").props("flat"):
                    with ui.menu():
                        ui.menu_item(
                            "Change Password",
                            lambda: ui.navigate.to("/admin/change-password"),
                        )
            ui.button(
                icon="logout",
                on_click=_handle_logout,
            ).props("flat")

    with drawer:
        _nav_item(
            label="Dashboard",
            icon="dashboard",
            target="/admin/",
            active=current_domain == "",
        )

        if visible_configs:
            _nav_section("Operations")
            for page_config in visible_configs:
                _nav_item(
                    label=page_config.display_name,
                    icon=page_config.icon,
                    target=f"/admin/{page_config.domain_name}",
                    active=page_config.domain_name == current_domain,
                )

        show_accounts = permissions is None or "accounts" in permissions
        show_audit = permissions is None or "audit_log" in permissions
        if show_accounts or show_audit:
            _nav_section("Management")
            if show_accounts:
                _nav_item(
                    label="Accounts",
                    icon="manage_accounts",
                    target="/admin/accounts",
                    active=current_domain == "accounts",
                )
            if show_audit:
                _nav_item(
                    label="Audit Log",
                    icon="fact_check",
                    target="/admin/audit-log",
                    active=current_domain == "audit_log",
                )


def _nav_section(title: str) -> None:
    """Render a muted, uppercase section header in the sidebar."""
    ui.label(title).classes(f"{AdminClasses.NAV_SECTION} q-mt-md q-mb-xs q-ml-md")


def _nav_item(*, label: str, icon: str, target: str, active: bool) -> None:
    """Render one sidebar nav item, highlighted when it is the active route."""
    item = ui.item(on_click=lambda: ui.navigate.to(target))
    if active:
        item.classes(AdminClasses.NAV_ACTIVE_ITEM)
    with item:
        with ui.item_section().props("avatar"):
            ui.icon(icon).classes(AdminClasses.ACCENT_ICON if active else "")
        with ui.item_section():
            text = ui.label(label)
            if active:
                text.classes(AdminClasses.NAV_ACTIVE)


def _render_dark_mode_toggle() -> None:
    """Render the header light/dark toggle (#193).

    The ``ui.dark_mode`` handle is page-scoped, so it is created here on every
    page that renders the shell. It is seeded from the operator's stored
    preference, falling back to ``admin_dark_mode_default`` (which may be None =
    follow the browser's prefers-color-scheme, matching ``ui.run_with(dark=)``).
    Toggling flips Quasar's ``body--dark`` class live — no reload — and the new
    value is persisted so it survives navigation.
    """
    stored = _stored_dark_preference()
    dark = ui.dark_mode(value=stored)

    def _toggle() -> None:
        # ``dark.toggle()`` raises when the value is None (auto/system mode), so
        # resolve the next state explicitly via _next_dark_value.
        dark.value = _next_dark_value(dark.value)
        app.storage.user[_DARK_MODE_KEY] = dark.value

    ui.button(icon="dark_mode", on_click=_toggle).props("flat").tooltip(
        "Toggle light / dark"
    )


def _next_dark_value(current: bool | None) -> bool:
    """Resolve the next dark-mode value for a toggle click.

    From auto (None) the first toggle resolves to an explicit dark theme; from
    an explicit state it flips. Always returns a concrete bool so the persisted
    preference is unambiguous on the next page load.
    """
    return True if current is None else not current


def _stored_dark_preference() -> bool | None:
    """Read the operator's dark-mode override, defaulting to the global policy.

    Defensive against an unconfigured ``storage_secret`` (``app.storage.user``
    raises) — degrades to the configured default rather than 500-ing the page.
    """
    try:
        return app.storage.user.get(_DARK_MODE_KEY, settings.admin_dark_mode_default)
    except Exception:  # noqa: BLE001 - storage unavailable → fall back to default
        return settings.admin_dark_mode_default


def _app_username() -> str | None:
    return app.storage.user.get("username")  # type: ignore[return-value]


# Keep the old name as an alias so existing callers still work.
app_username = _app_username


async def _handle_logout() -> None:
    # Record the user-initiated logout BEFORE the session is cleared (#196).
    # AdminAuthProvider.logout() is also called from several non-user cleanup
    # paths (forced-logout, setup tear-down, ...), so audit logging lives here
    # — the explicit button — rather than inside logout().
    await get_audit_logger().log(
        action=AdminAction.LOGOUT,
        domain="auth",
        result=AuditResult.SUCCESS,
        admin_user_id=app.storage.user.get("user_id"),
        admin_username=app.storage.user.get("username") or "unknown",
    )
    AdminAuthProvider.logout()
    ui.navigate.to("/admin/login")
