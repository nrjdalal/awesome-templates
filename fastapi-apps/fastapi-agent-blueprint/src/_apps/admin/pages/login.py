from fastapi import Request
from nicegui import app, ui

from src._core.config import settings
from src._core.infrastructure.admin import components as c
from src._core.infrastructure.admin.auth import (
    AdminAuthProvider,
    get_admin_auth_provider,
)
from src._core.infrastructure.admin.layout import (
    button_loading,
    render_dark_mode_toggle,
)
from src._core.infrastructure.admin.theme import AdminClasses
from src.admin_identity.domain.exceptions.admin_identity_exceptions import (
    AdminCredentialDisabledException,
    AdminInvalidCredentialsException,
    AdminSetupRequiredException,
)


@ui.page("/admin/login")
def login_page(request: Request):
    # Capture client IP best-effort for the audit log (#196). Behind a trusted
    # proxy you would need to parse X-Forwarded-For instead; that requires
    # explicit proxy-trust configuration so we don't do it implicitly here.
    client_ip = request.client.host if request.client else None

    # Distinct dark background for the auth screen (page-scoped).
    ui.query("body").classes(AdminClasses.LOGIN_BG)

    # Light/dark toggle (top-right) — login has no shell header, so render the
    # shared toggle directly. It also establishes the page's dark-mode state, so
    # the backdrop + card switch between the light/dark login variants.
    with ui.row().classes("absolute-top-right q-pa-md"):
        render_dark_mode_toggle()

    # Left-aligned, not centred: a centred form makes labels and the error
    # message harder to scan than a single left edge. Only the card is centred.
    with ui.card().classes(f"absolute-center q-pa-lg {AdminClasses.LOGIN_CARD}"):
        # One identity line rather than three stacked elements. The icon matches
        # the shell header's brand row (same glyph, header scale) so the two
        # surfaces read as one product; a 3rem version here said nothing extra.
        with ui.row().classes("items-center q-gutter-sm"):
            ui.icon("smart_toy").classes(f"text-h5 {AdminClasses.ACCENT_ICON}")
            ui.label(settings.admin_brand_name).classes("text-h6 text-weight-bold")
        # Replaces a letterspaced "ADMIN" that read as decoration. This says the
        # same thing as a sentence, and the realm distinction is real: admin
        # credentials are a separate identity store from the customer API (#218).
        ui.label("Administrator sign-in").classes(f"{AdminClasses.MUTED} q-mb-md")

        # A persistent slot, not a toast. `ui.notify` fades, so a few seconds
        # after a failed attempt the screen shows no reason for it — the operator
        # is left re-reading a form that looks fine. Cleared on the next submit.
        error = ui.label().classes("text-negative q-mb-sm")
        error.set_visibility(False)

        username = c.text_field("Username").classes("full-width").props("autofocus")
        password = c.text_field("Password", password=True).classes("full-width q-mt-sm")

        async def try_login():
            target: str | None = None
            # Clear the previous reason before trying again, so a stale message
            # can never sit next to a fresh attempt.
            error.set_visibility(False)
            async with button_loading(login_btn):
                try:
                    session = await get_admin_auth_provider().authenticate(
                        username.value,
                        password.value,
                        ip_address=client_ip,
                    )
                except AdminSetupRequiredException:
                    app.storage.user["setup_granted"] = True
                    target = "/admin/setup"
                except (
                    AdminInvalidCredentialsException,
                    AdminCredentialDisabledException,
                ):
                    # Deliberately does not distinguish "no such account" from
                    # "wrong password" or "credential disabled" — all three
                    # collapse to one message so the form cannot be used to probe
                    # which admin usernames exist.
                    error.set_text("Invalid credentials")
                    error.set_visibility(True)
                else:
                    AdminAuthProvider.login(session)
                    target = "/admin/"
            # Navigate only after loading state is cleared (button not yet torn down).
            if target:
                ui.navigate.to(target)

        # Both fields, not just the password one: with autofocus on username,
        # typing a name and pressing Enter was previously a no-op.
        username.on("keydown.enter", try_login)
        password.on("keydown.enter", try_login)
        login_btn = (
            ui.button("Login", on_click=try_login)
            .props("color=primary unelevated size=lg")
            .classes("q-mt-md full-width")
        )
