from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
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

    # Create the drawer first so the header hamburger can toggle it. Both the
    # full drawer and the collapsed mini rail offset the content (push, not
    # overlay) on desktop; Quasar still auto-overlays below its breakpoint on
    # narrow viewports. (``mini-to-overlay`` was dropped — it made the expanded
    # desktop drawer overlay and hide content.)
    drawer = ui.left_drawer(top_corner=True, bottom_corner=True).classes(
        AdminClasses.DRAWER
    )

    # On desktop the toggle collapses the drawer to an icon-only mini rail
    # rather than hiding it, so navigation stays reachable while reclaiming
    # content width. On narrow viewports Quasar overlays the drawer and ``mini``
    # has no effect, so there we fall back to a plain show/hide toggle — without
    # this, the menu button would do nothing on mobile.
    nav_mini = False
    # The in-drawer chevron, assigned once the collapse control renders below;
    # its direction flips on each toggle.
    collapse_icon: ui.icon | None = None

    async def _toggle_nav() -> None:
        nonlocal nav_mini
        # run_javascript may raise TimeoutError (NiceGUI 3.9+) if the client is
        # slow/disconnected; fall back to the desktop mini toggle rather than
        # letting the event handler raise.
        try:
            width = await ui.run_javascript("window.innerWidth", timeout=2.0)
        except Exception:  # noqa: BLE001 - timeout/transport error → desktop default
            width = None
        if isinstance(width, (int, float)) and width < 1024:
            drawer.toggle()
            return
        nav_mini = not nav_mini
        drawer.props(add="mini") if nav_mini else drawer.props(remove="mini")
        if collapse_icon is not None:
            collapse_icon.props(
                f"name={'chevron_right' if nav_mini else 'chevron_left'}"
            )

    with ui.header(elevated=True).classes(
        f"items-center justify-between {AdminClasses.HEADER}"
    ):
        # Brand: a hamburger + an icon standing in for a project logo (swap for
        # ui.image in a fork) + the brand name. The hamburger is mobile-only
        # (``lt-md``): below the breakpoint Quasar overlays the drawer and the
        # in-drawer collapse control is hidden with it, so a header trigger is
        # the only way to reopen. On desktop the in-drawer control owns this.
        with ui.row().classes(f"items-center q-gutter-sm {AdminClasses.BRAND}"):
            ui.button(icon="menu", on_click=_toggle_nav).props(
                'flat dense aria-label="Toggle navigation"'
            ).classes("lt-md")
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
        # Collapse control at the TOP of the drawer (above the nav), set off by a
        # separator: prominent enough to notice, and the directional chevron +
        # divider keep it from reading as just another nav icon in the mini rail.
        collapse_icon = _render_collapse_control(on_click=_toggle_nav)
        ui.separator().classes("q-my-xs")

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


def _render_collapse_control(*, on_click: Callable[[], Awaitable[None]]) -> ui.icon:
    """Render the 'Collapse' control (top of the drawer) that toggles the mini rail.

    Attached to the drawer (not the header) so the affordance sits on the panel
    it controls — far more discoverable than the detached header hamburger, and
    placed at the top (above a separator) so it is noticeable without being
    mistaken for a nav item. Built as a ``ui.item`` so Quasar hides the text
    label in the mini rail, leaving just the chevron. Returns the chevron handle
    so :func:`admin_layout`'s toggle can flip its direction.
    """
    item = ui.item(on_click=on_click).props('aria-label="Collapse sidebar"')
    with item:
        with ui.item_section().props("avatar"):
            icon = ui.icon("chevron_left").classes(AdminClasses.MUTED)
        with ui.item_section():
            ui.label("Collapse").classes(AdminClasses.MUTED)
    return icon


def _nav_item(*, label: str, icon: str, target: str, active: bool) -> None:
    """Render one sidebar nav item, highlighted when it is the active route.

    Carries a tooltip + ``aria-label`` so the item stays identifiable when the
    drawer collapses to the icon-only mini rail (the text label is hidden then).
    """
    item = ui.item(on_click=lambda: ui.navigate.to(target))
    item.props(f'aria-label="{label}"').tooltip(label)
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
